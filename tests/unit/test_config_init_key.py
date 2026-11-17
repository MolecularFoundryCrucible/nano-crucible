"""config init creates an API key after a browser sign-in."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.auth.session import TokenSet
from crucible.cli import config as config_cli
from crucible.cli import helpers

API = 'https://crucible.example/api/v3'


@pytest.fixture
def signed_in(monkeypatch):
    """A browser is available, the person agrees, and sign-in returns tokens."""
    import crucible.auth.loopback as loopback
    import crucible.auth.oauth as oauth
    import crucible.auth.session as session
    tokens = TokenSet(API, 'chba_a', 'chbr_r', time.time() + 900)
    monkeypatch.setattr(loopback, 'browser_available', lambda: True)
    monkeypatch.setattr(helpers, 'prompt_confirm', lambda message, **kwargs: True)
    monkeypatch.setattr(helpers, 'prompt_optional', lambda label, **kwargs: 'laptop')
    sign_in = MagicMock(return_value=tokens)
    monkeypatch.setattr(session, 'sign_in', sign_in)
    revoke = MagicMock()
    monkeypatch.setattr(oauth, 'revoke', revoke)
    return SimpleNamespace(tokens=tokens, sign_in=sign_in, revoke=revoke)


def _answer(monkeypatch, status, body):
    """The API answers every request with this status and JSON body; returns the sent requests."""
    sent = []

    def request(self, method, url, **kwargs):
        prepared = requests.Request(method, url, json=kwargs.get('json'),
                                    headers=kwargs.get('headers')).prepare()
        self.auth(prepared)
        sent.append(prepared)
        response = requests.Response()
        response.status_code = status
        response._content = __import__('json').dumps(body).encode()
        response.headers['Content-Type'] = 'application/json'
        response.url = url
        return response
    monkeypatch.setattr(requests.Session, 'request', request)
    return sent


def test_creates_key_with_the_fresh_session_and_ends_it(signed_in, monkeypatch):
    sent = _answer(monkeypatch, 201, {'id': 7, 'name': 'laptop', 'api_key': 'crucible_new',
                                      'expires_at': '2027-11-17T00:00:00Z'})
    assert config_cli._offer_browser_key(API) == 'crucible_new'
    assert signed_in.sign_in.call_args.args[:2] == (API, 'browser')
    assert [(r.method, r.url) for r in sent] == [('POST', f'{API}/account/apikeys')]
    assert sent[0].headers['Authorization'] == 'Bearer chba_a'
    signed_in.revoke.assert_called_once_with(signed_in.tokens)


def test_refused_creation_falls_back_to_pasting(signed_in, monkeypatch, capsys):
    _answer(monkeypatch, 403, {'detail': {'code': 'browser_sign_in_required', 'message': 'no'}})
    assert config_cli._offer_browser_key(API) is None
    assert 'Could not create the key' in capsys.readouterr().err
    signed_in.revoke.assert_called_once()


def test_no_browser_skips_sign_in(signed_in, monkeypatch, capsys):
    import crucible.auth.loopback as loopback
    monkeypatch.setattr(loopback, 'browser_available', lambda: False)
    assert config_cli._offer_browser_key(API) is None
    signed_in.sign_in.assert_not_called()
    assert 'needs a browser on this computer' in capsys.readouterr().out


def test_declining_skips_sign_in(signed_in, monkeypatch):
    monkeypatch.setattr(helpers, 'prompt_confirm', lambda message, **kwargs: False)
    assert config_cli._offer_browser_key(API) is None
    signed_in.sign_in.assert_not_called()


def test_init_saves_the_created_key_without_asking_for_one(monkeypatch, tmp_path):
    from crucible.config import config
    import crucible.config as cfg_pkg
    monkeypatch.setattr(type(config), 'config_file_path', property(lambda self: tmp_path / 'none.ini'))
    monkeypatch.setattr(helpers, 'prompt_optional', lambda *args, **kwargs: None)
    monkeypatch.setattr(helpers, 'prompt_secret',
                        lambda *args, **kwargs: pytest.fail('secret prompt should not run'))
    monkeypatch.setattr(config_cli, '_offer_browser_key', lambda api_url: 'crucible_new')
    create = MagicMock(return_value=tmp_path / 'config.ini')
    monkeypatch.setattr(cfg_pkg, 'create_config_file', create)
    config_cli.cmd_init(SimpleNamespace())
    assert create.call_args.kwargs['api_key'] == 'crucible_new'
