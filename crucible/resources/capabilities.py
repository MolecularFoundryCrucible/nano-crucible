"""Reusable resource capabilities backed by generic API endpoints."""

from typing import Dict, List

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

    def set_public(self, mfid: str) -> 'AccessGrant':
        """Grant public viewer access to a resource."""
        from ..models import AccessGrant

        raw = self._request('put', f'/resources/{mfid}/access/public')
        return AccessGrant.model_validate(raw)

    def set_private(self, mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self._request('delete', f'/resources/{mfid}/access/public')

    @_deprecated("set_public()")
    def publish(self, mfid: str) -> 'AccessGrant':
        """Grant public viewer access to a resource."""
        return self.set_public(mfid)

    @_deprecated("set_private()")
    def unpublish(self, mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self.set_private(mfid)

    @_deprecated("set_private()")
    def unset_public(self, mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self.set_private(mfid)


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
