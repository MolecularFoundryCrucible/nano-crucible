"""Unit coverage for project CLI argument compatibility."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.cli.project import (
    _execute_add_user,
    _register_add_user,
    _register_get,
    _register_remove_user,
    _register_update_user_role,
)


def parse_project_get(*arguments):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    _register_get(subparsers)
    return parser.parse_args(['get'] + list(arguments))


def test_include_members_is_canonical_without_warning():
    args = parse_project_get('example-project', '--include-members')

    assert args.include_members is True


def test_members_alias_warns_and_remains_supported():
    with pytest.warns(DeprecationWarning, match='--include-members'):
        args = parse_project_get('example-project', '--members')

    assert args.include_members is True


def parse_project_command(register, command, *arguments):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    register(subparsers)
    return parser.parse_args([command] + list(arguments))


@pytest.mark.parametrize('role', ['viewer', 'contributor', 'editor', 'admin'])
def test_add_user_accepts_named_roles(role):
    args = parse_project_command(
        _register_add_user, 'add-user', 'example-project', '--user', 'alice', '--role', role)

    assert args.role == role


@pytest.mark.parametrize('role', ['owner', 'invalid', '3'])
def test_add_user_rejects_invalid_roles(role):
    with pytest.raises(SystemExit):
        parse_project_command(
            _register_add_user, 'add-user', 'example-project', '--user', 'alice', '--role', role)


def test_update_user_role_rejects_owner():
    with pytest.raises(SystemExit):
        parse_project_command(
            _register_update_user_role,
            'update-user-role',
            'example-project',
            '0000-0001-6402-3752',
            'owner',
        )


@pytest.mark.parametrize(('register', 'command', 'expected'), [
    (_register_add_user, 'add-user', 'granted role must be below your role'),
    (_register_update_user_role, 'update-user-role', 'must both be below your role'),
    (_register_remove_user, 'remove-user', 'project owner or platform administrator'),
])
def test_membership_help_describes_current_hierarchy(register, command, expected):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    register(subparsers)

    assert expected in subparsers.choices[command].description


def test_add_user_dispatches_named_role_and_username(monkeypatch):
    client = SimpleNamespace(projects=SimpleNamespace())
    client.projects.add_user = MagicMock(return_value=[SimpleNamespace(
        unique_id='0000-0001-6402-3752',
        username='alice',
        first_name='Alice',
        last_name='User',
    )])
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    _execute_add_user(SimpleNamespace(
        project_id='example-project',
        user='alice',
        role='editor',
        orcid=None,
        email=None,
        username=None,
        debug=False,
        json=False,
    ))

    client.projects.add_user.assert_called_once_with(
        user_unique_id=None,
        project_id='example-project',
        email=None,
        username='alice',
        role='editor',
    )


def test_add_user_duplicate_conflict_uses_shared_error_formatter(monkeypatch, capsys):
    response = requests.Response()
    response.status_code = 409
    response.reason = 'Conflict'
    response._content = b'{"detail":"User is already a project member"}'
    client = SimpleNamespace(projects=SimpleNamespace())
    client.projects.add_user = MagicMock(side_effect=requests.HTTPError(
        '409 Conflict', response=response))
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    with pytest.raises(SystemExit) as raised:
        _execute_add_user(SimpleNamespace(
            project_id='example-project',
            user='alice',
            role=None,
            orcid=None,
            email=None,
            username=None,
            debug=False,
            json=False,
        ))

    assert raised.value.code == 1
    error = capsys.readouterr().err
    assert 'Error 409 Conflict' in error
    assert 'User is already a project member' in error
