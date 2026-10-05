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
    assert 'Crucible-Privilege-Mode' not in (sent_headers(client) or {})


@pytest.mark.parametrize('mode, can_elevate, expected', [
    (None, True, True),
    (None, False, False),
    ('normal', True, False),
    ('elevated', True, True),
])
def test_is_elevated_reflects_the_server_default(make_client, mode, can_elevate,
                                                 expected):
    client = make_client(privilege_mode=mode)
    client._authorization = {'can_elevate': can_elevate}

    assert client.is_elevated is expected


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
    from crucible.cli.shell import _set_elevated
    from crucible.config import config

    _set_elevated(True)
    assert config.privilege_mode == 'elevated'

    _set_elevated(False)
    assert config.privilege_mode == 'normal'
    config._data.pop('privilege_mode', None)


def test_shell_toolbar_shows_the_elevated_badge():
    from crucible.cli import shell

    instance = shell.CrucibleShell.__new__(shell.CrucibleShell)
    instance.state = {'elevated': True, 'debug': False, 'project': None,
                      'user_label': 'me', 'api_label': 'v3'}

    markup = instance._toolbar().value

    assert 'ELEVATED' in markup


def test_shell_toggle_updates_its_long_lived_client():
    from crucible.cli import shell
    from crucible.config import config

    config._data.pop('privilege_mode', None)
    instance = shell.CrucibleShell.__new__(shell.CrucibleShell)
    instance.state = {'elevated': False}
    instance.client = MagicMock(privilege_mode=None)

    instance._apply_elevated(True)
    assert instance.client.privilege_mode == 'elevated'
    assert config.privilege_mode == 'elevated'

    instance._apply_elevated(False)
    assert instance.client.privilege_mode == 'normal'
    assert config.privilege_mode == 'normal'


def test_shell_toggle_tolerates_a_client_that_is_not_built_yet():
    from crucible.cli import shell
    from crucible.config import config

    config._data.pop('privilege_mode', None)
    instance = shell.CrucibleShell.__new__(shell.CrucibleShell)
    instance.state = {'elevated': False}
    instance.client = None

    instance._apply_elevated(True)
    assert instance.state['elevated'] is True

    instance._apply_elevated(False)


def make_admin_client(make_client, resource, response, can_elevate=True):
    """Build a client whose named resource records its _request calls.

    Resources bind the client's _request at construction, so the stub has to
    replace the resource's own reference rather than the client's.
    """
    client = make_client()
    client._authorization = {'can_elevate': can_elevate}
    client._capabilities = {}
    request = MagicMock(return_value=response)
    getattr(client, resource)._request = request
    return client, request


def test_service_account_admin_always_elevates(make_client):
    client, request = make_admin_client(
        make_client, 'service_accounts', {'unique_id': 'x'}, can_elevate=False)

    client.service_accounts.set_platform_role(
        '0td7evvtg5wb90005k1j97ak94', 'contributor')

    assert request.call_args.kwargs['privilege_mode'] == 'elevated'


def test_deletion_review_elevates_only_for_eligible_callers(make_client):
    for can_elevate, expected in ((True, 'elevated'), (False, None)):
        client, request = make_admin_client(
            make_client, 'deletions', {'id': 1}, can_elevate=can_elevate)

        client.deletions.get(1)

        assert request.call_args.kwargs.get('privilege_mode') == expected


def test_reviewable_scope_elevates_but_accessible_does_not(make_client):
    for scope, expected in (('reviewable', 'elevated'), ('accessible', None)):
        client, request = make_admin_client(
            make_client, 'deletions', {'total': 0, 'items': []})

        client.deletions.list(scope=scope)

        assert request.call_args.kwargs.get('privilege_mode') == expected


def test_capabilities_are_fetched_in_normal_mode_and_cached(make_client):
    client = make_client()
    profile = {'authorization': {'can_elevate': True},
               'capabilities': {'can_create_project': True}}
    with patch.object(client.account, 'profile',
                      return_value=profile) as fetch:
        assert client.can_elevate is True
        assert client.capabilities['can_create_project'] is True
        assert client.authorization['can_elevate'] is True

    fetch.assert_called_once_with(privilege_mode='normal')


def test_unreadable_profile_degrades_to_no_authority(make_client):
    client = make_client()
    with patch.object(client.account, 'profile', side_effect=RuntimeError):
        assert client.can_elevate is False
        assert client.capabilities == {}


def test_require_capability_blocks_a_disallowed_action(capsys):
    from crucible.cli.helpers import require_capability

    client = MagicMock(capabilities={'can_create_project': False})

    with pytest.raises(SystemExit):
        require_capability(client, 'can_create_project', 'create projects')

    assert 'not permitted to create projects' in capsys.readouterr().err


def test_require_capability_allows_a_permitted_action():
    from crucible.cli.helpers import require_capability

    client = MagicMock(capabilities={'can_create_project': True})

    require_capability(client, 'can_create_project', 'create projects')


def test_require_capability_defers_to_the_api_when_unknown():
    from crucible.cli.helpers import require_capability

    require_capability(MagicMock(capabilities={}), 'can_create_project', 'x')
