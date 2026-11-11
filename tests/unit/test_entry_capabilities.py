"""Unit coverage for per-entry capabilities on access grants and group members."""

from unittest.mock import MagicMock

from crucible.models import ResourceCapabilities
from crucible.resources.datasets import DatasetOperations
from crucible.resources.instruments import InstrumentOperations


MFID = '0tkn2knjast3h0008nyq9zps2c'
CAPS = {'can_remove': True, 'can_change_role': True, 'assignable_roles': ['viewer', 'editor']}


def test_list_access_keeps_entry_capabilities():
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value=[{
        'principal_id': '0000-0002-1825-0097', 'principal_type': 'user',
        'permission': 'contributor', 'capabilities': CAPS,
    }])

    grant = operations.list_access(MFID)[0]

    assert grant.capabilities.can_remove is True
    assert grant.capabilities.assignable_roles == ['viewer', 'editor']


def test_list_access_without_capabilities_is_none():
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value=[{
        'principal_id': 'public', 'principal_type': 'public', 'permission': 'viewer'}])

    assert operations.list_access(MFID)[0].capabilities is None


def test_instrument_service_accounts_keep_entry_capabilities():
    operations = InstrumentOperations(MagicMock())
    operations._request = MagicMock(return_value=[{
        'unique_id': MFID, 'first_name': 'Robot', 'last_name': 'Operator', 'role': 'contributor',
        'capabilities': {'can_remove': True, 'can_change_role': False, 'assignable_roles': []},
    }])

    member = operations.list_service_accounts(MFID)[0]

    assert member.capabilities.can_remove is True
    assert member.capabilities.can_change_role is False


def test_resource_capabilities_declare_view_access():
    caps = ResourceCapabilities.model_validate({
        'can_edit': False, 'can_manage_access': False, 'can_change_status': False,
        'can_transfer': False, 'can_view_access': True})

    assert caps.can_view_access is True
    assert caps.can_delete is None
