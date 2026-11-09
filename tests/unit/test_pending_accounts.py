"""Unit coverage for accounts waiting for approval."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli.user import (
    _execute_approve,
    _execute_list,
    _execute_reject,
    _register_list,
    _register_reject,
    _show_user,
)
from crucible.resources.users import UserOperations

WAITING = {
    'unique_id': 'MFU0001', 'username': 'jdoe', 'first_name': 'Jane', 'last_name': 'Doe',
    'email': 'jdoe@example.org', 'pending_at': '2026-11-01T10:00:00Z',
    'sign_in_methods': ['password'],
}


def _ops():
    client = MagicMock()
    client._request.return_value = {'items': [], 'total': 0}
    return client, UserOperations(client)


def test_pending_list_asks_for_waiting_accounts_elevated():
    client, ops = _ops()

    ops.list(pending=True)

    kwargs = client._request.call_args.kwargs
    assert kwargs['params']['pending'] is True
    assert kwargs['privilege_mode'] == 'elevated'


def test_ordinary_list_sends_no_pending_filter():
    client, ops = _ops()

    ops.list()

    kwargs = client._request.call_args.kwargs
    assert 'pending' not in kwargs['params']
    assert kwargs.get('privilege_mode') is None


@pytest.mark.parametrize('method, verb', [('approve', 'approve'), ('reject', 'reject')])
def test_decisions_post_elevated_to_the_reference_given(method, verb):
    client, ops = _ops()
    client._request.return_value = WAITING if method == 'approve' else None

    result = getattr(ops, method)('jdoe')

    client._request.assert_called_once_with('post', f'/users/jdoe/{verb}', privilege_mode='elevated')
    assert result == (WAITING if method == 'approve' else None)


@pytest.mark.parametrize('method', ['approve', 'reject'])
def test_decisions_refuse_an_email_without_a_request(method):
    client, ops = _ops()

    with pytest.raises(ValueError, match='username'):
        getattr(ops, method)('jdoe@example.org')

    client._request.assert_not_called()


def _parse(register, *arguments):
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(dest='command'))
    return parser.parse_args(list(arguments))


def test_cli_lists_waiting_accounts_with_sign_in_and_date(monkeypatch, capsys):
    client = MagicMock()
    client.users.list.return_value = [WAITING]
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    _execute_list(_parse(_register_list, 'list', '--pending'))

    assert client.users.list.call_args.kwargs['pending'] is True
    out = capsys.readouterr().out
    assert 'waiting for approval' in out and 'jdoe' in out and 'password' in out
    assert '2026-11-01' in out


def test_cli_pending_list_stops_for_a_caller_who_cannot_elevate(monkeypatch):
    client = MagicMock()
    client.authorization = SimpleNamespace(platform_role='none', can_elevate=False)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    with pytest.raises(SystemExit):
        _execute_list(_parse(_register_list, 'list', '--pending'))

    client.users.list.assert_not_called()


def test_cli_approve_passes_the_reference_through(monkeypatch, capsys):
    client = MagicMock()
    client.users.approve.return_value = {**WAITING, 'pending_at': None}
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    _execute_approve(SimpleNamespace(user='jdoe', json=False, debug=False))

    client.users.approve.assert_called_once_with('jdoe')
    client.users.get.assert_not_called()
    assert 'Approved jdoe' in capsys.readouterr().out


def test_cli_reject_needs_confirmation(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: False)

    _execute_reject(_parse(_register_reject, 'reject', 'jdoe'))

    client.users.reject.assert_not_called()


def test_cli_reject_with_yes(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    _execute_reject(_parse(_register_reject, 'reject', 'jdoe', '--yes'))

    client.users.reject.assert_called_once_with('jdoe')


def test_cli_reject_email_exits_with_the_hint(monkeypatch):
    client = MagicMock()
    client.users.reject.side_effect = ValueError("Name a waiting account by ORCID, MFID, or username")
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    with pytest.raises(SystemExit):
        _execute_reject(_parse(_register_reject, 'reject', 'jdoe@example.org', '--yes'))


def test_show_user_marks_a_waiting_account(capsys):
    _show_user(WAITING)

    out = capsys.readouterr().out
    assert 'waiting for approval since' in out
    assert 'Signs in with' in out and 'password' in out

