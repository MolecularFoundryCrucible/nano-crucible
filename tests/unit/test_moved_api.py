"""A deployment that moves its API to a new path, answering the old one with a redirect."""

import http.server
import json
import logging
import threading
import time

import pytest
import requests

from crucible import client as client_module
from crucible.auth import oauth, session as auth_session, store as auth_store
from crucible.auth.errors import SignInError
from crucible.auth.tokens import TokenSet
from crucible.client import CrucibleClient

_REAL_SEND = requests.adapters.HTTPAdapter.send


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 308
    issuer_path = '/new'

    def _answer(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        if self.path.startswith('/old/'):
            self.send_response(self.status)
            self.send_header('Location', '/new/' + self.path[len('/old/'):])
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        host = f'http://{self.headers["Host"]}'
        if self.path.endswith(oauth.WELL_KNOWN_PATH):
            issuer = host + self.issuer_path
            out = {'issuer': issuer, 'authorization_endpoint': f'{issuer}/oauth/authorize',
                   'token_endpoint': f'{issuer}/oauth/token'}
        else:
            out = {'method': self.command, 'path': self.path, 'body': body.decode(),
                   'authorization': self.headers.get('Authorization')}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PATCH = _answer

    def log_message(self, *args):
        pass


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_store, '_config_dir', lambda: tmp_path)
    monkeypatch.setattr(oauth, '_metadata_cache', {})
    monkeypatch.setattr(client_module, '_moves_seen', set())

    def loopback_only(self, request, *args, **kwargs):
        if not request.url.startswith('http://127.0.0.1:'):
            raise RuntimeError(f"unit tests must not reach the network: {request.url}")
        return _REAL_SEND(self, request, *args, **kwargs)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', loopback_only)
    handler = type('Handler', (_Handler,), {})
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}', handler
    httpd.shutdown()


def test_calls_follow_the_move_with_method_body_and_credential(server, caplog):
    host, _ = server
    client = CrucibleClient(api_url=f'{host}/old', api_key='the-key')

    with caplog.at_level(logging.WARNING, logger='crucible.client'):
        posted = client._request('POST', '/datasets', json={'a': 1})
        client._request('PATCH', '/datasets/x', json={'b': 2})

    assert posted == {'method': 'POST', 'path': '/new/datasets', 'body': '{"a": 1}',
                      'authorization': 'Bearer the-key'}
    moves = [r.getMessage() for r in caplog.records if 'has moved' in r.getMessage()]
    assert moves == [f'The Crucible API at {host}/old has moved to {host}/new. Update the address: '
                     f'crucible config set api_url {host}/new']


def test_a_temporary_redirect_is_followed_without_a_warning(server, caplog):
    host, handler = server
    handler.status = 307
    client = CrucibleClient(api_url=f'{host}/old', api_key='the-key')

    with caplog.at_level(logging.WARNING, logger='crucible.client'):
        assert client._request('GET', '/datasets')['path'] == '/new/datasets'

    assert not [r for r in caplog.records if 'has moved' in r.getMessage()]


def test_discovery_accepts_the_issuer_the_api_moved_to(server):
    host, _ = server

    assert oauth.discover(f'{host}/old')['issuer'] == f'{host}/new'


def test_discovery_still_refuses_an_issuer_it_was_not_redirected_to(server):
    host, handler = server
    handler.issuer_path = '/elsewhere'

    with pytest.raises(SignInError, match='refusing'):
        oauth.discover(f'{host}/old')


def _redirected(urls, issuer):
    hops = []
    for url in urls[:-1]:
        hop = requests.Response()
        hop.status_code, hop.url = 308, url
        hops.append(hop)
    final = requests.Response()
    final.status_code, final.url, final.history = 200, urls[-1], hops
    final._content = json.dumps({'issuer': issuer}).encode()
    return final


@pytest.mark.parametrize('final', [
    'https://other.example.test/api/v4',
    'http://crucible.example.test/api/v4',
])
def test_discovery_refuses_a_move_to_another_host_or_scheme(monkeypatch, final):
    monkeypatch.setattr(oauth, '_metadata_cache', {})
    old = 'https://crucible.example.test/api/v3'
    monkeypatch.setattr(requests, 'get', lambda url, **kwargs: _redirected(
        [url, final + oauth.WELL_KNOWN_PATH], final))

    with pytest.raises(SignInError, match='refusing'):
        oauth.discover(old)


def _stored(api_url):
    tokens = TokenSet(api_url, 'chba_a', 'chbr_r', time.time() + 900, user_unique_id='u1')
    store = auth_store.FileStore()
    store.save(tokens)
    auth_store.remember(tokens, store)
    return store


def test_a_stored_sign_in_moves_with_the_api(server):
    host, _ = server
    store = _stored(f'{host}/old')

    assert auth_session.carry_sign_in(f'{host}/old', f'{host}/new') is True

    assert auth_store.signed_in(f'{host}/old') is None
    assert auth_store.signed_in(f'{host}/new')['user_unique_id'] == 'u1'
    assert store.load(f'{host}/new').refresh_token == 'chbr_r'


def test_a_stored_sign_in_stays_when_the_new_address_is_not_where_the_api_moved(server):
    host, _ = server
    _stored(f'{host}/old')

    assert auth_session.carry_sign_in(f'{host}/old', f'{host}/other') is False
    assert auth_store.signed_in(f'{host}/old') is not None
