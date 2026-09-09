"""Unit coverage for user CLI presentation and argument contracts."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import term
from crucible.cli.helpers import prompt_username
from crucible.cli.user import _execute_create, _execute_edit, _register_create, _register_update, _show_user


BASE_USER = {
    'unique_id': '0000-0001-6402-3752',
    'username': 'roncofaber',
    'first_name': 'Fabrice',
    'last_name': 'Roncoroni',
}


def test_omitted_email_row_is_hidden(capsys):
    _show_user(dict(BASE_USER))

    output = capsys.readouterr().out
    assert 'Email' not in output
    assert '(not disclosed)' not in output


def test_explicit_null_email_is_reported_as_not_set(capsys):
    _show_user({**BASE_USER, 'email': None})

    output = capsys.readouterr().out
    assert 'Email' in output
    assert '(not set)' in output


def test_authorized_email_is_displayed(capsys):
    _show_user({**BASE_USER, 'email': 'roncoroni@lbl.gov'})

    assert 'roncoroni@lbl.gov' in capsys.readouterr().out


def _parse(register, *arguments):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    register(subparsers)
    return parser.parse_args(list(arguments))


def test_mfid_backed_human_uses_user_id_label(capsys):
    _show_user({
        **BASE_USER,
        'unique_id': '0tkvpezyz1zzf00076nahf85j4',
        'is_service_account': False,
    })

    output = capsys.readouterr().out
    assert 'User ID' in output
    assert 'ORCID' not in output


def test_create_accepts_username_without_orcid():
    args = _parse(
        _register_create,
        'create', '--username', 'test-user-one',
        '--first-name', 'Test', '--last-name', 'User One',
    )

    assert args.username == 'test-user-one'
    assert args.orcid is None


def test_interactive_username_prompt_retries_and_normalizes(monkeypatch, capsys):
    answers = iter(['1invalid', 'Alice_User'])
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))

    assert prompt_username() == 'alice_user'
    assert 'Invalid value' in capsys.readouterr().err


def test_interactive_create_uses_validated_username(monkeypatch):
    client = SimpleNamespace(users=SimpleNamespace())
    client.users.create = MagicMock(return_value={
        'unique_id': '0tkvpezyz1zzf00076nahf85j4',
        'username': 'alice_user',
        'first_name': 'Alice',
        'last_name': 'User',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.prompt_username', lambda prompt='Username: ': 'alice_user')
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    _execute_create(SimpleNamespace(
        orcid=None,
        first_name='Alice',
        last_name='User',
        username=None,
        email=None,
        projects=None,
        debug=False,
        json=False,
    ))

    created_user = client.users.create.call_args.args[0]
    assert created_user.username == 'alice_user'


def test_update_no_longer_accepts_service_account_conversion():
    with pytest.raises(SystemExit):
        _parse(
            _register_update,
            'update', 'test-user-one', '--service-account',
        )


def test_edit_updates_mfid_backed_human(monkeypatch):
    user_mfid = '0tkvpezyz1zzf00076nahf85j4'
    client = SimpleNamespace(users=SimpleNamespace())
    client.users.get = MagicMock(return_value={
        'unique_id': user_mfid,
        'username': 'test-user-one',
        'first_name': 'Test',
        'last_name': 'User One',
        'email': None,
        'is_service_account': False,
    })
    client.users.update = MagicMock(return_value={
        'unique_id': user_mfid,
        'username': 'test-user-one',
        'first_name': 'Updated',
        'last_name': 'User One',
        'email': None,
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(term, 'open_editor_json', lambda original: {
        **original,
        'first_name': 'Updated',
    })

    _execute_edit(SimpleNamespace(
        user=user_mfid,
        orcid=None,
        username=None,
        email=None,
        debug=False,
    ))

    client.users.update.assert_called_once_with(user_mfid, first_name='Updated')
