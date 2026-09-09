"""Unit coverage for raw JSON output from read-only CLI commands."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset as dataset_cli
from crucible.cli import instrument as instrument_cli
from crucible.cli import project as project_cli
from crucible.cli import sample as sample_cli
from crucible.cli import service_account as service_account_cli
from crucible.cli import user as user_cli


MFID = '0tkn2knjast3h0008nyq9zps2c'


def parse_command(register, command, *arguments):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    register(subparsers)
    return parser.parse_args([command] + list(arguments))


@pytest.mark.parametrize(('register', 'command', 'arguments'), [
    (project_cli._register_list, 'list', ('--json',)),
    (dataset_cli._register_search, 'search', ('query', '--json')),
    (sample_cli._register_search, 'search', ('query', '--json')),
    (project_cli._register_search, 'search', ('query', '--json')),
    (instrument_cli._register_search, 'search', ('query', '--json')),
    (dataset_cli._register_search_metadata, 'search-metadata', ('query', '--json')),
    (sample_cli._register_search_metadata, 'search-metadata', ('query', '--json')),
    (project_cli._register_search_metadata, 'search-metadata', ('query', '--json')),
    (instrument_cli._register_search_metadata, 'search-metadata', ('query', '--json')),
    (user_cli._register_search, 'search', ('query', '--json')),
    (user_cli._register_list, 'list', ('--json',)),
    (service_account_cli._register_get, 'get', ('service-user', '--json')),
    (service_account_cli._register_list, 'list', ('--json',)),
])
def test_read_command_parsers_expose_json(register, command, arguments):
    args = parse_command(register, command, *arguments)

    assert args.json is True


def test_project_list_json_returns_raw_array(monkeypatch, capsys):
    projects = [{
        'unique_id': MFID,
        'project_id': 'project-one',
        'scientific_metadata': {'temperature': 300},
    }]
    client = SimpleNamespace(projects=SimpleNamespace(list=MagicMock(return_value=projects)))
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    project_cli._execute_list(SimpleNamespace(
        limit=10,
        include_metadata=True,
        json=True,
        debug=False,
    ))

    assert json.loads(capsys.readouterr().out) == projects
    client.projects.list.assert_called_once_with(limit=10, include_metadata=True)


@pytest.mark.parametrize(('json_output', 'include_datasets'), [(False, False), (True, True)])
def test_sample_get_optimizes_human_output_and_preserves_json(
        monkeypatch, capsys, json_output, include_datasets):
    sample = {'unique_id': MFID, 'resource_type': 'sample', 'datasets': []}
    operations = SimpleNamespace(get=MagicMock(return_value=sample))
    client = SimpleNamespace(samples=operations)
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(sample_cli, '_show_sample', MagicMock())

    sample_cli._execute_get(SimpleNamespace(
        sample_id=MFID,
        json=json_output,
        include_metadata=False,
        graph=False,
        verbose=False,
        debug=False,
        _shell_state=None,
    ))

    operations.get.assert_called_once_with(
        MFID,
        include_links=False,
        include_metadata=json_output,
        include_owner=True,
        include_datasets=include_datasets,
    )
    if json_output:
        assert json.loads(capsys.readouterr().out) == sample


@pytest.mark.parametrize(('module', 'resource_name'), [
    (dataset_cli, 'datasets'),
    (sample_cli, 'samples'),
    (project_cli, 'projects'),
    (instrument_cli, 'instruments'),
])
def test_resource_search_json_returns_raw_array(monkeypatch, capsys, module, resource_name):
    results = [{'unique_id': MFID, 'resource': resource_name}]
    operations = SimpleNamespace(search=MagicMock(return_value=results))
    client = SimpleNamespace(**{resource_name: operations})
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    args = SimpleNamespace(query='query', limit=7, json=True, debug=False)
    if resource_name in ('datasets', 'samples'):
        args.project_id = 'project-one'

    module._execute_search(args)

    assert json.loads(capsys.readouterr().out) == results


@pytest.mark.parametrize(('module', 'resource_name'), [
    (dataset_cli, 'datasets'),
    (sample_cli, 'samples'),
    (project_cli, 'projects'),
    (instrument_cli, 'instruments'),
])
def test_metadata_search_json_returns_nested_raw_values(
        monkeypatch, capsys, module, resource_name):
    results = [{
        'unique_id': MFID,
        'scientific_metadata': {'nested': {'value': 1}},
    }]
    operations = SimpleNamespace(search_metadata=MagicMock(return_value=results))
    client = SimpleNamespace(**{resource_name: operations})
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    module._execute_search_metadata(SimpleNamespace(
        query='query',
        limit=7,
        json=True,
        debug=False,
    ))

    assert json.loads(capsys.readouterr().out) == results


def test_user_search_and_list_json_return_raw_arrays(monkeypatch, capsys):
    users = [{'unique_id': MFID, 'username': 'service-user'}]
    operations = SimpleNamespace(
        search=MagicMock(return_value=users),
        list=MagicMock(return_value=users),
    )
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: SimpleNamespace(users=operations),
    )

    user_cli._execute_search(SimpleNamespace(query='query', json=True, debug=False))
    assert json.loads(capsys.readouterr().out) == users

    user_cli._execute_list(SimpleNamespace(
        limit=10,
        username=None,
        json=True,
        debug=False,
    ))
    assert json.loads(capsys.readouterr().out) == users


def test_service_account_get_and_list_json_use_object_and_array_shapes(
        monkeypatch, capsys):
    account = {'unique_id': MFID, 'username': 'service-user'}
    operations = SimpleNamespace(list=MagicMock(return_value=[account]))
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: SimpleNamespace(service_accounts=operations),
    )
    monkeypatch.setattr(
        service_account_cli,
        '_resolve_sa_ref',
        lambda args: (MFID, None, False),
    )
    monkeypatch.setattr(
        service_account_cli,
        '_resolve_sa',
        lambda client, **kwargs: account,
    )

    service_account_cli._execute_get(SimpleNamespace(json=True, debug=False))
    assert json.loads(capsys.readouterr().out) == account

    service_account_cli._execute_list(SimpleNamespace(
        limit=10,
        json=True,
        debug=False,
    ))
    assert json.loads(capsys.readouterr().out) == [account]


@pytest.mark.parametrize(('module', 'resource_name'), [
    (dataset_cli, 'datasets'),
    (sample_cli, 'samples'),
    (project_cli, 'projects'),
    (instrument_cli, 'instruments'),
    (user_cli, 'users'),
])
def test_short_search_query_emits_structured_json_error(
        capsys, module, resource_name):
    args = SimpleNamespace(query='ab', json=True, debug=False)

    with pytest.raises(SystemExit) as raised:
        module._execute_search(args)

    assert raised.value.code == 1
    error = json.loads(capsys.readouterr().err)['error']
    assert error['message'] == f'Failed while searching {resource_name}.'
    assert error['details'][0]['message'] == 'Search term must be at least 3 characters.'


def test_service_account_missing_reference_emits_structured_json_error(capsys):
    args = SimpleNamespace(
        sa=None,
        unique_id=None,
        username=None,
        json=True,
        debug=False,
    )

    with pytest.raises(SystemExit) as raised:
        service_account_cli._execute_get(args)

    assert raised.value.code == 1
    error = json.loads(capsys.readouterr().err)['error']
    assert error['details'][0]['message'].startswith(
        'Provide a service account identifier')
