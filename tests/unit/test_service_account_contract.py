"""Unit coverage for service-account creation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.resources.service_accounts import ServiceAccountOperations
from crucible.cli.service_account import _execute_create


def make_ops():
    operations = ServiceAccountOperations(MagicMock())
    operations._request = MagicMock(return_value={})
    return operations


def test_create_normalizes_username_before_request():
    operations = make_ops()

    operations.create('  Smoke-Test  ')

    operations._request.assert_called_once_with(
        'post', '/service_accounts', json={'username': 'smoke-test'})


@pytest.mark.parametrize('username', ['ab', '1smoke-test', 'smoke__test', 'a' * 25])
def test_create_rejects_invalid_username(username):
    operations = make_ops()

    with pytest.raises(ValueError, match='Username must be 3 to 24 characters'):
        operations.create(username)

    operations._request.assert_not_called()


def test_create_rejects_invalid_explicit_mfid():
    operations = make_ops()

    with pytest.raises(ValueError, match='MFID must be exactly 26'):
        operations.create('smoke-test', unique_id='not-an-mfid')

    operations._request.assert_not_called()


def test_interactive_create_uses_validated_username(monkeypatch):
    client = SimpleNamespace(service_accounts=SimpleNamespace())
    client.service_accounts.create = MagicMock(return_value={
        'unique_id': '0tkvpezyz1zzf00076nahf85j4',
        'username': 'smoke-test',
        'api_key': 'test-key',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_username', lambda prompt='Username: ': 'smoke-test')
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    _execute_create(SimpleNamespace(username=None, unique_id=None, debug=False))

    client.service_accounts.create.assert_called_once_with(
        username='smoke-test', unique_id=None)


ADMIN_RECORD = {
    'unique_id': '0td7evvtg5wb90005k1j97ak94',
    'username': 'robot',
    'first_name': 'Robot',
    'last_name': 'Account',
    'platform_role': 'contributor',
    'api_key_status': {'created_at': '2026-01-01', 'expires_at': '2027-01-01',
                       'valid': True},
}


def test_get_admin_reads_the_service_account_endpoint():
    operations = make_ops()
    operations._request.return_value = ADMIN_RECORD

    result = operations.get_admin('0td7evvtg5wb90005k1j97ak94')

    operations._request.assert_called_once_with(
        'get', '/service_accounts/0td7evvtg5wb90005k1j97ak94')
    assert result['platform_role'] == 'contributor'
    assert result['api_key_status']['valid'] is True


def test_get_admin_rejects_a_non_mfid():
    operations = make_ops()

    with pytest.raises(ValueError):
        operations.get_admin('robot')

    operations._request.assert_not_called()


def test_list_admin_forwards_the_search_string():
    operations = make_ops()
    operations._request.return_value = {'total': 1, 'items': [ADMIN_RECORD]}

    result = operations.list_admin(q='rob', limit=10)

    assert operations._request.call_args.kwargs['params']['q'] == 'rob'
    assert result[0]['username'] == 'robot'


def test_list_admin_omits_the_search_string_by_default():
    operations = make_ops()
    operations._request.return_value = {'total': 0, 'items': []}

    operations.list_admin()

    assert 'q' not in operations._request.call_args.kwargs['params']


def test_set_platform_role_patches_the_service_account():
    operations = make_ops()
    operations._request.return_value = ADMIN_RECORD

    operations.set_platform_role('0td7evvtg5wb90005k1j97ak94', 'contributor')

    operations._request.assert_called_once_with(
        'patch', '/service_accounts/0td7evvtg5wb90005k1j97ak94',
        json={'platform_role': 'contributor'})


def test_set_platform_role_rejects_an_unknown_role():
    operations = make_ops()

    with pytest.raises(ValueError, match='platform_role must be one of'):
        operations.set_platform_role('0td7evvtg5wb90005k1j97ak94', 'superuser')

    operations._request.assert_not_called()


def test_admin_parse_preserves_unknown_server_fields():
    operations = make_ops()
    operations._request.return_value = {**ADMIN_RECORD, 'future_field': 'kept'}

    result = operations.get_admin('0td7evvtg5wb90005k1j97ak94')

    assert result['future_field'] == 'kept'
