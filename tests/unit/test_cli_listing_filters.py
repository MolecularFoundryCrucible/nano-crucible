"""Unit coverage for the shared CLI listing filters."""

import argparse

import pytest

from crucible.cli import dataset, sample
from crucible.cli.helpers import listing_filter_kwargs, scope_filter_kwargs


def make_parser(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    module.register_subcommand(subparsers)
    return parser


@pytest.mark.parametrize('module', [dataset, sample])
def test_defaults_produce_no_filter_keywords(module):
    args = make_parser(module).parse_args([module.__name__.split('.')[-1], 'list'])

    assert listing_filter_kwargs(args) == {'sort': 'created', 'direction': 'desc'}


@pytest.mark.parametrize('module', [dataset, sample])
def test_sort_and_direction_are_collected(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args(
        [name, 'list', '--sort', 'created', '--direction', 'asc'])

    assert listing_filter_kwargs(args) == {'sort': 'created', 'direction': 'asc'}


@pytest.mark.parametrize('module', [dataset, sample])
def test_mine_maps_to_the_owner_affiliation(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args([name, 'list', '--mine', '--all-projects'])

    assert scope_filter_kwargs(args) == {'affiliation': 'owner'}


@pytest.mark.parametrize('module', [dataset, sample])
def test_time_bounds_are_collected(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args([
        name, 'list', '--created-after', '2026-01-01',
        '--modified-before', '2026-06-01', '--all-projects',
    ])

    assert scope_filter_kwargs(args) == {
        'creation_time_gte': '2026-01-01',
        'modification_time_lte': '2026-06-01',
    }


@pytest.mark.parametrize('module', [dataset, sample])
def test_invalid_sort_is_rejected_by_argparse(module):
    name = module.__name__.split('.')[-1]

    with pytest.raises(SystemExit):
        make_parser(module).parse_args([name, 'list', '--sort', 'bogus'])


def _run_list(module, argv, records, monkeypatch, config_data=None):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    name = module.__name__.split('.')[-1]
    operation = SimpleNamespace(list=MagicMock(return_value=records))
    client = SimpleNamespace(**{f'{name}s': operation},
                             users=SimpleNamespace(get=MagicMock(
                                 return_value={'unique_id': '0000-0002-1825-0097'})))
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.config.config._data', dict(config_data or {}))
    args = make_parser(module).parse_args([name, 'list'] + argv)
    args.func(args)
    return operation.list


def _names(output, prefix):
    return [line.split()[0] for line in output.splitlines()
            if line.strip().startswith(prefix)]


@pytest.mark.parametrize('module, key', [(dataset, 'dataset_name'), (sample, 'sample_name')])
def test_newest_record_is_printed_last(module, key, monkeypatch, capsys):
    newest_first = [{key: 'item-3', 'unique_id': 'c'},
                    {key: 'item-2', 'unique_id': 'b'},
                    {key: 'item-1', 'unique_id': 'a'}]

    _run_list(module, ['--all-projects'], newest_first, monkeypatch)

    assert _names(capsys.readouterr().out, 'item-') == ['item-1', 'item-2', 'item-3']


@pytest.mark.parametrize('module, key', [(dataset, 'dataset_name'), (sample, 'sample_name')])
def test_explicit_ascending_sort_keeps_server_order(module, key, monkeypatch, capsys):
    ascending = [{key: 'alpha'}, {key: 'beta'}, {key: 'gamma'}]

    list_call = _run_list(module, ['--all-projects', '--sort', 'name',
                                   '--direction', 'asc'], ascending, monkeypatch)

    out = capsys.readouterr().out
    assert [n for n in ('alpha', 'beta', 'gamma') if n in out] == ['alpha', 'beta', 'gamma']
    assert out.index('alpha') < out.index('gamma')
    assert list_call.call_args.kwargs['sort'] == 'name'


@pytest.mark.parametrize('module', [dataset, sample])
def test_no_project_lists_every_accessible_project(module, monkeypatch, capsys):
    list_call = _run_list(module, [], [], monkeypatch)

    kwargs = list_call.call_args.kwargs
    assert 'project_id' not in kwargs and 'project_mfid' not in kwargs
    assert 'all projects' in capsys.readouterr().out


@pytest.mark.parametrize('module', [dataset, sample])
def test_current_project_still_applies_unless_all_projects(module, monkeypatch):
    current = {'current_project': 'my-project'}

    scoped = _run_list(module, [], [], monkeypatch, current)
    unscoped = _run_list(module, ['--all-projects'], [], monkeypatch, current)

    assert scoped.call_args.kwargs['project_id'] == 'my-project'
    assert 'project_id' not in unscoped.call_args.kwargs


def test_dataset_filters_reach_the_api(monkeypatch):
    list_call = _run_list(dataset, [
        '--all-projects', '--name', 'run-1', '--sample-mfid', 'S' * 26,
        '--missing', 'session', '--missing', 'instrument',
        '--owner', 'alice', '-m', 'XRD',
    ], [], monkeypatch)

    kwargs = list_call.call_args.kwargs
    assert kwargs['dataset_name'] == 'run-1'
    assert kwargs['sample_mfid'] == 'S' * 26
    assert kwargs['session_name_is_null'] is True
    assert kwargs['instrument_mfid_is_null'] is True
    assert kwargs['owner_id'] == '0000-0002-1825-0097'
    assert kwargs['measurement'] == 'XRD'


def test_sample_filters_reach_the_api(monkeypatch):
    list_call = _run_list(sample, [
        '--all-projects', '--dataset-mfid', 'D' * 26, '--description', 'note',
        '--missing', 'sample_type', '--type', 'wafer',
    ], [], monkeypatch)

    kwargs = list_call.call_args.kwargs
    assert kwargs['dataset_mfid'] == 'D' * 26
    assert kwargs['description'] == 'note'
    assert kwargs['sample_type_is_null'] is True
    assert kwargs['sample_type'] == 'wafer'


def test_groups_follow_chronology_with_newest_group_last(capsys):
    from crucible.cli.helpers import display_order, group_records

    newest_first = [{'m': 'XRD', 'n': 4}, {'m': 'SEM', 'n': 3},
                    {'m': 'XRD', 'n': 2}, {'m': 'SEM', 'n': 1}]

    groups = group_records(display_order(newest_first), 'm')

    assert [key for key, _ in groups] == ['SEM', 'XRD']
    assert [[r['n'] for r in rows] for _, rows in groups] == [[1, 3], [2, 4]]
