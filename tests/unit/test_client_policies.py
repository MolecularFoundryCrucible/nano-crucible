"""Unit coverage for retry policy, deprecation headers, and the API key commands."""

import argparse
import json
import warnings
from unittest.mock import MagicMock

import pytest
import requests

from crucible import client as client_module
from crucible.cli import account as account_cli
from crucible.client import CrucibleClient

API = 'https://crucible.example.test/api/v3'


@pytest.fixture
def client():
    return CrucibleClient(API, 'key')


def _retry(session):
    return session.get_adapter(API).max_retries


def test_repeatable_requests_retry_gateway_errors_and_rate_limits(client):
    retry = _retry(client._session)

    assert set(retry.status_forcelist) == {429, 502, 503, 504}
    assert retry.total == 3 and not retry.allowed_methods


def test_unrepeatable_requests_retry_only_what_never_reached_the_server(client):
    retry = _retry(client._no_retry_session)

    assert set(retry.status_forcelist) == {429}
    assert (retry.connect, retry.read, retry.other) == (3, 0, 0)
    assert client._no_retry_session.headers['Connection'] == 'close'


@pytest.mark.parametrize('method, headers, retry, expected', [
    ('get', None, True, '_session'),
    ('delete', None, True, '_session'),
    ('post', None, True, '_no_retry_session'),
    ('patch', None, True, '_no_retry_session'),
    ('post', {'Idempotency-Key': 'k'}, True, '_session'),
    ('get', None, False, '_no_retry_session'),
])
def test_requests_pick_the_session_their_method_allows(client, monkeypatch, method, headers,
                                                       retry, expected):
    used = []
    response = requests.Response()
    response.status_code = 200
    response._content = b'{}'
    for name in ('_session', '_no_retry_session'):
        monkeypatch.setattr(getattr(client, name), 'request',
                            lambda *a, _name=name, **k: used.append(_name) or response)

    client._request(method, '/datasets', headers=headers, retry=retry)

    assert used == [expected]


def _deprecated_response(headers):
    response = requests.Response()
    response.status_code = 200
    response._content = b'{}'
    response.headers.update(headers)
    return response


@pytest.mark.parametrize('endpoint, route', [
    ('/datasets/0tkn2knjast3h0008nyq9zps2c/samples', '/datasets/{id}/samples'),
    ('/users/0000-0001-6402-3752/apikey', '/users/{id}/apikey'),
    ('/join_requests/42?x=1', '/join_requests/{id}'),
])
def test_deprecation_warnings_name_the_route_without_ids(endpoint, route):
    client_module._deprecations_seen.clear()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        client_module._warn_if_deprecated('get', endpoint, _deprecated_response({'Deprecation': 'true'}))

    assert len(caught) == 1
    message = str(caught[0].message)
    assert f'GET {route} as deprecated' in message and 'since' not in message


def test_deprecation_warning_carries_date_sunset_and_link_once_per_route():
    client_module._deprecations_seen.clear()
    headers = {'Deprecation': '@1700000000', 'Sunset': 'Wed, 01 Jul 2027 00:00:00 GMT',
               'Link': '<https://docs.example/old>; rel="deprecation"; type="text/html"'}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        for _ in range(2):
            client_module._warn_if_deprecated('get', '/old', _deprecated_response(headers))

    assert len(caught) == 1
    message = str(caught[0].message)
    assert '(since 2023-11-14)' in message
    assert 'removed after Wed, 01 Jul 2027' in message
    assert 'see https://docs.example/old' in message


def test_responses_without_deprecation_do_not_warn():
    client_module._deprecations_seen.clear()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        client_module._warn_if_deprecated('get', '/datasets', _deprecated_response({}))
    assert caught == []


def _keys(*argv):
    parser = argparse.ArgumentParser()
    account_cli.register_subcommand(parser.add_subparsers(dest='resource'))
    args = parser.parse_args(['account', 'keys', *argv])
    args.debug = False
    return args


def test_keys_rename(monkeypatch, capsys):
    client = MagicMock()
    client.account.rename_api_key.return_value = {'id': 12, 'name': 'laptop'}
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = _keys('rename', '12', 'laptop')
    args.func(args)

    client.account.rename_api_key.assert_called_once_with(12, 'laptop')
    assert "Renamed key 12 to 'laptop'" in capsys.readouterr().out


@pytest.mark.parametrize('confirmed', [False, True])
def test_keys_revoke_asks_first(monkeypatch, confirmed):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: confirmed)

    args = _keys('revoke', '12')
    args.func(args)

    assert client.account.revoke_api_key.called is confirmed


def test_keys_revoke_with_y_skips_the_prompt(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', MagicMock(side_effect=AssertionError))

    args = _keys('revoke', '12', '-y')
    args.func(args)

    client.account.revoke_api_key.assert_called_once_with(12)


def test_keys_create_json_prints_the_key_once(monkeypatch, capsys):
    created = {'id': 3, 'name': 'ci', 'api_key': 'chk_secret', 'expires_at': '2027-01-01T00:00:00Z'}
    client = MagicMock()
    client.account.create_api_key.return_value = created
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = _keys('create', 'ci', '--json')
    args.func(args)

    assert json.loads(capsys.readouterr().out) == created
    client.account.create_api_key.assert_called_once_with('ci', expires_at=None)


def test_upload_progress_ignores_reports_after_a_file_finished():
    import io
    from crucible.cli.helpers import UploadProgress

    stream = io.StringIO()
    stream.isatty = lambda: True
    progress = UploadProgress(stream=stream, interval=0)

    progress('a.dat', 10, 10)
    shown = stream.getvalue()
    progress('a.dat', 4, 10)

    assert stream.getvalue() == shown
