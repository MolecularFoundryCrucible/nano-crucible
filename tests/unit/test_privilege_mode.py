"""Unit coverage for the Crucible-Privilege-Mode header."""

from unittest.mock import MagicMock, patch

import pytest

from crucible.client import CrucibleClient


@pytest.fixture
def make_client(monkeypatch):
    from crucible.config import config

    monkeypatch.setitem(config._data, 'api_url', 'https://example.test/api/v3')
    monkeypatch.setitem(config._data, 'api_key', 'test-key')
    config._data.pop('privilege_mode', None)

    def build(**kwargs):
        client = CrucibleClient(**kwargs)
        client._session = MagicMock()
        client._session.request.return_value = MagicMock(
            ok=True, status_code=200, content=b'{}', text='{}')
        client._session.request.return_value.json.return_value = {}
        return client

    return build


def sent_headers(client):
    return client._session.request.call_args.kwargs.get('headers')


def test_no_header_is_sent_by_default(make_client):
    client = make_client()

    client._request('get', '/datasets')

    assert client.privilege_mode is None
    assert sent_headers(client) is None


def test_client_level_mode_is_sent_on_every_request(make_client):
    client = make_client(privilege_mode='elevated')

    client._request('get', '/datasets')

    assert sent_headers(client)['Crucible-Privilege-Mode'] == 'elevated'


def test_per_call_override_wins(make_client):
    client = make_client(privilege_mode='normal')

    client._request('get', '/datasets', privilege_mode='elevated')

    assert sent_headers(client)['Crucible-Privilege-Mode'] == 'elevated'


def test_existing_headers_are_preserved(make_client):
    client = make_client(privilege_mode='elevated')

    client._request('get', '/datasets', headers={'X-Test': '1'})

    headers = sent_headers(client)
    assert headers['X-Test'] == '1'
    assert headers['Crucible-Privilege-Mode'] == 'elevated'


def test_invalid_mode_is_rejected_at_construction(make_client):
    with pytest.raises(ValueError):
        make_client(privilege_mode='superuser')


def test_mode_is_read_from_config(make_client, monkeypatch):
    from crucible.config import config

    monkeypatch.setitem(config._data, 'privilege_mode', 'elevated')
    client = make_client()

    assert client.privilege_mode == 'elevated'


def test_elevated_flag_sets_the_config_mode(monkeypatch):
    from crucible.cli import main
    from crucible.config import config

    config._data.pop('privilege_mode', None)
    seen = {}

    def execute(args):
        seen['mode'] = config.privilege_mode

    with patch('crucible.cli.dataset._execute_list', side_effect=execute):
        monkeypatch.setattr('sys.argv', ['crucible', '--elevated', 'dataset', 'list'])
        main()

    assert seen['mode'] == 'elevated'
    config._data.pop('privilege_mode', None)


def test_without_the_flag_no_mode_is_set(monkeypatch):
    from crucible.cli import main
    from crucible.config import config

    config._data.pop('privilege_mode', None)
    seen = {}

    def execute(args):
        seen['mode'] = config.privilege_mode

    with patch('crucible.cli.dataset._execute_list', side_effect=execute):
        monkeypatch.setattr('sys.argv', ['crucible', 'dataset', 'list'])
        main()

    assert seen['mode'] is None


def test_config_sourced_elevation_is_announced(monkeypatch, capsys):
    from crucible.cli import main
    from crucible.config import config

    monkeypatch.setitem(config._data, 'privilege_mode', 'elevated')
    monkeypatch.setitem(config._sources, 'privilege_mode', 'config file')

    with patch('crucible.cli.dataset._execute_list'):
        monkeypatch.setattr('sys.argv', ['crucible', 'dataset', 'list'])
        main()

    assert 'Elevated privilege is active from config file' in capsys.readouterr().err


def test_explicit_flag_is_not_announced(monkeypatch, capsys):
    from crucible.cli import main
    from crucible.config import config

    config._data.pop('privilege_mode', None)

    with patch('crucible.cli.dataset._execute_list'):
        monkeypatch.setattr('sys.argv', ['crucible', '--elevated', 'dataset', 'list'])
        main()

    assert 'Elevated privilege is active' not in capsys.readouterr().err
    config._data.pop('privilege_mode', None)


def test_shell_toggle_sets_and_clears_the_config_mode():
    from crucible.cli.shell import _elevated_now, _set_elevated

    _set_elevated(True)
    assert _elevated_now() is True

    _set_elevated(False)
    assert _elevated_now() is False


def test_shell_toolbar_shows_the_elevated_badge():
    from crucible.cli import shell

    instance = shell.CrucibleShell.__new__(shell.CrucibleShell)
    instance.state = {'elevated': True, 'debug': False, 'project': None,
                      'user_label': 'me', 'api_label': 'v3'}

    markup = instance._toolbar().value

    assert 'ELEVATED' in markup
