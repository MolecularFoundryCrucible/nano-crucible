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
