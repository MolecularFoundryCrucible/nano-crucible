"""Unit coverage for sign-in renewal, re-login, precedence fallbacks, login/logout, and step-up."""

import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.auth import oauth, session as auth_session, store as auth_store, stepup
from crucible.auth.errors import SignInRequired
from crucible.auth.tokens import TokenSet
from crucible.cli import stepup as cli_stepup

API = 'https://crucible.example.test/api/v3'
USER = '0tkvpezyz1zzf00076nahf85j4'


def tokens(access='chba_a', refresh='chbr_r', expires_in=900, auth_time=None, user=USER):
    return TokenSet(API, access, refresh, time.time() + expires_in,
                    auth_time=auth_time if auth_time is not None else int(time.time()),
                    user_unique_id=user)


def reply(status, body):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    return response


# ── re-login and renewal ──────────────────────────────────────────────────────

def test_signing_in_again_revokes_the_previous_session(tmp_path, monkeypatch):
    store = auth_store.FileStore(tmp_path)
    revoked = []
    monkeypatch.setattr(oauth, 'revoke', revoked.append)
    first, second = tokens(refresh='chbr_1'), tokens(access='chba_2', refresh='chbr_2')

    auth_session.save_sign_in(first, store)
    auth_session.save_sign_in(second, store)
    auth_session.save_sign_in(second, store)

    assert [t.refresh_token for t in revoked] == ['chbr_1']
    assert store.load(API).refresh_token == 'chbr_2'


def test_forced_renewal_refreshes_a_token_that_still_looks_fresh(tmp_path, monkeypatch):
    store = auth_store.FileStore(tmp_path)
    store.save(tokens(access='chba_old'))
    monkeypatch.setattr(oauth, 'refresh', lambda current: tokens(access='chba_new', refresh='chbr_new'))
    credential = auth_session.SessionCredential(store.load(API), store)

    assert credential.renew() is True
    assert credential.bearer() == 'chba_new'
    assert store.load(API).access_token == 'chba_new'


def test_renewal_adopts_tokens_another_process_already_rotated(tmp_path, monkeypatch):
    store = auth_store.FileStore(tmp_path)
    credential = auth_session.SessionCredential(tokens(access='chba_old', expires_in=0), store)
    store.save(tokens(access='chba_rotated'))
    refresh = MagicMock()
    monkeypatch.setattr(oauth, 'refresh', refresh)

    assert credential.renew() is True
    assert credential.bearer() == 'chba_rotated'
    refresh.assert_not_called()


def test_renewal_after_signing_out_elsewhere_asks_to_sign_in(tmp_path):
    store = auth_store.FileStore(tmp_path)
    credential = auth_session.SessionCredential(tokens(expires_in=0), store)

    with pytest.raises(SignInRequired, match='crucible login'):
        credential.bearer()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX record locks')
def test_the_store_lock_excludes_another_process(tmp_path):
    holder = subprocess.Popen(
        [sys.executable, '-c',
         'import sys, time\n'
         'from crucible.auth.store import FileStore\n'
         'with FileStore(__import__("pathlib").Path(sys.argv[1])).lock():\n'
         '    print("ready", flush=True)\n'
         '    time.sleep(0.8)\n',
         str(tmp_path)],
        stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'ready'
        started = time.monotonic()
        with auth_store.FileStore(tmp_path).lock():
            waited = time.monotonic() - started
    finally:
        holder.wait(20)
    assert waited >= 0.3


# ── requests and credentials ──────────────────────────────────────────────────

def api_client(monkeypatch, responses):
    from crucible.client import CrucibleClient
    client = CrucibleClient(API, 'the-key')
    sent = []

    def request(method, url, **kwargs):
        sent.append(kwargs.get('auth'))
        return responses.pop(0)

    monkeypatch.setattr(client._session, 'request', request)
    monkeypatch.setattr(client._no_retry_session, 'request', request)
    return client, sent


def test_a_401_with_an_error_code_is_not_renewed(monkeypatch):
    client, sent = api_client(monkeypatch, [reply(401, {'detail': {'code': 'key_revoked'}})])
    client._credential = SimpleNamespace(kind='session', renew=MagicMock(), source='sign-in')

    with pytest.raises(requests.HTTPError):
        client._request('get', '/account')
    client._credential.renew.assert_not_called()
    assert len(sent) == 1


def test_an_unreadable_sign_in_falls_back_to_the_config_file_key(monkeypatch):
    from crucible.client import _resolve_credential
    from crucible.config import config
    monkeypatch.setattr(config, '_data', {'api_key': 'file-key'})
    monkeypatch.setattr(config, '_sources', {'api_key': 'config file'})
    monkeypatch.setattr('crucible.auth.store.signed_in', lambda url: {'store': 'keyring'})

    def broken(entry):
        raise RuntimeError('keyring locked')
    monkeypatch.setattr('crucible.auth.store.store_for', broken)

    credential = _resolve_credential(config, API, None)

    assert (credential.kind, credential.source) == ('api_key', 'config file')


def test_login_stores_the_session_and_switches_the_client(monkeypatch):
    from crucible.client import CrucibleClient
    client = CrucibleClient(API, 'the-key')
    signed = tokens(access='chba_new')
    monkeypatch.setattr(auth_session, 'sign_in', lambda *a, **k: signed)
    monkeypatch.setattr(oauth, 'revoke', MagicMock())
    monkeypatch.setattr(client, 'refresh_profile', MagicMock())

    result = client.login(store='memory')

    assert result == {'user_unique_id': USER, 'store': 'memory', 'grant': 'authorization_code'}
    assert client.credential_source == 'this session' and client.api_key is None
    assert client._credential.bearer() == 'chba_new'
    client.refresh_profile.assert_called_once()


def test_logout_without_and_with_a_stored_sign_in(tmp_path, monkeypatch):
    from crucible.client import CrucibleClient
    client = CrucibleClient(API, 'the-key')
    assert client.logout() is False

    revoked = []
    monkeypatch.setattr(oauth, 'revoke', revoked.append)
    store = auth_store.FileStore()
    auth_session.save_sign_in(tokens(), store)

    assert client.logout() is True
    assert store.load(API) is None and auth_store.signed_in(API) is None
    assert [t.refresh_token for t in revoked] == ['chbr_r']


# ── step-up ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('stdin, stdout, as_json, installed', [
    (True, True, False, True),
    (False, True, False, False),
    (True, False, False, False),
    (True, True, True, False),
])
def test_the_prompt_is_only_installed_for_interactive_human_output(monkeypatch, stdin, stdout,
                                                                  as_json, installed):
    monkeypatch.setattr('sys.stdin', SimpleNamespace(isatty=lambda: stdin))
    monkeypatch.setattr('sys.stdout', SimpleNamespace(isatty=lambda: stdout))

    cli_stepup.install_for(SimpleNamespace(json=as_json))

    assert (stepup.handler() is cli_stepup._handle) is installed
    stepup.install(None)


def refusal(code='hub_session_required'):
    return reply(403, {'detail': {'code': code, 'message': 'needs a recent sign-in'}})


def test_a_recent_step_up_is_reused_without_asking_again(monkeypatch):
    client, _ = api_client(monkeypatch, [refusal(), reply(200, {'n': 1}), refusal(), reply(200, {'n': 2})])
    fresh = auth_session.SessionCredential(tokens(access='chba_fresh'), auth_store.TokenStore())
    handler = MagicMock(return_value=fresh)
    stepup.install(handler)

    assert client._request('post', '/account/apikeys', json={}) == {'n': 1}
    assert client._request('post', '/account/apikeys', json={}) == {'n': 2}
    handler.assert_called_once()


def test_a_stale_step_up_asks_again(monkeypatch):
    client, _ = api_client(monkeypatch, [refusal(), reply(200, {})])
    client._step_up_credential = auth_session.SessionCredential(
        tokens(auth_time=int(time.time()) - stepup.RECENT_SECONDS - 60), auth_store.TokenStore())
    handler = MagicMock(return_value=auth_session.SessionCredential(tokens(), auth_store.TokenStore()))
    stepup.install(handler)

    client._request('post', '/account/apikeys', json={})

    handler.assert_called_once()


def test_a_declined_step_up_keeps_the_refusal(monkeypatch):
    client, sent = api_client(monkeypatch, [refusal()])
    stepup.install(MagicMock(return_value=None))

    with pytest.raises(requests.HTTPError) as error:
        client._request('post', '/account/apikeys', json={})
    assert error.value.response.status_code == 403
    assert len(sent) == 1


def _handler_client(credential):
    client = SimpleNamespace(api_url=API, _credential=credential,
                             whoami=MagicMock(return_value={'user_unique_id': USER}))
    return client


def test_handler_declined_returns_nothing(monkeypatch):
    monkeypatch.setattr('crucible.auth.loopback.browser_available', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: False)
    sign_in = MagicMock()
    monkeypatch.setattr(auth_session, 'sign_in', sign_in)

    assert cli_stepup._handle(_handler_client(SimpleNamespace(kind='api_key')), 'hub_session_required') is None
    sign_in.assert_not_called()


def test_handler_for_a_stored_session_replaces_it(tmp_path, monkeypatch):
    store = auth_store.FileStore(tmp_path)
    old = tokens(access='chba_old', refresh='chbr_old', auth_time=1)
    credential = auth_session.SessionCredential(old, store)
    client = _handler_client(credential)
    fresh = tokens(access='chba_fresh', refresh='chbr_fresh')
    monkeypatch.setattr('crucible.auth.loopback.browser_available', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: True)
    calls = {}

    def sign_in(api_url, method, **kwargs):
        calls.update(kwargs, method=method)
        return fresh
    monkeypatch.setattr(auth_session, 'sign_in', sign_in)
    monkeypatch.setattr(oauth, 'revoke', MagicMock())

    result = cli_stepup._handle(client, 'hub_session_required')

    assert calls['method'] == 'browser' and calls['max_age'] == 0
    assert calls['required_user'] == USER
    assert client._credential is result and result.tokens.access_token == 'chba_fresh'
    assert store.load(API).access_token == 'chba_fresh'
    client.whoami.assert_not_called()


def test_handler_for_an_api_key_keeps_the_key_and_returns_a_one_off_session(monkeypatch):
    key = SimpleNamespace(kind='api_key')
    client = _handler_client(key)
    monkeypatch.setattr('crucible.auth.loopback.browser_available', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: True)
    seen = {}
    monkeypatch.setattr(auth_session, 'sign_in',
                        lambda api_url, method, **kwargs: seen.update(kwargs) or tokens(access='chba_once'))

    result = cli_stepup._handle(client, 'insufficient_user_authentication')

    assert seen['required_user'] == USER
    assert client._credential is key
    assert result.store.name == 'memory' and result.tokens.access_token == 'chba_once'
