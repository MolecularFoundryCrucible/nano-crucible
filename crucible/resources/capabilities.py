"""Reusable resource capabilities backed by generic API endpoints."""

from typing import Dict, List, Optional

from ..utils.deprecation import _deprecated


class AccessControlMixin:
    """Access-control operations for resources that support generic ACLs."""

    @_deprecated("list_access()")
    def get_access_groups(self, mfid: str) -> List[str]:
        """Return the names of access groups granted access to a resource."""
        groups = self._request('get', f'/resources/{mfid}/access_groups')
        return [group['group_name'] for group in groups]

    @_deprecated("set_access()")
    def add_access_group(self, mfid: str, group_name: str,
                         read: bool = True, write: bool = False) -> Dict:
        """Grant an access group read and optionally write access."""
        params = {'group_name': group_name, 'read': read, 'write': write}
        return self._request('post', f'/resources/{mfid}/access_groups', params=params)

    def list_access(self, mfid: str) -> List['AccessGrant']:
        """List every principal with access to a resource."""
        from ..models import AccessGrant

        raw = self._request('get', f'/resources/{mfid}/access')
        return [AccessGrant.model_validate(grant) for grant in raw]

    def set_access(self, mfid: str, kind: str, principal: str,
                   permission: str) -> 'AccessGrant':
        """Grant or change a principal's non-owner access to a resource."""
        from ..models import AccessGrant

        allowed = {'viewer', 'contributor', 'editor', 'admin'}
        if permission not in allowed:
            if permission == 'owner':
                raise ValueError("Use transfer_ownership() to assign ownership.")
            raise ValueError(f"permission must be one of: {', '.join(sorted(allowed))}")
        raw = self._request(
            'put',
            f'/resources/{mfid}/access/{kind}/{principal}',
            json={'permission': permission},
        )
        return AccessGrant.model_validate(raw)

    def revoke_access(self, mfid: str, kind: str, principal: str) -> Dict:
        """Revoke a principal's access to a resource."""
        return self._request('delete', f'/resources/{mfid}/access/{kind}/{principal}')

    def publish(self, resource_mfid: str) -> 'AccessGrant':
        """Grant public viewer access to a resource."""
        from ..models import AccessGrant

        raw = self._request('put', f'/resources/{resource_mfid}/access/public')
        return AccessGrant.model_validate(raw)

    def unpublish(self, resource_mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self._request('delete', f'/resources/{resource_mfid}/access/public')

    @_deprecated("publish()")
    def set_public(self, mfid: str) -> 'AccessGrant':
        """Grant public viewer access to a resource."""
        return self.publish(mfid)

    @_deprecated("unpublish()")
    def unset_public(self, mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self.unpublish(mfid)


class OwnershipMixin:
    """Ownership-transfer operations for resources with an exclusive owner."""

    def transfer_ownership(self, mfid: str, new_owner: str,
                           confirm: bool = False) -> 'OwnershipTransfer':
        """Preview or apply a resource ownership transfer."""
        from ..models import OwnershipTransfer

        raw = self._request(
            'post',
            f'/resources/{mfid}/transfer_ownership',
            params={'confirm': confirm},
            json={'new_owner': new_owner},
        )
        return OwnershipTransfer.model_validate(raw)


class ProjectAssignmentMixin:
    """Project-reassignment operations for project-scoped resources."""

    def reassign_project(self, mfid: str, project_id: str,
                         confirm: bool = False) -> 'ProjectReassignment':
        """Preview or apply reassignment to another project."""
        from ..models import ProjectReassignment

        raw = self._request(
            'post',
            f'/resources/{mfid}/project',
            params={'confirm': confirm},
            json={'project_id': project_id},
        )
        return ProjectReassignment.model_validate(raw)


class InstrumentAssignmentMixin:
    """Instrument-assignment operations for instrument-scoped resources."""

    def assign_instrument(self, mfid: str, instrument_id: Optional[str] = None,
                          instrument_mfid: Optional[str] = None) -> 'InstrumentAssignment':
        """Assign or reassign the dataset's instrument, by slug or MFID.

        Sets instrument_id, instrument_mfid, and instrument_name together from
        the resolved instrument, and grants the instrument's access group
        contributor on the dataset. Reassignment drops the outgoing
        instrument's grant only. Requires manage_acl on the dataset.

        instrument_name is not settable: it is a label derived from the
        instrument, so the server always overwrites it.

        Args:
            mfid: Dataset MFID.
            instrument_id: Registered instrument slug.
            instrument_mfid: Canonical instrument MFID. If both are given they
                must identify the same instrument (422 otherwise).

        Returns:
            InstrumentAssignment: the new instrument plus what it replaced.

        Example:
            >>> client.datasets.assign_instrument("<dataset-mfid>", instrument_id="xrd-1")
        """
        from ..models import InstrumentAssignment

        if instrument_id is None and instrument_mfid is None:
            raise ValueError("Provide instrument_id or instrument_mfid")
        body = {k: v for k, v in (('instrument_id', instrument_id),
                                  ('instrument_mfid', instrument_mfid)) if v is not None}
        raw = self._request('put', f'/datasets/{mfid}/instrument', json=body)
        return InstrumentAssignment.model_validate(raw)
