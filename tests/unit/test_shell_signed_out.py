"""The shell opens signed out when no credential works, and connects after login."""

from unittest.mock import MagicMock

import pytest
import requests

from crucible.errors import NotSignedInError


@pytest.fixture
def shell(monkeypatch):
    from crucible.cli import shell as shell_pkg
    from crucible.config import config

    monkeypatch.setattr(config, 'reload', lambda: None)
    monkeypatch.setattr(shell_pkg.CrucibleShell, '_start_background_checks', lambda self: None)
    return shell_pkg.CrucibleShell(MagicMock())


def _client_factory(monkeypatch, *outcomes):
    """get_client returns or raises each outcome in turn."""
    import crucible.config as cfg_pkg
    queue = list(outcomes)

    def get_client():
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(cfg_pkg, 'get_client', get_client)


def _refused():
    response = requests.Response()
    response.status_code = 401
    return requests.HTTPError('401', response=response)


def test_no_credential_opens_signed_out(shell, monkeypatch):
    from crucible.config import config
    _client_factory(monkeypatch, NotSignedInError('none'))
    assert shell._verify_connection() is None
    assert shell.client is None
    assert shell._signed_out_reason == f'Not signed in to {config.api_url}.'


def test_refused_credential_opens_signed_out(shell, monkeypatch):
    _client_factory(monkeypatch, MagicMock(whoami=MagicMock(side_effect=_refused())))
    assert shell._verify_connection() is None
    assert 'refused the credential (401)' in shell._signed_out_reason


def test_unreachable_api_still_exits(shell, monkeypatch):
    _client_factory(monkeypatch, MagicMock(whoami=MagicMock(side_effect=requests.ConnectionError())))
    with pytest.raises(SystemExit):
        shell._verify_connection()


def _feed(monkeypatch, lines):
    import prompt_toolkit
    session = MagicMock()
    session.prompt.side_effect = list(lines) + [EOFError()]
    monkeypatch.setattr(prompt_toolkit, 'PromptSession', lambda **kwargs: session)


def test_signed_out_prompt_runs_only_sign_in_commands(shell, monkeypatch, capsys):
    shell._signed_out_reason = 'Not signed in to https://example.test.'
    ran = []
    monkeypatch.setattr(shell, '_run_signed_out_command', ran.append)
    _feed(monkeypatch, ['dataset list', 'help', 'status'])
    assert shell._signed_out_prompt(None) is None
    assert ran == ['status']
    out = capsys.readouterr().out
    assert 'Not signed in to https://example.test.' in out
    assert 'runs only login, config, status, help, exit' in out


def test_login_connects_and_hands_over(shell, monkeypatch):
    shell._signed_out_reason = 'Not signed in.'
    info = {'user_info': {'first_name': 'Ada'}}
    client = MagicMock(whoami=MagicMock(return_value=info))
    _client_factory(monkeypatch, NotSignedInError('none'), client)
    monkeypatch.setattr(shell, '_run_signed_out_command', lambda line: None)
    _feed(monkeypatch, ['config show', 'login'])
    assert shell._signed_out_prompt(None) == info
    assert shell.client is client


def test_config_without_a_credential_stays_quiet(shell, monkeypatch, capsys):
    _client_factory(monkeypatch, NotSignedInError('none'))
    assert shell._connect_if_credential() is None
    assert 'Connecting' not in capsys.readouterr().out
