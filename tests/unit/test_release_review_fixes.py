"""Regression coverage for list ordering, deletion scopes, and instrument updates."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import deletion as deletion_cli
from crucible.cli import instrument as instrument_cli
from crucible.cli.helpers import display_order, resolve_list_project
from crucible.resources.deletion import DeletionOperations


@pytest.mark.parametrize('sort, direction, expected', [
    (None, None, [3, 2, 1]),
    ('created', None, [3, 2, 1]),
    ('name', None, [1, 2, 3]),
    ('name', 'desc', [3, 2, 1]),
    ('updated', 'asc', [1, 2, 3]),
])
def test_display_order_follows_the_effective_direction(sort, direction, expected):
    assert display_order([1, 2, 3], sort, direction) == expected


def test_missing_project_skips_the_current_project(monkeypatch):
    monkeypatch.setattr('crucible.cli.helpers.resolve_project_context',
                        lambda args: ('saved-project', 'config'))
    args = argparse.Namespace(project_id=None, project_mfid=None, all_projects=False,
                              missing=['project'], project_scope=None)

    assert resolve_list_project(args) == (None, None)


def _deletion_args(**overrides):
    values = dict(status='pending', scope=None, project_mfid=None, sort=None,
                  direction=None, json=False, debug=False)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize('status, expected_scope', [
    ('pending', 'reviewable'), ('approved', None), ('all', None)])
def test_deletion_list_reviewable_default_is_pending_only(monkeypatch, status, expected_scope):
    deletions = SimpleNamespace(list=MagicMock(return_value=[]))
    client = SimpleNamespace(deletions=deletions, can_elevate=True)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    deletion_cli._execute_list(_deletion_args(status=status))

    assert deletions.list.call_args.kwargs['scope'] == expected_scope


def test_deletion_list_keeps_the_server_order_for_an_explicit_direction(monkeypatch, capsys):
    records = [{'id': 2, 'status': 'pending'}, {'id': 1, 'status': 'pending'}]
    client = SimpleNamespace(deletions=SimpleNamespace(list=MagicMock(return_value=records)),
                             can_elevate=False)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.resolve_usernames', lambda c, ids: {})

    deletion_cli._execute_list(_deletion_args(direction='desc'))

    rows = [line for line in capsys.readouterr().out.splitlines() if line.strip()[:1] in '12']
    assert [row.strip()[0] for row in rows] == ['2', '1']


@pytest.mark.parametrize('can_elevate, expected', [(True, None), (False, 'submitted')])
def test_list_deleted_defaults_to_submitted_for_non_admins(can_elevate, expected):
    client = MagicMock(can_elevate=can_elevate)
    client._admin_mode.return_value = 'elevated' if can_elevate else None
    client._request.return_value = {'items': [], 'next_cursor': None}
    operations = DeletionOperations(client)

    operations.list_deleted()

    assert client._request.call_args.kwargs['params'].get('scope') == expected


def test_instrument_rename_writes_metadata_to_the_renamed_instrument(monkeypatch):
    instruments = SimpleNamespace(
        update=MagicMock(return_value={'unique_id': 'I' * 26, 'instrument_id': 'titan-2'}),
        update_scientific_metadata=MagicMock())
    monkeypatch.setattr('crucible.config.get_client',
                        lambda: SimpleNamespace(instruments=instruments))
    monkeypatch.setattr('crucible.cli.helpers.load_metadata', lambda value: {'k': 1})
    monkeypatch.setattr(instrument_cli, '_show_instrument', lambda record: None)
    args = SimpleNamespace(unique_id='titan', instrument_name=None, instrument_id='titan-2',
                           location=None, manufacturer=None, model=None, instrument_type=None,
                           description=None, metadata='{"k": 1}', overwrite=False,
                           json=False, debug=False)

    instrument_cli._execute_update(args)

    instruments.update_scientific_metadata.assert_called_once_with(
        'I' * 26, {'k': 1}, overwrite=False)
