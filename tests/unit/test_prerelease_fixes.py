"""Unit coverage for fixes found in the 4.0.0 pre-release review."""

import argparse
import os
import warnings
from unittest.mock import MagicMock

import pytest
import requests

from crucible.cli import dataset as dataset_cli
from crucible.cli import service_account as sa_cli
from crucible.cli.helpers import resolve_usernames
from crucible.client import CrucibleClient
from crucible.resources.users import UserOperations

ORCID = '0000-0001-6402-3752'


def test_resolve_usernames_uses_the_current_resolve_keyword():
    client = MagicMock()
    client.users = UserOperations(MagicMock())
    client.users._paginate = MagicMock(return_value=[{'unique_id': ORCID, 'username': 'roncofaber'}])

    assert resolve_usernames(client, [ORCID, None]) == {ORCID: 'roncofaber'}
    assert client.users._paginate.call_args.args[1]['unique_id'] == [ORCID]


def _parse(module, *argv):
    parser = argparse.ArgumentParser()
    module.register_subcommand(parser.add_subparsers(dest='resource'))
    return parser.parse_args(list(argv))


def test_dataset_update_set_public_is_removed(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    args = _parse(dataset_cli, 'dataset', 'update', '0' * 26, '--set', 'public=true')

    with pytest.raises(SystemExit) as stop:
        args.func(args)

    assert stop.value.code == 2
    client.datasets.set_public.assert_not_called()
    client.datasets.update.assert_not_called()


def test_sa_create_keeps_the_given_mfid_when_prompting_for_the_username(monkeypatch):
    client = MagicMock()
    client.authorization = None
    client.service_accounts.create.return_value = {'unique_id': '0' * 26, 'username': 'robot'}
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_username', lambda *a, **k: 'robot')
    asked = MagicMock(return_value='1' * 26)
    monkeypatch.setattr('crucible.cli.helpers.prompt_optional', asked)
    monkeypatch.setattr(sa_cli, '_show_sa', lambda *a, **k: None)
    args = _parse(sa_cli, 'sa', 'create', '--unique-id', '0' * 26)

    args.func(args)

    asked.assert_not_called()
    client.service_accounts.create.assert_called_once_with(username='robot', unique_id='0' * 26)


def test_api_deprecation_warning_points_at_the_caller(monkeypatch):
    response = MagicMock(ok=True, status_code=200, headers={'Deprecation': '@1700000000'})
    response.json.return_value = {'unique_id': '0' * 26}
    monkeypatch.setattr(requests.Session, 'request', lambda self, *a, **k: response)
    client = CrucibleClient('https://crucible.example.test/api/v3', 'key')

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        client.datasets.get('0' * 26)

    assert [w.category for w in caught] == [DeprecationWarning]
    assert os.path.abspath(caught[0].filename) == os.path.abspath(__file__)


def test_shell_completion_leaves_out_removed_commands():
    from crucible.cli import _drop_removed_commands
    from crucible.cli import account, upload

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    upload.register_subcommand(subparsers)
    account.register_subcommand(subparsers)

    _drop_removed_commands(parser)

    assert 'upload' not in subparsers.choices
    account_subs = next(a for a in subparsers.choices['account']._actions
                        if isinstance(a, argparse._SubParsersAction))
    assert 'api-key' not in account_subs.choices
    assert 'keys' in account_subs.choices
