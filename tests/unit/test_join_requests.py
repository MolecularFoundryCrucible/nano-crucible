"""Unit coverage for the project join-request routes and their CLI."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.cli import access_group as access_group_cli
from crucible.resources.access_groups import AccessGroupOperations
from crucible.resources.account import AccountOperations


RECORD = {
    'id': 42,
    'status': 'pending',
    'project_mfid': '0tkn2knjast3h0008nyq9zps2c',
    'project': {'unique_id': '0tkn2knjast3h0008nyq9zps2c', 'project_id': 'thin-films',
                'title': 'Thin films'},
    'requester_id': '0000-0002-1825-0097',
    'requester': {'unique_id': '0000-0002-1825-0097', 'username': 'ehwong'},
    'reason': 'XRD campaign',
    'request_time': '2026-10-16T17:02:11.000000Z',
    'capabilities': {'can_review': True, 'can_withdraw': False},
    'group_name': 'thin-films',
}


def make(response=None):
    client = MagicMock()
    client._admin_mode.return_value = None
    client._request.return_value = response if response is not None else {
        'items': [], 'next_cursor': None}
    return AccessGroupOperations(client), client


def test_request_join_posts_to_the_project_route():
    resource, client = make(RECORD)

    record = resource.request_join('thin-films', reason='XRD campaign')

    args, kwargs = client._request.call_args
    assert args == ('post', '/projects/thin-films/join_requests')
    assert kwargs['json'] == {'reason': 'XRD campaign'}
    assert record['project']['project_id'] == 'thin-films'
    assert record['capabilities'] == {'can_review': True, 'can_withdraw': False}


def test_request_join_group_name_keyword_is_deprecated():
    resource, client = make(RECORD)

    with pytest.warns(DeprecationWarning, match='group_name'):
        resource.request_join(group_name='thin-films')

    assert client._request.call_args.args[1] == '/projects/thin-films/join_requests'
    assert client._request.call_args.kwargs['json'] == {}


def test_list_forwards_filters_and_sort():
    resource, client = make()

    resource.list_join_requests(
        scope='reviewable', status=['pending', 'approved'], project_mfid='mf-1',
        reviewer_id='0000-0001', requested_after=date(2026, 10, 1),
        requested_before='2026-10-02', q='smith', sort='requester_name',
        direction='asc')

    params = client._request.call_args.kwargs['params']
    assert params['scope'] == 'reviewable'
    assert params['status'] == ['pending', 'approved']
    assert params['project_mfid'] == 'mf-1'
    assert params['reviewer_id'] == '0000-0001'
    assert params['requested_after'] == '2026-10-01T00:00:00+00:00'
    assert params['requested_before'] == '2026-10-02T23:59:59.999999+00:00'
    assert params['q'] == 'smith'
    assert params['sort'] == 'requester_name'
    assert params['direction'] == 'asc'
    assert 'group_name' not in params


def test_list_group_name_resolves_to_project_mfid():
    resource, client = make()
    client.projects._resource_mfid.return_value = 'mf-1'

    with pytest.warns(DeprecationWarning, match='group_name'):
        resource.list_join_requests(group_name='thin-films')

    client.projects._resource_mfid.assert_called_once_with('thin-films')
    params = client._request.call_args.kwargs['params']
    assert params['project_mfid'] == 'mf-1'
    assert 'group_name' not in params


@pytest.mark.parametrize('kwargs', [
    {'status': 'closed'},
    {'scope': 'everything'},
    {'sort': 'created'},
    {'direction': 'sideways'},
])
def test_list_rejects_unknown_choices(kwargs):
    resource, client = make()

    with pytest.raises(ValueError):
        resource.list_join_requests(**kwargs)

    client._request.assert_not_called()


def test_submitted_scope_does_not_request_elevation():
    resource, client = make()
    client._admin_mode.return_value = 'elevated'

    resource.list_join_requests(scope='submitted')
    assert 'privilege_mode' not in client._request.call_args.kwargs

    resource.list_join_requests(scope='reviewable')
    assert client._request.call_args.kwargs['privilege_mode'] == 'elevated'


def test_account_join_requests_lists_submitted_scope():
    client = MagicMock()
    AccountOperations(client).join_requests(status='pending', limit=5)

    client.access_groups.list_join_requests.assert_called_once_with(
        scope='submitted', status='pending', limit=5, offset=0, cursor=None)


def test_facets_send_field_and_filters():
    resource, client = make({'field': 'status', 'items': [
        {'value': 'pending', 'label': 'pending', 'count': 3}], 'limit': 50})

    result = resource.join_request_facets('status', scope='reviewable', status='pending')

    args, kwargs = client._request.call_args
    assert args == ('get', '/join_requests/facets')
    assert kwargs['params'] == {'scope': 'reviewable', 'status': ['pending'],
                                'field': 'status', 'limit': 50}
    assert result['items'][0]['count'] == 3


def test_facets_reject_unknown_field():
    resource, _ = make()

    with pytest.raises(ValueError):
        resource.join_request_facets('owner')


def test_get_reads_the_single_record_route():
    resource, client = make(RECORD)

    assert resource.get(42)['id'] == 42
    assert client._request.call_args.args == ('get', '/join_requests/42')


def test_get_returns_none_for_404_only():
    resource, client = make()
    missing = requests.exceptions.HTTPError(response=SimpleNamespace(status_code=404))
    client._request.side_effect = missing
    assert resource.get(42) is None

    client._request.side_effect = requests.exceptions.HTTPError(
        response=SimpleNamespace(status_code=500))
    with pytest.raises(requests.exceptions.HTTPError):
        resource.get(42)


def test_approve_sends_role_and_notes():
    resource, client = make(RECORD)

    resource.approve_join_request(42, reviewer_notes='Welcome', role='editor')

    args, kwargs = client._request.call_args
    assert args == ('patch', '/join_requests/42')
    assert kwargs['json'] == {'status': 'approved', 'role': 'editor',
                              'reviewer_notes': 'Welcome'}


def test_approve_rejects_owner_role():
    resource, client = make()

    with pytest.raises(ValueError):
        resource.approve_join_request(42, role='owner')

    client._request.assert_not_called()


def test_reject_sends_no_role():
    resource, client = make(RECORD)

    resource.reject_join_request(42)

    assert client._request.call_args.kwargs['json'] == {'status': 'rejected'}


def test_withdraw_posts_to_withdraw_route():
    resource, client = make({**RECORD, 'status': 'withdrawn'})

    record = resource.withdraw_join_request(42)

    assert client._request.call_args.args == ('post', '/join_requests/42/withdraw')
    assert record['status'] == 'withdrawn'


def test_cli_list_defaults_to_pending_review_queue(monkeypatch, capsys):
    client = MagicMock()
    client.access_groups.list_join_requests.return_value = [RECORD]
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser = access_group_cli.argparse.ArgumentParser()
    access_group_cli.register_subcommand(parser.add_subparsers())

    args = parser.parse_args(['ag', 'list'])
    args.func(args)

    kwargs = client.access_groups.list_join_requests.call_args.kwargs
    assert kwargs['scope'] == 'reviewable'
    assert kwargs['status'] == ['pending']
    client.users.resolve.assert_not_called()
    out = capsys.readouterr().out
    assert 'thin-films' in out
    assert 'ehwong' in out


def test_cli_list_project_and_deprecated_group(monkeypatch, capsys):
    client = MagicMock()
    client.projects.list_join_requests.return_value = []
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser = access_group_cli.argparse.ArgumentParser()
    access_group_cli.register_subcommand(parser.add_subparsers())

    args = parser.parse_args(['ag', 'list', '--group', 'thin-films', '--status', 'all'])
    args.func(args)

    assert 'deprecated' in capsys.readouterr().err
    call = client.projects.list_join_requests.call_args
    assert call.args == ('thin-films',)
    assert call.kwargs['status'] is None


def test_cli_approve_passes_role(monkeypatch):
    client = MagicMock()
    client.access_groups.approve_join_request.return_value = RECORD
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser = access_group_cli.argparse.ArgumentParser()
    access_group_cli.register_subcommand(parser.add_subparsers())

    args = parser.parse_args(['ag', 'approve', '42', '--role', 'viewer'])
    args.func(args)

    client.access_groups.approve_join_request.assert_called_once_with(
        42, reviewer_notes=None, role='viewer')


def test_cli_withdraw_exits_nonzero_on_failure(monkeypatch):
    client = MagicMock()
    client.access_groups.withdraw_join_request.side_effect = RuntimeError('409 closed')
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    parser = access_group_cli.argparse.ArgumentParser()
    access_group_cli.register_subcommand(parser.add_subparsers())

    args = parser.parse_args(['ag', 'withdraw', '42'])
    with pytest.raises(SystemExit) as exc:
        args.func(args)

    assert exc.value.code == 1
