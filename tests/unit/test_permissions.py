"""Unit tests for the permission-system overhaul - mocked, no live API.

Targets the `feat/permission-roles` crucible-api branch (see
crucible-api/docs/permission_system_api_changes.md), not yet universally
deployed - see tests/unit/ vs tests/integration/ split in CLAUDE.md.
"""

from unittest.mock import MagicMock

import pytest
import requests

from crucible.models import (
    AccessGrant,
    EffectiveResourceAccess,
    Instrument,
    OwnershipTransfer,
    Project,
    ProjectMember,
    ProjectReassignment,
    ResourceCapabilities,
)
from crucible.resources.datasets import DatasetOperations
from crucible.resources.instruments import InstrumentOperations
from crucible.resources.projects import ProjectOperations
from crucible.resources.users import UserOperations


@pytest.fixture
def dataset_ops():
    client = MagicMock()
    ops = DatasetOperations(client)
    ops._client = client
    return ops


@pytest.fixture
def instrument_ops():
    client = MagicMock()
    ops = InstrumentOperations(client)
    ops._client = client
    return ops


@pytest.fixture
def project_ops():
    client = MagicMock()
    ops = ProjectOperations(client)
    ops._client = client
    return ops


@pytest.fixture
def user_ops():
    client = MagicMock()
    ops = UserOperations(client)
    ops._client = client
    return ops


class TestResourceCapabilities:
    def test_optional_capabilities_accept_absent_and_null(self):
        assert Instrument().capabilities is None
        assert Project(
            project_id='example',
            organization='LBNL',
            capabilities=None,
        ).capabilities is None

    def test_capabilities_parse_named_maximum_grant_role(self):
        capabilities = ResourceCapabilities(
            can_edit=True,
            can_manage_access=True,
            can_change_status=False,
            can_transfer=False,
            max_grant_role='editor',
        )

        instrument = Instrument(capabilities=capabilities)

        assert instrument.capabilities.max_grant_role == 'editor'

    def test_capabilities_reject_owner_as_normal_grant_role(self):
        with pytest.raises(ValueError):
            ResourceCapabilities(
                can_edit=True,
                can_manage_access=True,
                can_change_status=True,
                can_transfer=True,
                max_grant_role='owner',
            )

    def test_project_create_omits_response_capabilities(self, project_ops):
        project_ops._request = MagicMock(return_value={
            'unique_id': '0tkn2knjast3h0008nyq9zps2c',
            'project_id': 'example',
        })
        project = Project(
            project_id='example',
            organization='LBNL',
            project_lead='alice',
            capabilities=ResourceCapabilities(
                can_edit=True,
                can_manage_access=True,
                can_change_status=True,
                can_transfer=True,
                max_grant_role='admin',
            ),
        )

        project_ops.create(project)

        assert 'capabilities' not in project_ops._request.call_args.kwargs['json']

    def test_project_update_rejects_response_capabilities(self, project_ops):
        project_ops._request = MagicMock()

        with pytest.raises(ValueError, match='response-only'):
            project_ops.update('example', capabilities={})

        project_ops._request.assert_not_called()


class TestListAccess:
    def test_parses_access_grants(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value=[
            {'principal_id': '0000-0001', 'principal_type': 'user', 'permission': 'viewer',
             'display_name': 'A User'},
        ])

        result = dataset_ops.list_access('ds-1')

        dataset_ops._request.assert_called_once_with('get', '/resources/ds-1/access')
        assert isinstance(result[0], AccessGrant)
        assert result[0].principal_type == 'user'
        assert result[0].permission == 'viewer'
        assert result[0].kind == 'user'
        assert result[0].effective_permission == 'viewer'


class TestSetAccess:
    def test_sends_correct_route_and_body(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={
            'principal_id': 'project-mfid', 'principal_type': 'project',
            'permission': 'editor', 'slug': 'proj-1',
        })

        result = dataset_ops.set_access('ds-1', 'projects', 'proj-1', 'editor')

        dataset_ops._request.assert_called_once_with(
            'put', '/resources/ds-1/access/projects/proj-1',
            json={'permission': 'editor'})
        assert isinstance(result, AccessGrant)
        assert result.principal_id == 'project-mfid'
        assert result.slug == 'proj-1'


class TestRevokeAccess:
    def test_sends_correct_route(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value=None)

        dataset_ops.revoke_access('ds-1', 'users', '0000-0001')

        dataset_ops._request.assert_called_once_with(
            'delete', '/resources/ds-1/access/users/0000-0001')


class TestPublicAccess:
    def test_set_public_no_permission_param(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={
            'principal_id': 'public',
            'principal_type': 'public',
            'permission': 'viewer',
        })

        result = dataset_ops.set_public('ds-1')

        dataset_ops._request.assert_called_once_with('put', '/resources/ds-1/access/public')
        assert isinstance(result, AccessGrant)

    def test_set_private(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value=None)

        dataset_ops.set_private('ds-1')

        dataset_ops._request.assert_called_once_with('delete', '/resources/ds-1/access/public')

    def test_publish_warns_and_sets_public(self, dataset_ops):
        dataset_ops.set_public = MagicMock(return_value='grant')

        with pytest.warns(DeprecationWarning, match=r'publish\(\) is deprecated'):
            result = dataset_ops.publish('ds-1')

        dataset_ops.set_public.assert_called_once_with('ds-1')
        assert result == 'grant'

    @pytest.mark.parametrize('method_name', ['unpublish', 'unset_public'])
    def test_private_aliases_warn_and_set_private(self, dataset_ops, method_name):
        dataset_ops.set_private = MagicMock(return_value={'detail': 'removed'})

        with pytest.warns(DeprecationWarning, match=rf'{method_name}\(\) is deprecated'):
            result = getattr(dataset_ops, method_name)('ds-1')

        dataset_ops.set_private.assert_called_once_with('ds-1')
        assert result == {'detail': 'removed'}

    def test_dataset_update_public_delegates_to_access_route(self, dataset_ops):
        dataset_ops._request = MagicMock(side_effect=[
            {'unique_id': 'ds-1', 'dataset_name': 'Updated'},
            {
                'principal_id': 'public',
                'principal_type': 'public',
                'permission': 'viewer',
            },
        ])

        with pytest.warns(DeprecationWarning, match="'public' update field"):
            result = dataset_ops.update('ds-1', dataset_name='Updated', public=True)

        assert dataset_ops._request.call_args_list == [
            (("patch", "/datasets/ds-1"), {'json': {'dataset_name': 'Updated'}}),
            (("put", "/resources/ds-1/access/public"),),
        ]
        assert result['public'] is True

    def test_sample_update_public_delegates_to_access_route(self):
        client = MagicMock()
        from crucible.resources.samples import SampleOperations
        sample_ops = SampleOperations(client)
        sample_ops._request = MagicMock(side_effect=[
            {'unique_id': 'sample-1', 'sample_name': 'Updated'},
            {
                'principal_id': 'public',
                'principal_type': 'public',
                'permission': 'viewer',
            },
        ])

        with pytest.warns(DeprecationWarning, match="Parameter 'public'"):
            result = sample_ops.update('sample-1', sample_name='Updated', public=True)

        assert sample_ops._request.call_args_list == [
            (("patch", "/samples/sample-1"), {'json': {'sample_name': 'Updated'}}),
            (("put", "/resources/sample-1/access/public"),),
        ]
        assert result['public'] is True


class TestEffectiveDatasetAccess:
    def test_parses_effective_access(self, user_ops):
        user_ops._request = MagicMock(return_value={
            'resource_mfid': 'ds-1',
            'user_id': '0000-0001',
            'effective_access': 'editor',
        })

        result = user_ops.check_dataset_access('alice', 'ds-1')

        user_ops._request.assert_called_once_with(
            'get', '/users/alice/datasets/ds-1')
        assert isinstance(result, EffectiveResourceAccess)
        assert result.effective_access == 'editor'


class TestTransferOwnership:
    def test_preview_by_default(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={
            'resource_id': 'ds-1',
            'previous_owner': {'unique_id': 'u1', 'username': 'old'},
            'new_owner': {'unique_id': 'u2', 'username': 'new'},
        })

        result = dataset_ops.transfer_ownership('ds-1', 'new')

        dataset_ops._request.assert_called_once_with(
            'post', '/resources/ds-1/transfer_ownership',
            params={'confirm': False}, json={'new_owner': 'new'})
        assert isinstance(result, OwnershipTransfer)
        assert result.new_owner.username == 'new'

    def test_confirm_true_passed_through(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={
            'resource_id': 'ds-1', 'previous_owner': None,
            'new_owner': {'unique_id': 'u2', 'username': 'new'},
        })

        dataset_ops.transfer_ownership('ds-1', 'new', confirm=True)

        assert dataset_ops._request.call_args.kwargs['params'] == {'confirm': True}


class TestReassignProject:
    def test_sends_correct_route_and_body(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={
            'resource_id': 'ds-1', 'previous_project_id': 'old-proj', 'new_project_id': 'new-proj',
        })

        result = dataset_ops.reassign_project('ds-1', 'new-proj', confirm=True)

        dataset_ops._request.assert_called_once_with(
            'post', '/resources/ds-1/project',
            params={'confirm': True}, json={'project_id': 'new-proj'})
        assert isinstance(result, ProjectReassignment)
        assert result.new_project_id == 'new-proj'


class TestInstrumentCreateRequiresInstrumentId:
    def test_raises_when_missing(self, instrument_ops):
        instrument = Instrument(instrument_name='titan', owner='mf', location='B67')

        with pytest.raises(ValueError):
            instrument_ops.create(instrument)

    def test_passes_through_when_present(self, instrument_ops):
        instrument_ops._request = MagicMock(side_effect=[
            {'total': 0, 'items': []},
            {'unique_id': 'mf-1', 'instrument_id': 'titan'},
        ])
        instrument = Instrument(instrument_name='titan', instrument_id='titan', owner='mf', location='B67')

        result = instrument_ops.create(instrument)

        assert instrument_ops._request.call_count == 2
        _, endpoint = instrument_ops._request.call_args.args
        assert endpoint == '/instruments'
        assert instrument_ops._request.call_args.kwargs['json']['instrument_id'] == 'titan'
        assert result['instrument_id'] == 'titan'


class TestBindServiceAccount:
    def test_bind(self, instrument_ops):
        instrument_ops._request = MagicMock(return_value=[
            {'unique_id': 'sa-1', 'username': 'sa', 'role': 'operator'},
        ])

        result = instrument_ops.bind_service_account('mf-1', 'sa-1')

        instrument_ops._request.assert_called_once_with(
            'post', '/instruments/mf-1/service_accounts/sa-1')
        assert isinstance(result[0], ProjectMember)
        assert result[0].role == 'operator'

    def test_unbind(self, instrument_ops):
        instrument_ops._request = MagicMock(return_value=[])

        instrument_ops.unbind_service_account('mf-1', 'sa-1')

        instrument_ops._request.assert_called_once_with(
            'delete', '/instruments/mf-1/service_accounts/sa-1')


class TestProjectAddUserRole:
    def test_role_passed_as_query_param(self, project_ops):
        project_ops._request = MagicMock(return_value=[
            {'unique_id': 'u1', 'username': 'alice', 'role': 'editor'},
        ])

        result = project_ops.add_user(
            user_unique_id='0000-0001', project_id='proj-1', role='editor')

        project_ops._request.assert_called_once_with(
            'post', '/projects/proj-1/users/0000-0001', params={'role': 'editor'})
        assert isinstance(result[0], ProjectMember)
        assert result[0].role == 'editor'

    def test_role_omitted_when_not_given(self, project_ops):
        project_ops._request = MagicMock(return_value=[])

        project_ops.add_user(user_unique_id='0000-0001', project_id='proj-1')

        project_ops._request.assert_called_once_with(
            'post', '/projects/proj-1/users/0000-0001', params={})

    def test_username_resolves_before_canonical_membership_request(self, project_ops):
        project_ops._client.users.get.return_value = {
            'unique_id': '0000-0001',
            'username': 'alice',
        }
        project_ops._request = MagicMock(return_value=[])

        project_ops.add_user(username='alice', project_id='proj-1')

        project_ops._client.users.get.assert_called_once_with(username='alice')
        project_ops._request.assert_called_once_with(
            'post', '/projects/proj-1/users/0000-0001', params={})

    def test_email_resolves_before_canonical_membership_request(self, project_ops):
        project_ops._client.users.get.return_value = {
            'unique_id': '0000-0001',
            'username': 'alice',
        }
        project_ops._request = MagicMock(return_value=[])

        project_ops.add_user(email='alice@example.org', project_id='proj-1')

        project_ops._client.users.get.assert_called_once_with(email='alice@example.org')
        project_ops._request.assert_called_once_with(
            'post', '/projects/proj-1/users/0000-0001', params={})

    def test_service_account_mfid_uses_canonical_membership_request(self, project_ops):
        service_account_mfid = '0tkvpezyz1zzf00076nahf85j4'
        project_ops._request = MagicMock(return_value=[])

        project_ops.add_user(user_unique_id=service_account_mfid, project_id='proj-1')

        project_ops._client.users.get.assert_not_called()
        project_ops._request.assert_called_once_with(
            'post', f'/projects/proj-1/users/{service_account_mfid}', params={})

    def test_conflicting_identifiers_are_rejected(self, project_ops):
        project_ops._request = MagicMock()

        with pytest.raises(ValueError, match='exactly one user identifier'):
            project_ops.add_user(
                user_unique_id='0000-0001', username='alice', project_id='proj-1')

        project_ops._request.assert_not_called()

    @pytest.mark.parametrize('role', ['owner', 'invalid', 'EDITOR', 3])
    def test_invalid_role_is_rejected(self, project_ops, role):
        project_ops._request = MagicMock()

        with pytest.raises(ValueError, match='Project member role must be one of'):
            project_ops.add_user(
                user_unique_id='0000-0001', project_id='proj-1', role=role)

        project_ops._request.assert_not_called()

    def test_duplicate_member_conflict_is_preserved(self, project_ops):
        response = requests.Response()
        response.status_code = 409
        response.reason = 'Conflict'
        response._content = b'{"detail":"User is already a project member"}'
        project_ops._request = MagicMock(side_effect=requests.HTTPError(
            '409 Conflict', response=response))

        with pytest.raises(requests.HTTPError) as raised:
            project_ops.add_user(user_unique_id='0000-0001', project_id='proj-1')

        assert raised.value.response.status_code == 409


class TestProjectUpdateUserRole:
    def test_sends_correct_route_and_param(self, project_ops):
        project_ops._request = MagicMock(return_value=[
            {'unique_id': 'u1', 'username': 'alice', 'role': 'admin'},
        ])

        result = project_ops.update_user_role('proj-1', '0000-0001', 'admin')

        project_ops._request.assert_called_once_with(
            'patch', '/projects/proj-1/users/0000-0001', params={'role': 'admin'})
        assert result[0].role == 'admin'

    @pytest.mark.parametrize('role', ['owner', 'invalid', 'ADMIN', 4])
    def test_invalid_role_is_rejected(self, project_ops, role):
        project_ops._request = MagicMock()

        with pytest.raises(ValueError, match='Project member role must be one of'):
            project_ops.update_user_role('proj-1', '0000-0001', role)

        project_ops._request.assert_not_called()


class TestProjectGetIncludeMembers:
    def test_include_members_sets_param(self, project_ops):
        project_ops._request = MagicMock(return_value={
            'total': 1,
            'items': [{'unique_id': '0tkn2knjast3h0008nyq9zps2c', 'project_id': 'proj-1', 'members': []}],
        })

        project_ops.get('proj-1', include_members=True)

        project_ops._request.assert_called_once_with(
            'get', '/projects',
            params={'project_id': 'proj-1', 'limit': 2, 'include_members': True})

    def test_no_flags_sends_no_params(self, project_ops):
        project_ops._request = MagicMock(return_value={
            'total': 1,
            'items': [{'unique_id': '0tkn2knjast3h0008nyq9zps2c', 'project_id': 'proj-1'}],
        })

        project_ops.get('proj-1')

        project_ops._request.assert_called_once_with(
            'get', '/projects', params={'project_id': 'proj-1', 'limit': 2})

    def test_both_flags_combine(self, project_ops):
        project_ops._request = MagicMock(return_value={
            'total': 1,
            'items': [{'unique_id': '0tkn2knjast3h0008nyq9zps2c', 'project_id': 'proj-1'}],
        })

        project_ops.get('proj-1', include_metadata=True, include_members=True)

        project_ops._request.assert_called_once_with(
            'get', '/projects', params={
                'project_id': 'proj-1',
                'limit': 2,
                'include_metadata': True,
                'include_members': True,
            })


class TestProjectUpdateNoIdentifierCollision:
    def test_project_id_field_and_identifier_coexist(self, project_ops):
        project_ops._request = MagicMock(return_value={'project_id': 'new-slug'})

        result = project_ops.update('old-slug', project_id='new-slug')

        project_ops._request.assert_called_once_with(
            'patch', '/projects/old-slug', json={'project_id': 'new-slug'})
        assert result['project_id'] == 'new-slug'
