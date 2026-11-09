import base64
import hashlib
import json
import os
import stat
import threading
import time
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.auth import oauth, session as auth_session, store as auth_store, stepup
from crucible.auth.errors import SignInError, SignInRequired
from crucible.auth.loopback import LoopbackListener, browser_available
from crucible.auth.tokens import TokenSet

API = 'https://crucible.example.test/api/v3'
METADATA = {
    'issuer': API,
    'authorization_endpoint': f'{API}/oauth/authorize',
    'token_endpoint': f'{API}/oauth/token',
    'revocation_endpoint': f'{API}/oauth/revoke',
    'device_authorization_endpoint': f'{API}/oauth/device_authorization',
}
USER = '0tkvpezyz1zzf00076nahf85j4'


def reply(status, body):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    return response


def token_body(access='chba_a', refresh='chbr_r', expires_in=900, auth_time=None):
    return {'access_token': access, 'token_type': 'Bearer', 'expires_in': expires_in,
            'refresh_token': refresh, 'auth_time': auth_time or int(time.time())}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_store, '_config_dir', lambda: tmp_path)
    monkeypatch.setattr(oauth, '_metadata_cache', {})
    stepup.install(None)
    yield
    stepup.install(None)


def test_pkce_challenge_is_s256_of_the_verifier():
    verifier, challenge = oauth.new_pkce()

    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert challenge == expected
    assert 43 <= len(verifier) <= 128


def test_discovery_refuses_another_issuer(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda *a, **k: reply(200, {**METADATA, 'issuer': 'https://evil.test'}))

    with pytest.raises(SignInError, match='refusing'):
        oauth.discover(API)


def test_discovery_accepts_a_trailing_slash(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda *a, **k: reply(200, {**METADATA, 'issuer': API + '/'}))

    assert oauth.discover(API + '/')['token_endpoint'] == METADATA['token_endpoint']


def test_authorization_url_carries_pkce_and_the_pinned_account():
    url = oauth.authorization_url(METADATA, 'http://127.0.0.1:5000/callback', 's' * 32, 'c' * 43,
                                  max_age=0, required_user=USER)

    assert url.startswith(METADATA['authorization_endpoint'] + '?')
    for part in ('client_id=nano-crucible', 'code_challenge_method=S256', 'max_age=0',
                 f'required_user={USER}', 'redirect_uri=http%3A%2F%2F127.0.0.1%3A5000%2Fcallback'):
        assert part in url


def browse(url):
    def run():
        time.sleep(0.05)
        with urllib.request.urlopen(url) as page:
            page.read()
    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_loopback_listener_returns_the_code_for_its_own_state():
    listener = LoopbackListener()
    assert listener.redirect_uri.startswith(('http://127.0.0.1:', 'http://[::1]:'))
    thread = browse(f'{listener.redirect_uri}?code=abc&state={listener.state}&iss={API}')

    assert listener.wait(API, timeout=5) == 'abc'
    thread.join()


@pytest.mark.parametrize('query, message', [
    ('code=abc&state=other&iss=' + API, 'another request'),
    ('code=abc&state={state}&iss=https://evil.test', 'another server'),
    ('error=access_denied&state={state}&iss=' + API, 'cancelled'),
    ('error=login_required&state={state}&iss=' + API, 'different account'),
])
def test_loopback_listener_refuses_bad_redirects(query, message):
    listener = LoopbackListener()
    thread = browse(f'{listener.redirect_uri}?{query.format(state=listener.state)}')

    with pytest.raises(SignInError, match=message):
        listener.wait(API, timeout=5)
    thread.join()


def test_browser_is_unavailable_over_ssh(monkeypatch):
    monkeypatch.setenv('SSH_CONNECTION', '1.2.3.4 22 5.6.7.8 22')
    assert browser_available() is False


def test_browser_is_unavailable_on_headless_linux(monkeypatch):
    for name in ('SSH_CONNECTION', 'SSH_TTY', 'SSH_CLIENT', 'JUPYTERHUB_API_URL', 'JUPYTERHUB_USER',
                 'DISPLAY', 'WAYLAND_DISPLAY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr('sys.platform', 'linux')
    assert browser_available() is False
    monkeypatch.setenv('DISPLAY', ':0')
    assert browser_available() is True


def fake_server(monkeypatch, account=USER, token_replies=None):
    posts = []
    replies = list(token_replies or [reply(200, token_body())])

    def post(url, data=None, **kwargs):
        posts.append((url, dict(data)))
        if url == METADATA['revocation_endpoint']:
            return reply(200, {})
        return replies.pop(0)

    def get(url, **kwargs):
        if url.endswith('/.well-known/oauth-authorization-server'):
            return reply(200, METADATA)
        assert kwargs['headers']['Authorization'].startswith('Bearer chba_')
        return reply(200, {'user_unique_id': account})

    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', get)
    return posts


def follow_redirect(url):
    from urllib.parse import parse_qs, urlsplit
    query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
    browse(f"{query['redirect_uri']}?code=the-code&state={query['state']}&iss={API}")
    return True


def test_browser_sign_in_exchanges_the_code_with_the_verifier(monkeypatch):
    posts = fake_server(monkeypatch)
    monkeypatch.setattr('webbrowser.open', follow_redirect)

    tokens = auth_session.sign_in(API, 'browser', required_user=USER, notify=lambda *a: None)

    (url, fields), = posts
    assert url == METADATA['token_endpoint']
    assert fields['grant_type'] == 'authorization_code'
    assert fields['client_id'] == 'nano-crucible'
    assert fields['code'] == 'the-code'
    assert fields['redirect_uri'].endswith('/callback')
    assert 'client_secret' not in fields
    assert tokens.user_unique_id == USER
    assert tokens.grant == 'authorization_code'


def test_sign_in_as_another_account_is_revoked_and_refused(monkeypatch):
    posts = fake_server(monkeypatch, account='someone-else')
    monkeypatch.setattr('webbrowser.open', follow_redirect)

    with pytest.raises(SignInError, match='this needs'):
        auth_session.sign_in(API, 'browser', required_user=USER, notify=lambda *a: None)

    assert posts[-1][0] == METADATA['revocation_endpoint']
    assert posts[-1][1]['token'] == 'chbr_r'


def test_device_flow_waits_slows_down_and_succeeds(monkeypatch):
    fake_server(monkeypatch, token_replies=[
        reply(400, {'error': 'authorization_pending'}),
        reply(400, {'error': 'slow_down'}),
        reply(200, token_body()),
    ])
    waits = []
    device = {'device_code': 'dc', 'user_code': 'WDJB-MJHT', 'interval': 5, 'expires_in': 600,
              'verification_uri': f'{API}/oauth/device'}

    tokens = oauth.poll_device(API, METADATA, device, sleep=waits.append, clock=lambda: 0)

    assert waits == [5, 5, 10]
    assert tokens.grant == 'device_code'


def test_device_flow_stops_when_denied(monkeypatch):
    fake_server(monkeypatch, token_replies=[reply(400, {'error': 'access_denied'})])
    device = {'device_code': 'dc', 'interval': 1, 'expires_in': 600}

    with pytest.raises(SignInError, match='denied'):
        oauth.poll_device(API, METADATA, device, sleep=lambda s: None, clock=lambda: 0)


def stored(tmp_path, access='chba_old', refresh='chbr_old', expires_at=None):
    tokens = TokenSet(API, access, refresh, expires_at if expires_at is not None else time.time() - 1,
                      auth_time=int(time.time()), user_unique_id=USER)
    store = auth_store.FileStore(tmp_path)
    auth_session.save_sign_in(tokens, store)
    return tokens, store


def test_file_store_is_private(tmp_path):
    stored(tmp_path)

    mode = stat.S_IMODE(os.stat(tmp_path / 'credentials.json').st_mode)
    assert mode == 0o600


def test_expired_access_token_is_renewed_once_and_stored(tmp_path, monkeypatch):
    posts = fake_server(monkeypatch, token_replies=[reply(200, token_body('chba_new', 'chbr_new'))])
    tokens, store = stored(tmp_path)
    credential = auth_session.SessionCredential(tokens, store)

    assert credential.bearer() == 'chba_new'
    assert credential.bearer() == 'chba_new'

    assert [fields['refresh_token'] for _, fields in posts] == ['chbr_old']
    assert store.load(API).refresh_token == 'chbr_new'
    assert store.load(API).user_unique_id == USER


def test_a_second_process_uses_the_rotated_tokens_instead_of_replaying(tmp_path, monkeypatch):
    posts = fake_server(monkeypatch, token_replies=[reply(200, token_body('chba_new', 'chbr_new'))])
    tokens, store = stored(tmp_path)
    first = auth_session.SessionCredential(TokenSet.from_dict(tokens.to_dict()), store)
    second = auth_session.SessionCredential(TokenSet.from_dict(tokens.to_dict()), auth_store.FileStore(tmp_path))

    assert first.bearer() == 'chba_new'
    assert second.bearer() == 'chba_new'

    assert len(posts) == 1


def test_an_ended_session_is_forgotten(tmp_path, monkeypatch):
    fake_server(monkeypatch, token_replies=[reply(400, {'error': 'invalid_grant'})])
    tokens, store = stored(tmp_path)

    with pytest.raises(SignInRequired, match='crucible login'):
        auth_session.SessionCredential(tokens, store).bearer()

    assert store.load(API) is None
    assert auth_store.signed_in(API) is None


def test_sign_out_revokes_and_deletes(tmp_path, monkeypatch):
    posts = fake_server(monkeypatch)
    _, store = stored(tmp_path)

    assert auth_session.sign_out(API, store) is True

    assert posts == [(METADATA['revocation_endpoint'], {'client_id': 'nano-crucible', 'token': 'chbr_old'})]
    assert store.load(API) is None
    assert auth_session.sign_out(API, store) is False


def test_the_index_never_holds_tokens(tmp_path):
    stored(tmp_path)

    index = (tmp_path / 'signins.json').read_text()
    assert 'chba_' not in index and 'chbr_' not in index
    assert json.loads(index)[API] == {'store': 'file', 'user_unique_id': USER}


def test_keyring_is_skipped_without_a_dbus_session_on_linux(monkeypatch):
    monkeypatch.setattr('sys.platform', 'linux')
    monkeypatch.delenv('DBUS_SESSION_BUS_ADDRESS', raising=False)

    assert auth_store.open_store('auto').name == 'file'
    with pytest.raises(ValueError, match='keyring'):
        auth_store.open_store('keyring')


def test_keyring_store_round_trips_through_the_backend(tmp_path):
    pytest.importorskip('keyring')
    backend = MagicMock()
    saved = {}
    backend.set_password.side_effect = lambda service, user, value: saved.__setitem__((service, user), value)
    backend.get_password.side_effect = lambda service, user: saved.get((service, user))
    store = auth_store.KeyringStore(backend, tmp_path)
    tokens = TokenSet(API, 'chba_a', 'chbr_r', time.time() + 900)

    store.save(tokens)

    assert ('nano-crucible', API) in saved
    assert store.load(API).refresh_token == 'chbr_r'


@pytest.fixture
def fake_config(monkeypatch):
    from crucible.config import config
    monkeypatch.setattr(config, '_data', dict(config._data))
    monkeypatch.setattr(config, '_sources', dict(config._sources))
    config._data.pop('api_key', None)
    config._sources.pop('api_key', None)
    return config


def test_precedence_env_key_then_sign_in_then_config_key(tmp_path, fake_config):
    from crucible.client import _resolve_credential
    stored(tmp_path, expires_at=time.time() + 900)
    fake_config._data['api_key'] = 'file-key'
    fake_config._sources['api_key'] = 'config file'

    assert _resolve_credential(fake_config, API, 'arg-key').source == 'argument'
    assert _resolve_credential(fake_config, API, None).source == 'sign-in'
    assert _resolve_credential(fake_config, 'https://other.test/api/v3', None).source == 'config file'

    fake_config._sources['api_key'] = 'environment'
    assert _resolve_credential(fake_config, API, None).source == 'CRUCIBLE_API_KEY'


def test_no_key_and_no_sign_in_says_how_to_sign_in(fake_config):
    from crucible.client import _resolve_credential

    with pytest.raises(ValueError, match='crucible login'):
        _resolve_credential(fake_config, API, None)


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


def refusal(code, status=403):
    return reply(status, {'detail': {'code': code, 'message': 'needs a recent sign-in'}})


def test_step_up_retries_once_with_a_fresh_browser_session(monkeypatch):
    client, sent = api_client(monkeypatch, [refusal('hub_session_required'), reply(201, {'id': 1})])
    fresh = auth_session.SessionCredential(
        TokenSet(API, 'chba_fresh', 'chbr_f', time.time() + 900, auth_time=int(time.time())),
        auth_store.TokenStore())
    handler = MagicMock(return_value=fresh)
    stepup.install(handler)

    assert client._request('post', '/account/apikeys', json={'name': 'x'}) == {'id': 1}

    handler.assert_called_once_with(client, 'hub_session_required')
    assert sent[0] is None
    prepared = sent[1](requests.Request('POST', API).prepare())
    assert prepared.headers['Authorization'] == 'Bearer chba_fresh'


def test_no_step_up_without_a_handler_or_off_the_main_thread(monkeypatch):
    client, _ = api_client(monkeypatch, [refusal('hub_session_required')])
    with pytest.raises(requests.HTTPError):
        client._request('post', '/account/apikeys', json={'name': 'x'})

    client, _ = api_client(monkeypatch, [refusal('hub_session_required')])
    handler = MagicMock()
    stepup.install(handler)
    errors = []

    def worker():
        try:
            client._request('post', '/account/apikeys', json={'name': 'x'})
        except requests.HTTPError as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    handler.assert_not_called()
    assert errors


def test_a_refused_session_token_is_renewed_and_retried(monkeypatch, tmp_path):
    client, sent = api_client(monkeypatch, [reply(401, {'detail': 'Invalid token'}), reply(200, {'ok': True})])
    client._credential = SimpleNamespace(kind='session', renew=MagicMock(return_value=True), source='sign-in')

    assert client._request('get', '/account') == {'ok': True}
    client._credential.renew.assert_called_once()


def test_cli_hint_for_a_device_session_refusal():
    from crucible.cli.helpers import format_cli_error
    error = requests.HTTPError('403', response=refusal('browser_sign_in_required'))

    rendered = json.dumps(format_cli_error('creating an API key', error))

    assert 'computer with a browser' in rendered


def test_login_command_stores_the_session_and_warns_about_an_env_key(monkeypatch, capsys, fake_config):
    from crucible.cli import login as login_cli
    tokens = TokenSet(API, 'chba_a', 'chbr_r', time.time() + 900, user_unique_id=USER)
    monkeypatch.setattr(auth_session, 'sign_in', lambda *a, **k: tokens)
    monkeypatch.setattr(fake_config, 'reload', lambda: None)
    fake_config._data['api_url'] = API
    fake_config._data['api_key'] = 'env-key'
    fake_config._sources['api_key'] = 'environment'
    warnings = []
    monkeypatch.setattr('crucible.cli.helpers.show_warning', warnings.append)

    login_cli.execute_login(SimpleNamespace(method='auto', open_browser=True, json=False))

    assert f'Signed in as {USER}' in capsys.readouterr().out
    assert auth_store.signed_in(API)['user_unique_id'] == USER
    assert any('CRUCIBLE_API_KEY' in warning for warning in warnings)


def test_logout_command_without_a_sign_in(monkeypatch, capsys, fake_config):
    from crucible.cli import login as login_cli
    fake_config._data['api_url'] = API

    login_cli.execute_logout(SimpleNamespace(json=False))

    assert 'Not signed in' in capsys.readouterr().out


def test_whoami_names_the_credential():
    from crucible.cli.whoami import credential_label
    client = SimpleNamespace(credential_source='sign-in', _credential=SimpleNamespace(
        store=SimpleNamespace(name='keyring'), tokens=SimpleNamespace(grant='device_code')))

    assert credential_label(client) == 'Crucible sign-in (device code, OS keyring)'
    assert credential_label(SimpleNamespace(credential_source='config file')) == 'API key (config file)'


def test_step_up_handler_needs_a_local_browser(monkeypatch):
    from crucible.cli import stepup as cli_stepup
    monkeypatch.setattr('crucible.auth.loopback.browser_available', lambda: False)

    assert cli_stepup._handle(SimpleNamespace(), 'hub_session_required') is None


def test_the_constructor_prefers_a_stored_sign_in_over_the_config_file_key(tmp_path, fake_config):
    from crucible.client import CrucibleClient
    stored(tmp_path, expires_at=time.time() + 900)
    fake_config._data['api_key'] = 'file-key'
    fake_config._sources['api_key'] = 'config file'

    assert CrucibleClient(API).credential_source == 'sign-in'
    assert CrucibleClient('https://other.test/api/v3').credential_source == 'config file'
    assert CrucibleClient(API, 'arg-key').credential_source == 'argument'


def test_a_sign_in_alone_is_enough_to_build_a_client(tmp_path, fake_config):
    from crucible.client import CrucibleClient
    stored(tmp_path, expires_at=time.time() + 900)

    client = CrucibleClient(API)

    assert client.credential_source == 'sign-in'
    assert client.api_key is None

