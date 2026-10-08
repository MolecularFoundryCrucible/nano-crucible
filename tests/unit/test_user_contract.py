"""Unit coverage for human-user creation and canonical identity behavior."""

from unittest.mock import MagicMock

import pytest

from crucible.models import User
from crucible.resources.account import AccountOperations
from crucible.resources.users import UserOperations


USER_MFID = '0tkvpezyz1zzf00076nahf85j4'


def make_ops(response=None):
    operations = UserOperations(MagicMock())
    operations._request = MagicMock(return_value=response or {})
    return operations


def test_create_can_omit_orcid_and_sends_required_username():
    operations = make_ops({
        'unique_id': USER_MFID,
        'username': 'test-user-one',
        'first_name': 'Test',
        'last_name': 'User One',
        'is_service_account': False,
    })

    result = operations.create(User(
        username='test-user-one',
        first_name='Test',
        last_name='User One',
    ))

    operations._request.assert_called_once_with(
        'post',
        '/users',
        json={
            'user_info': {
                'username': 'test-user-one',
                'first_name': 'Test',
                'last_name': 'User One',
            },
            'project_ids': [],
        },
    )
    assert result['unique_id'] == USER_MFID
    assert result['is_service_account'] is False


def test_create_rejects_service_account_discriminator():
    operations = make_ops()

    with pytest.raises(ValueError, match='cannot be supplied'):
        operations.create(User(
            username='test-user-one',
            first_name='Test',
            last_name='User One',
            is_service_account=False,
        ))

    operations._request.assert_not_called()


def test_create_requires_username():
    operations = make_ops()

    with pytest.raises(ValueError, match='username'):
        operations.create(User(first_name='Test', last_name='User One'))

    operations._request.assert_not_called()


def test_create_normalizes_username_before_request():
    operations = make_ops()

    operations.create({
        'username': '  Test-User-One  ',
        'first_name': 'Test',
        'last_name': 'User One',
    })

    assert operations._request.call_args.kwargs['json']['user_info']['username'] == 'test-user-one'


@pytest.mark.parametrize('username', ['ab', '1test-user', 'test--user', 'a' * 25])
def test_create_rejects_invalid_username(username):
    operations = make_ops()

    with pytest.raises(ValueError, match='Username must be 3 to 24 characters'):
        operations.create({
            'username': username,
            'first_name': 'Test',
            'last_name': 'User One',
        })

    operations._request.assert_not_called()


def test_update_rejects_service_account_conversion():
    operations = make_ops()

    with pytest.raises(ValueError, match='cannot be changed'):
        operations.update(USER_MFID, is_service_account=True)

    operations._request.assert_not_called()


def test_update_keeps_orcid_keyword_as_deprecated_alias():
    operations = make_ops({'unique_id': USER_MFID, 'username': 'test-user-one'})

    with pytest.warns(DeprecationWarning, match='user_unique_id'):
        operations.update(orcid=USER_MFID, username='updated-user')

    operations._request.assert_called_once_with(
        'patch', f'/users/{USER_MFID}', json={'username': 'updated-user'})


def test_batch_resolve_uses_canonical_user_ids_with_legacy_wire_field():
    operations = make_ops({USER_MFID: {'unique_id': USER_MFID}})

    operations.resolve(user_unique_ids=[USER_MFID])

    operations._request.assert_called_once_with(
        'post', '/users/resolve', json={'orcids': [USER_MFID]})


def test_batch_resolve_keeps_orcids_keyword_as_deprecated_alias():
    operations = make_ops({USER_MFID: {'unique_id': USER_MFID}})

    with pytest.warns(DeprecationWarning, match='user_unique_ids'):
        operations.resolve(orcids=[USER_MFID])


def test_account_update_rejects_service_account_conversion():
    operations = AccountOperations(MagicMock())
    operations._request = MagicMock()

    with pytest.raises(ValueError, match='cannot be changed'):
        operations.update_profile(is_service_account=True)

    operations._request.assert_not_called()


def test_set_platform_role_sends_patch_with_elevated_privilege():
    operations = make_ops({'unique_id': USER_MFID, 'platform_role': 'contributor'})

    operations.set_platform_role(USER_MFID, 'contributor')

    operations._request.assert_called_once_with(
        'patch',
        f'/users/{USER_MFID}/platform_role',
        json={'platform_role': 'contributor'},
        privilege_mode='elevated',
    )


def test_set_platform_role_rejects_support_role():
    operations = make_ops()

    with pytest.raises(ValueError, match='none, contributor, admin'):
        operations.set_platform_role(USER_MFID, 'support')

    operations._request.assert_not_called()


def test_revoke_api_keys_sends_delete_with_elevated_privilege():
    operations = make_ops()

    assert operations.revoke_api_keys(USER_MFID) is None

    operations._request.assert_called_once_with(
        'delete',
        f'/users/{USER_MFID}/apikey',
        privilege_mode='elevated',
    )


def make_listing_ops():
    operations = UserOperations(MagicMock())
    operations._paginate = MagicMock(return_value=[])
    return operations


def test_list_passes_explicit_filters_with_scalar_normalization():
    operations = make_listing_ops()

    operations.list(username='alice', platform_role='admin',
                    q='ali', search_fields='username', is_service_account=False)

    operations._paginate.assert_called_once_with('/users', {
        'q': 'ali',
        'username': 'alice',
        'platform_role': ['admin'],
        'search_fields': ['username'],
        'is_service_account': False,
    }, 100, 0)


def test_list_rejects_unknown_platform_role():
    operations = make_listing_ops()

    with pytest.raises(ValueError, match='platform_role'):
        operations.list(platform_role='superadmin')

    operations._paginate.assert_not_called()


def test_list_requires_q_with_search_fields():
    operations = make_listing_ops()

    with pytest.raises(ValueError, match='search_fields requires q'):
        operations.list(search_fields='username')

    operations._paginate.assert_not_called()


def test_list_omits_unset_filters():
    operations = make_listing_ops()

    operations.list()

    operations._paginate.assert_called_once_with('/users', {}, 100, 0)
