"""Unit coverage for user CLI presentation and argument contracts."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import term
from crucible.cli.helpers import prompt_username
from crucible.cli.user import (
    _execute_create,
    _execute_edit,
    _execute_revoke_keys,
    _execute_set_role,
    _register_create,
    _register_revoke_keys,
    _register_set_role,
    _register_update,
    _show_user,
)


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


def test_admin_view_shows_platform_role_and_key_status(capsys):
    _show_user({
        **BASE_USER,
        'platform_role': 'admin',
        'api_key_status': {'valid': True, 'created_at': '2026-01-01',
                           'expires_at': '2027-01-01'},
    })

    output = capsys.readouterr().out
    assert 'Authorization' in output
    assert 'Platform role' in output
    assert 'admin' in output
    assert 'API key' in output


def test_null_platform_role_hides_authorization_block(capsys):
    _show_user({**BASE_USER, 'platform_role': None})

    assert 'Authorization' not in capsys.readouterr().out


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
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
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
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
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


def test_whoami_shows_authorization(monkeypatch, capsys):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from crucible.cli import whoami
    from crucible.config import config
    from crucible.models import AccountAuthorization, AccountCapabilities

    client = MagicMock(
        privilege_mode=None,
        is_elevated=True,
        authorization=AccountAuthorization(platform_role='admin', can_elevate=True),
        capabilities=AccountCapabilities(can_create_project=True,
                                         can_create_for_others=False),
    )
    client.whoami.return_value = {'user_info': {'unique_id': '0000-0001-6402-3752',
                                                'first_name': 'A', 'last_name': 'B'}}
    monkeypatch.setattr(config, '_client', client)

    whoami.execute(SimpleNamespace(verbose=False, debug=False))

    out = capsys.readouterr().out
    assert 'admin' in out
    assert 'elevated' in out and '(default)' in out
    assert 'yes create projects' in out
    assert 'no create for other users' in out
    assert '- manage service accounts' in out


def test_set_role_restricts_role_choices():
    with pytest.raises(SystemExit):
        _parse(
            _register_set_role,
            'set-role', 'test-user-one', 'support',
        )


def test_set_role_accepts_user_role_values():
    args = _parse(
        _register_set_role,
        'set-role', '0000-0001-6402-3752', 'contributor',
    )

    assert args.user == '0000-0001-6402-3752'
    assert args.platform_role == 'contributor'


def test_set_role_dispatches_canonical_user_without_resolution(monkeypatch):
    client = MagicMock()
    client.users.set_platform_role = MagicMock(return_value={
        **BASE_USER,
        'platform_role': 'contributor',
    })
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    _execute_set_role(SimpleNamespace(
        user='0000-0001-6402-3752',
        platform_role='contributor',
        json=False,
        debug=False,
    ))

    client.users.set_platform_role.assert_called_once_with(
        '0000-0001-6402-3752', 'contributor')


def test_revoke_keys_accepts_yes_flag():
    args = _parse(
        _register_revoke_keys,
        'revoke-keys', '0000-0001-6402-3752', '--yes',
    )

    assert args.yes is True


def test_revoke_keys_skips_confirmation_with_yes(monkeypatch):
    client = MagicMock()
    client.users.revoke_api_keys = MagicMock(return_value=None)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    _execute_revoke_keys(SimpleNamespace(
        user='0000-0001-6402-3752',
        yes=True,
        debug=False,
    ))

    client.users.revoke_api_keys.assert_called_once_with('0000-0001-6402-3752')


def test_revoke_keys_aborts_without_confirmation(monkeypatch):
    client = MagicMock()
    client.users.revoke_api_keys = MagicMock(return_value=None)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr(
        'crucible.cli.helpers.prompt_confirm', lambda *a, **k: False)

    _execute_revoke_keys(SimpleNamespace(
        user='0000-0001-6402-3752',
        yes=False,
        debug=False,
    ))

    client.users.revoke_api_keys.assert_not_called()


def test_grid_fills_columns_top_to_bottom(capsys):
    from crucible.cli import term

    term.grid(['a', 'b', 'c', 'd', 'e'], columns=2, indent=0, gap=2)

    assert capsys.readouterr().out.splitlines() == ['a  d', 'b  e', 'c']
