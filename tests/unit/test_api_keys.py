import argparse
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import account as account_cli
from crucible.cli.user import _execute_revoke_keys, _register_list_keys
from crucible.resources.account import AccountOperations
from crucible.resources.base import ListResult
from crucible.resources.users import UserOperations

USER_MFID = '0tkvpezyz1zzf00076nahf85j4'
KEY = {'id': 12, 'name': 'laptop', 'last4': 'a1b2', 'status': 'active',
       'created_at': '2026-11-01T10:00:00Z', 'last_used_at': None,
       'expires_at': '2027-11-01T10:00:00Z', 'revoked_at': None, 'older_routes': False}


def make_account(response=None):
    operations = AccountOperations(MagicMock())
    operations._request = MagicMock(return_value=response if response is not None else {})
    return operations


def make_users(response=None):
    operations = UserOperations(MagicMock())
    operations._request = MagicMock(return_value=response if response is not None else {})
    return operations


def test_create_api_key_is_not_retried_or_logged_and_returns_the_key_once():
    operations = make_account({**KEY, 'api_key': 'crucible_secret'})

    created = operations.create_api_key(
        'laptop', expires_at=datetime(2027, 6, 30, tzinfo=timezone.utc))

    operations._request.assert_called_once_with(
        'post', '/account/apikeys',
        json={'name': 'laptop', 'expires_at': '2027-06-30T00:00:00+00:00'},
        retry=False, log_body=False)
    assert created['api_key'] == 'crucible_secret'
    assert created['last4'] == 'a1b2'


def test_create_api_key_omits_expiry_by_default():
    operations = make_account({**KEY, 'api_key': 'crucible_secret'})

    operations.create_api_key('laptop')

    assert operations._request.call_args.kwargs['json'] == {'name': 'laptop'}


def test_list_api_keys_pages_within_the_route_cap():
    operations = make_account()
    operations._request.side_effect = [
        {'total': 3, 'limit': 200, 'offset': None, 'items': [KEY, KEY], 'next_cursor': 'c1'},
        {'total': 3, 'limit': 200, 'offset': None, 'items': [KEY], 'next_cursor': None},
    ]

    keys = operations.list_api_keys(state='inactive', limit=None)

    first, second = operations._request.call_args_list
    assert first.args == ('get', '/account/apikeys')
    assert first.kwargs['params'] == {'state': 'inactive', 'limit': 200}
    assert second.kwargs['params'] == {'state': 'inactive', 'limit': 200, 'cursor': 'c1'}
    assert isinstance(keys, ListResult)
    assert [key['id'] for key in keys] == [12, 12, 12]
    assert keys.has_more is False


def test_list_api_keys_rejects_unknown_state():
    with pytest.raises(ValueError, match='state'):
        make_account().list_api_keys(state='revoked')


def test_rename_and_revoke_use_the_per_key_routes():
    operations = make_account({**KEY, 'name': 'cluster'})

    renamed = operations.rename_api_key(12, 'cluster')
    operations.revoke_api_key(12)

    assert operations._request.call_args_list[0].args == ('patch', '/account/apikeys/12')
    assert operations._request.call_args_list[0].kwargs == {'json': {'name': 'cluster'}}
    assert operations._request.call_args_list[1].args == ('delete', '/account/apikeys/12')
    assert renamed['name'] == 'cluster'




def test_admin_key_routes_are_elevated():
    operations = make_users({'total': 1, 'limit': 50, 'offset': None,
                             'items': [KEY], 'next_cursor': None})

    keys = operations.list_api_keys(USER_MFID, limit=50)
    operations.revoke_api_key(USER_MFID, 12)

    listing, revoke = operations._request.call_args_list
    assert listing.args == ('get', f'/users/{USER_MFID}/apikeys')
    assert listing.kwargs['privilege_mode'] == 'elevated'
    assert revoke.args == ('delete', f'/users/{USER_MFID}/apikeys/12')
    assert revoke.kwargs == {'privilege_mode': 'elevated'}
    assert keys[0]['id'] == 12


def test_revoke_all_keys_is_still_supported(recwarn):
    operations = make_users()

    operations.revoke_api_keys(USER_MFID)

    operations._request.assert_called_once_with(
        'delete', f'/users/{USER_MFID}/apikey', privilege_mode='elevated')
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def parse_account(*argv):
    parser = argparse.ArgumentParser()
    account_cli.register_subcommand(parser.add_subparsers())
    return parser.parse_args(['account', *argv])


def test_keys_create_reads_a_naive_expiry_as_utc(monkeypatch, capsys):
    client = MagicMock()
    client.account.create_api_key.return_value = {**KEY, 'api_key': 'crucible_secret'}
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse_account('keys', 'create', 'laptop', '--expires', '2027-06-30')
    args.func(args)

    client.account.create_api_key.assert_called_once_with(
        'laptop', expires_at=datetime(2027, 6, 30, tzinfo=timezone.utc))
    out = capsys.readouterr().out
    assert 'crucible_secret' in out
    assert 'not shown again' in out


def test_keys_create_rejects_a_bad_expiry(monkeypatch):
    monkeypatch.setattr('crucible.config.get_client', lambda: MagicMock())
    args = parse_account('keys', 'create', 'laptop', '--expires', 'next week')

    with pytest.raises(SystemExit):
        args.func(args)


def test_keys_list_shows_the_last_four_characters_only(monkeypatch, capsys):
    client = MagicMock()
    client.account.list_api_keys.return_value = ListResult([KEY], total=1)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse_account('keys', 'list')
    args.func(args)

    assert client.account.list_api_keys.call_args.kwargs['state'] == 'active'
    out = capsys.readouterr().out
    assert '...a1b2' in out
    assert 'laptop' in out


def test_keys_revoke_with_yes_revokes_one_key(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse_account('keys', 'revoke', '12', '--yes')
    args.func(args)

    client.account.revoke_api_key.assert_called_once_with(12)


def test_user_revoke_keys_with_key_revokes_only_that_key(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.resolve_user_id', lambda c, ref: USER_MFID)

    _execute_revoke_keys(SimpleNamespace(user='fabrice', key_id=12, yes=True, debug=False))

    client.users.revoke_api_key.assert_called_once_with(USER_MFID, 12)
    client.users.revoke_api_keys.assert_not_called()


def test_user_list_keys_parses_inactive():
    parser = argparse.ArgumentParser()
    _register_list_keys(parser.add_subparsers())

    args = parser.parse_args(['list-keys', 'fabrice', '--inactive'])

    assert args.inactive is True
    assert args.user == 'fabrice'


def test_hub_url_defaults_to_the_foundry_hub_and_drops_a_trailing_slash(monkeypatch):
    from crucible.config import config
    monkeypatch.delitem(config._data, 'hub_url', raising=False)
    assert config.hub_url == 'https://crucible.lbl.gov/hub'

    monkeypatch.setitem(config._data, 'hub_url', 'https://staging.example.org/hub/')
    assert config.hub_url == 'https://staging.example.org/hub'


def test_hub_session_hint_names_the_configured_hub(monkeypatch):
    import json
    import requests
    from crucible.cli.helpers import format_cli_error
    from crucible.config import config
    monkeypatch.setitem(config._data, 'hub_url', 'https://staging.example.org/hub')
    response = requests.models.Response()
    response.status_code = 403
    response.reason = 'Forbidden'
    response._content = json.dumps({'detail': {
        'code': 'hub_session_required',
        'message': 'Creating an API key needs a Hub session, not an API key'}}).encode()
    error = requests.exceptions.HTTPError('403 Forbidden', response=response)

    rendered = json.dumps(format_cli_error('creating an API key', error))

    assert 'https://staging.example.org/hub' in rendered
