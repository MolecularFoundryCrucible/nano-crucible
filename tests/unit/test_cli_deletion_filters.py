"""Unit coverage for the deletion CLI filter flags."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from crucible.cli import deletion


def make_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    deletion.register_subcommand(subparsers)
    return parser


@pytest.fixture
def client():
    fake = MagicMock()
    fake.deletions.list.return_value = []
    fake.deletions.list_deleted.return_value = []
    with patch('crucible.client.CrucibleClient', return_value=fake):
        yield fake


def test_request_list_defaults_pass_none(client):
    args = make_parser().parse_args(['deletion', 'list'])

    args.func(args)

    kwargs = client.deletions.list.call_args.kwargs
    assert kwargs['scope'] is None
    assert kwargs['sort'] is None
    assert kwargs['direction'] is None
    assert kwargs['project_mfid'] is None
    assert kwargs['status'] == 'pending'


def test_request_list_forwards_the_new_flags(client):
    args = make_parser().parse_args([
        'deletion', 'list', '--scope', 'reviewable', '--sort', 'status',
        '--direction', 'asc', '--project-mfid', 'mf-1',
    ])

    args.func(args)

    kwargs = client.deletions.list.call_args.kwargs
    assert kwargs['scope'] == 'reviewable'
    assert kwargs['sort'] == 'status'
    assert kwargs['direction'] == 'asc'
    assert kwargs['project_mfid'] == 'mf-1'


def test_server_ordering_is_preserved_when_sort_is_given(client):
    client.deletions.list.return_value = [
        {'id': 9, 'status': 'pending'}, {'id': 2, 'status': 'pending'}]
    args = make_parser().parse_args(['deletion', 'list', '--sort', 'status'])

    with patch.object(deletion.term, 'table') as table:
        args.func(args)

    assert [row[0] for row in table.call_args.args[0]] == [9, 2]


def test_audit_list_forwards_the_new_flags(client):
    args = make_parser().parse_args([
        'deletion', 'list-deleted', '--scope', 'submitted',
        '--project-id', 'demo', '--project-mfid', 'mf-1', '--direction', 'asc',
    ])

    args.func(args)

    kwargs = client.deletions.list_deleted.call_args.kwargs
    assert kwargs['scope'] == 'submitted'
    assert kwargs['project_id'] == 'demo'
    assert kwargs['project_mfid'] == 'mf-1'
    assert kwargs['direction'] == 'asc'


def test_invalid_scope_is_rejected():
    with pytest.raises(SystemExit):
        make_parser().parse_args(['deletion', 'list', '--scope', 'everything'])
