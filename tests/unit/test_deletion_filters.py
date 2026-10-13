"""Unit coverage for the deletion request and audit list filters."""

from unittest.mock import MagicMock

import pytest

from crucible.models import DeletionAuditLog, DeletionRequest
from crucible.resources.deletion import DeletionOperations


def make():
    client = MagicMock()
    resource = DeletionOperations(client)
    client._request.return_value = {'items': [], 'next_cursor': None}
    return resource, client._request


def sent_params(request):
    return request.call_args.kwargs['params']


def test_request_list_defaults_send_no_new_parameters():
    resource, request = make()

    resource.list()

    params = sent_params(request)
    for name in ('scope', 'sort', 'direction', 'project_mfid'):
        assert name not in params


def test_request_list_forwards_the_new_filters():
    resource, request = make()

    resource.list(scope='reviewable', project_mfid='mf-1', sort='resource_name',
                  direction='asc')

    params = sent_params(request)
    assert params['scope'] == 'reviewable'
    assert params['project_mfid'] == 'mf-1'
    assert params['sort'] == 'resource_name'
    assert params['direction'] == 'asc'


def test_request_list_direction_is_accepted_without_sort():
    resource, request = make()

    resource.list(direction='asc')

    assert sent_params(request)['direction'] == 'asc'


@pytest.mark.parametrize('kwargs', [
    {'scope': 'everything'},
    {'sort': 'deleted_at'},
    {'direction': 'sideways'},
])
def test_request_list_rejects_unknown_choices(kwargs):
    resource, _ = make()

    with pytest.raises(ValueError):
        resource.list(**kwargs)


def test_audit_list_defaults_send_no_new_parameters():
    resource, request = make()

    resource.list_deleted()

    params = sent_params(request)
    for name in ('scope', 'direction', 'project_id', 'project_mfid'):
        assert name not in params


def test_audit_list_forwards_the_new_filters():
    resource, request = make()

    resource.list_deleted(scope='submitted', project_id='demo',
                          project_mfid='mf-1', direction='asc')

    params = sent_params(request)
    assert params['scope'] == 'submitted'
    assert params['project_id'] == 'demo'
    assert params['project_mfid'] == 'mf-1'
    assert params['direction'] == 'asc'


@pytest.mark.parametrize('kwargs', [
    {'scope': 'reviewable'},
    {'direction': 'sideways'},
])
def test_audit_list_rejects_unknown_choices(kwargs):
    resource, _ = make()

    with pytest.raises(ValueError):
        resource.list_deleted(**kwargs)


def test_deletion_request_model_keeps_the_new_fields():
    record = DeletionRequest(
        id=1,
        project_mfid='mf-project',
        requester={'unique_id': 'mf-user', 'first_name': 'Ada'},
        reviewer={'unique_id': 'mf-admin'},
        capabilities={'can_review': True},
    ).model_dump()

    assert record['project_mfid'] == 'mf-project'
    assert record['requester']['first_name'] == 'Ada'
    assert record['reviewer']['unique_id'] == 'mf-admin'
    assert record['capabilities']['can_review'] is True


def test_deletion_audit_model_keeps_the_new_fields():
    record = DeletionAuditLog(
        id=1,
        project_mfid='mf-project',
        requester={'unique_id': 'mf-user'},
        reviewer={'unique_id': 'mf-admin'},
    ).model_dump()

    assert record['project_mfid'] == 'mf-project'
    assert record['requester']['unique_id'] == 'mf-user'
    assert record['reviewer']['unique_id'] == 'mf-admin'
