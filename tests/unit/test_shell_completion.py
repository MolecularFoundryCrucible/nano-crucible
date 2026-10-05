"""Unit coverage for interactive shell completion."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from prompt_toolkit.document import Document

from crucible.cli import dataset, instrument, project, sample, user
from crucible.cli.shell.completer import CrucibleCompleter as _CrucibleCompleter


MFID = '0tkn2knjast3h0008nyq9zps2c'


def make_completer(client=None, state=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    for module in (dataset, instrument, project, sample, user):
        module.register_subcommand(subparsers)
    return _CrucibleCompleter(
        parser,
        client=client,
        projects=[('cached-project', 'Cached Project')],
        state=state or {},
    )


def complete(completer, text):
    document = Document(text=text, cursor_position=len(text))
    return [item.text.strip() for item in completer.get_completions(document, None)]


def make_client():
    return SimpleNamespace(
        projects=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'project_id': 'project-one',
            'title': 'Project One',
        }])),
        instruments=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'instrument_id': 'xrd-one',
            'instrument_name': 'XRD One',
        }])),
        datasets=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'dataset_name': 'Perovskite Dataset',
        }])),
        samples=SimpleNamespace(search=MagicMock(return_value=[])),
        users=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': '0000-0001-6402-3752',
            'username': 'roncofaber',
            'first_name': 'Fabrice',
            'last_name': 'Roncoroni',
        }])),
    )


def test_flags_remain_available_after_project_positionals():
    completions = complete(make_completer(), 'project get project-one --i')

    assert '--include-members' in completions
    assert '--include-metadata' in completions


def test_flag_completion_hides_deprecated_aliases():
    completions = complete(make_completer(), 'sample create --')

    assert '--project-id' in completions
    assert '--type' in completions
    assert '--sample-type' not in completions
    assert '-pid' not in completions


def test_project_flag_values_use_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset search perovskite --project-id pro',
    )

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_project_mfid_flag_values_use_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'sample list --project-mfid pro',
    )

    assert MFID in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_project_positionals_use_project_search():
    client = make_client()

    completions = complete(make_completer(client), 'project get pro')

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_instrument_positionals_use_instrument_search():
    client = make_client()

    completions = complete(make_completer(client), 'instrument get xrd')

    assert 'xrd-one' in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_instrument_mfid_flags_use_instrument_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset list --instrument-mfid xrd',
    )

    assert MFID in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_dataset_create_instrument_id_uses_instrument_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset create --instrument-id xrd',
    )

    assert 'xrd-one' in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_dataset_positionals_use_scoped_dataset_search():
    client = make_client()

    completions = complete(
        make_completer(client, state={'project': 'project-one'}),
        'dataset get per',
    )

    assert MFID in completions
    client.datasets.search.assert_called_once_with(
        'per', project_id='project-one')


def test_user_flags_use_user_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'project add-user project-one --user ron',
    )

    assert 'roncofaber' in completions
    client.users.search.assert_called_once_with('ron')


def test_reassignment_target_uses_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        f'dataset reassign-project {MFID} pro',
    )

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_parent_flag_uses_resource_search_not_project_search():
    client = make_client()

    completions = complete(
        make_completer(client, state={'project': 'project-one'}),
        'dataset link --parent per',
    )

    assert MFID in completions
    client.datasets.search.assert_called_once_with(
        'per', project_id='project-one')
    client.projects.search.assert_not_called()


def test_fixed_flag_choices_are_completed():
    completions = complete(
        make_completer(),
        'instrument search xrd --status m',
    )

    assert completions == ['maintenance']


def test_project_scope_choices_are_completed():
    completions = complete(
        make_completer(),
        'dataset list --project-scope s',
    )

    assert completions == ['shared']


@pytest.mark.parametrize('line, expected', [
    ('pwd', '_pwd'),
    ('cd /tmp', '_cd'),
    ('cd', '_cd'),
    ('!echo hi', '_bang'),
    ('debug on', '_debug'),
    ('elevated', '_elevated'),
    ('use my-project', '_use'),
    ('v', '_toggle_verbose'),
    ('v extra', None),
    ('refresh now', None),
    ('lsof', None),
    ('dataset list', None),
])
def test_builtin_lookup(line, expected):
    from crucible.cli.shell.builtins import find_builtin

    handler = find_builtin(line)
    assert (handler.__name__ if handler else None) == expected


def _facet_completer(state=None):
    from crucible.cli import dataset as dataset_cli, sample as sample_cli

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    dataset_cli.register_subcommand(subparsers)
    sample_cli.register_subcommand(subparsers)
    client = MagicMock()
    client.datasets.facets.return_value = {'items': [
        {'value': 'XRD', 'label': 'XRD', 'count': 9},
        {'value': '4D-STEM', 'label': '4D-STEM', 'count': 4},
        {'value': None, 'label': None, 'count': 2},
    ]}
    client.samples.facets.return_value = {'items': [
        {'value': 'thin film', 'label': 'thin film', 'count': 3},
    ]}
    return _CrucibleCompleter(parser, client=client, state=state or {}), client


def _texts(completer, line):
    return [c.text for c in completer.get_completions(Document(line), None)]


def test_measurement_values_come_from_facets_in_the_current_project():
    completer, client = _facet_completer({'project': 'my-project'})

    assert _texts(completer, 'dataset list -m X') == ['XRD ']
    assert client.datasets.facets.call_args.kwargs['project_id'] == 'my-project'


def test_typed_project_id_overrides_the_current_project():
    completer, client = _facet_completer({'project': 'my-project'})

    _texts(completer, 'dataset list --project-id other -m ')

    assert client.datasets.facets.call_args.kwargs['project_id'] == 'other'


def test_all_projects_drops_the_project_scope():
    completer, client = _facet_completer({'project': 'my-project'})

    _texts(completer, 'dataset list --all-projects --measurement ')

    assert 'project_id' not in client.datasets.facets.call_args.kwargs


def test_values_with_spaces_are_quoted_and_null_buckets_skipped():
    completer, _ = _facet_completer()

    assert _texts(completer, 'sample list --type ') == ["'thin film' "]
    assert None not in _texts(completer, 'dataset list -m ')


def test_facet_values_are_cached_per_project():
    completer, client = _facet_completer({'project': 'p'})

    _texts(completer, 'dataset list -m ')
    _texts(completer, 'dataset list -m X')

    assert client.datasets.facets.call_count == 1


def _instrument_completer():
    from crucible.cli import dataset as dataset_cli, instrument as instrument_cli
    from crucible.cli import sample as sample_cli

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    for module in (dataset_cli, sample_cli, instrument_cli):
        module.register_subcommand(subparsers)
    client = MagicMock()
    client.instruments.search.return_value = [{
        'unique_id': '0tkadnh6g9zys00089c7g5ycmg', 'instrument_id': 'b30-fei-sem',
        'instrument_name': 'b30 - fei sem'}]
    client.users.search.return_value = [{
        'username': 'jdoe', 'unique_id': '0000-0002-1825-0097',
        'first_name': 'J', 'last_name': 'Doe'}]
    client.samples.search.return_value = [{'unique_id': 'S' * 26, 'sample_name': 'wafer'}]
    return _CrucibleCompleter(parser, client=client, state={})


@pytest.mark.parametrize('line, expected', [
    ('instrument add-user b30', 'b30-fei-sem '),
    ('instrument list-users b30', 'b30-fei-sem '),
    ('instrument add-user b30-fei-sem --user jdo', 'jdoe '),
    ('instrument update-user-role b30-fei-sem jdo', 'jdoe '),
    ('instrument update-user-role b30-fei-sem jdoe ', 'admin '),
    ('instrument add-user b30-fei-sem --role ', 'editor '),
    ('dataset list --instrument-id b30', 'b30-fei-sem '),
    ('dataset list --sample-mfid waf', 'S' * 26 + ' '),
    ('dataset facets se', 'session '),
    ('sample facets s', 'sample_type '),
    ('dataset list --missing ', 'session '),
])
def test_new_commands_and_flags_complete(line, expected):
    assert expected in _texts(_instrument_completer(), line)
