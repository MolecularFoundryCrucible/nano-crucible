"""Names renamed in 4.0.0 keep working with a DeprecationWarning that names the new one."""

import argparse
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset as dataset_cli
from crucible.cli import sample as sample_cli
from crucible.client import CrucibleClient


@pytest.fixture
def client():
    instance = CrucibleClient('https://crucible.example.test/api/v3', 'key')
    instance._request = MagicMock(return_value=[])
    return instance


@pytest.mark.parametrize('namespace, old, new', [
    ('datasets', 'get_keywords', 'list_keywords'),
    ('projects', 'get_users', 'list_users'),
    ('instruments', 'get_users', 'list_users'),
    ('users', 'get_projects', 'list_projects'),
])
def test_old_method_names_warn_and_delegate(client, namespace, old, new):
    operations = getattr(client, namespace)
    target = MagicMock(return_value='result')
    setattr(operations, new, target)

    with pytest.warns(DeprecationWarning, match=f'{old}.*{new}'):
        assert getattr(operations, old)('ref', limit=5) == 'result'
    target.assert_called_once_with('ref', limit=5)


@pytest.mark.parametrize('namespace, method, old, new, extra', [
    ('files', 'get', 'file_id', 'file_mfid', {}),
    ('deletions', 'request', 'resource_id', 'resource_mfid', {}),
    ('service_accounts', 'rotate_key', 'unique_id', 'service_account_ref', {}),
    ('instruments', 'update', 'unique_id', 'instrument_ref', {'location': 'B67'}),
    ('instruments', 'bind_service_account', 'sa_unique_id', 'service_account_ref',
     {'instrument_ref': 'xrd-one'}),
    ('users', 'set_platform_role', 'user_unique_id', 'user_ref', {'platform_role': 'contributor'}),
    ('projects', 'update_user_role', 'user_unique_id', 'user_ref',
     {'project_id': 'demo', 'role': 'viewer'}),
])
def test_old_keyword_names_warn_and_map(client, namespace, method, old, new, extra):
    operations = getattr(client, namespace)
    with pytest.warns(DeprecationWarning, match=f"'{old}'.*'{new}'"):
        try:
            getattr(operations, method)(**{old: '0' * 26}, **extra)
        except Exception as error:
            assert not isinstance(error, TypeError), error


def test_old_and_new_keyword_together_is_an_error(client):
    with pytest.raises(TypeError, match='file_mfid'):
        client.files.get(file_id='a', file_mfid='b')


def _subparsers(module):
    parser = argparse.ArgumentParser()
    module.register_subcommand(parser.add_subparsers(dest='resource'))
    resource = next(iter(parser._subparsers._group_actions[0].choices.values()))
    return parser, next(a for a in resource._actions if isinstance(a, argparse._SubParsersAction))


@pytest.mark.parametrize('module, resource, old, new, argv, call', [
    (dataset_cli, 'dataset', 'add-sample', 'link-sample', ['D' * 26, '-s', 'S' * 26],
     ('datasets', 'link_sample')),
    (dataset_cli, 'dataset', 'remove-sample', 'unlink-sample', ['D' * 26, '-s', 'S' * 26],
     ('datasets', 'unlink_sample')),
    (dataset_cli, 'dataset', 'remove-child', 'unlink', ['P' * 26, '-c', 'C' * 26],
     ('datasets', 'unlink')),
    (sample_cli, 'sample', 'add-dataset', 'link-dataset', ['S' * 26, '-d', 'D' * 26],
     ('samples', 'link_dataset')),
    (sample_cli, 'sample', 'remove-dataset', 'unlink-dataset', ['S' * 26, '-d', 'D' * 26],
     ('samples', 'unlink_dataset')),
    (sample_cli, 'sample', 'remove-child', 'unlink', ['P' * 26, '-c', 'C' * 26],
     ('samples', 'unlink')),
])
def test_old_cli_names_warn_run_and_stay_hidden(monkeypatch, capsys, module, resource, old, new,
                                                 argv, call):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser, subparsers = _subparsers(module)

    visible = {action.dest for action in subparsers._choices_actions}
    assert new in visible and old not in visible

    args = parser.parse_args([resource, old, *argv])
    args.func(args)

    assert f"use 'crucible {resource} {new}" in capsys.readouterr().err
    getattr(getattr(client, call[0]), call[1]).assert_called_once()


@pytest.mark.parametrize('module, resource', [(dataset_cli, 'dataset'), (sample_cli, 'sample')])
def test_unlink_mirrors_link(monkeypatch, module, resource):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser, _ = _subparsers(module)

    args = parser.parse_args([resource, 'unlink', '-p', 'P' * 26, '-c', 'C' * 26])
    args.func(args)

    getattr(client, f'{resource}s').unlink.assert_called_once_with('P' * 26, 'C' * 26)


@pytest.mark.parametrize('namespace', ['datasets', 'samples'])
def test_graph_wrappers_warn_and_delegate_to_graphs_get(client, namespace):
    client.graphs.get = MagicMock(return_value={'nodes': []})

    with pytest.warns(DeprecationWarning, match=r'graphs\.get'):
        assert getattr(client, namespace).graph('0' * 26, recursive=True) == {'nodes': []}
    client.graphs.get.assert_called_once_with('0' * 26, recursive=True, as_networkx=False)
