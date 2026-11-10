"""Reusable resource capabilities backed by generic API endpoints."""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..utils.deprecation import _removed

if TYPE_CHECKING:
    from ..models import (
        AccessGrant,
        InstrumentAssignment,
        OwnershipTransfer,
        ProjectReassignment,
    )


class AccessControlMixin:
    """Access-control operations for resources that support generic ACLs.

    The /resources/{mfid}/... routes accept only MFIDs. Every method passes
    its reference through ``_resource_mfid()`` (see BaseResource), which
    resources with human-readable slugs override to resolve them.
    """

    _request: Callable[..., Any]
    _resource_mfid: Callable[[str], str]

    @_removed("use list_access() instead.")
    def get_access_groups(self, *args, **kwargs):
        """Removed in 4.0.0: use list_access() instead."""

    @_removed("use set_access() instead.")
    def add_access_group(self, *args, **kwargs):
        """Removed in 4.0.0: use set_access() instead."""

    def list_access(self, mfid: str) -> List['AccessGrant']:
        """List every principal with access to a resource.

        Readable by anyone with a role on the resource (not through public
        access alone); the resource's ``capabilities.can_view_access`` says
        whether you can. Each grant's ``capabilities`` says whether you may
        remove it or change its role, and to which roles.
        """
        from ..models import AccessGrant

        raw = self._request('get', f'/resources/{self._resource_mfid(mfid)}/access')
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
            f'/resources/{self._resource_mfid(mfid)}/access/{kind}/{principal}',
            json={'permission': permission},
        )
        return AccessGrant.model_validate(raw)

    def revoke_access(self, mfid: str, kind: str, principal: str) -> Dict:
        """Revoke a principal's access to a resource."""
        return self._request('delete', f'/resources/{self._resource_mfid(mfid)}/access/{kind}/{principal}')

    def set_public(self, mfid: str) -> 'AccessGrant':
        """Grant public viewer access to a resource."""
        from ..models import AccessGrant

        raw = self._request('put', f'/resources/{self._resource_mfid(mfid)}/access/public')
        return AccessGrant.model_validate(raw)

    def set_private(self, mfid: str) -> Dict:
        """Revoke public access to a resource."""
        return self._request('delete', f'/resources/{self._resource_mfid(mfid)}/access/public')

    @_removed("use set_public() instead.")
    def publish(self, *args, **kwargs):
        """Removed in 4.0.0: use set_public() instead."""

    @_removed("use set_private() instead.")
    def unpublish(self, *args, **kwargs):
        """Removed in 4.0.0: use set_private() instead."""

    @_removed("use set_private() instead.")
    def unset_public(self, *args, **kwargs):
        """Removed in 4.0.0: use set_private() instead."""


class OwnershipMixin:
    """Ownership-transfer operations for resources with an exclusive owner."""

    _request: Callable[..., Any]
    _resource_mfid: Callable[[str], str]

    def transfer_ownership(self, mfid: str, new_owner: str,
                           confirm: bool = False) -> 'OwnershipTransfer':
        """Preview or apply a resource ownership transfer."""
        from ..models import OwnershipTransfer

        raw = self._request(
            'post',
            f'/resources/{self._resource_mfid(mfid)}/transfer_ownership',
            params={'confirm': confirm},
            json={'new_owner': new_owner},
        )
        return OwnershipTransfer.model_validate(raw)


class ProjectAssignmentMixin:
    """Project-reassignment operations for project-scoped resources."""

    _request: Callable[..., Any]
    _resource_mfid: Callable[[str], str]

    def reassign_project(self, mfid: str, project_id: Optional[str] = None,
                         confirm: bool = False, *,
                         project_mfid: Optional[str] = None) -> 'ProjectReassignment':
        """Preview or apply reassignment to another project.

        Args:
            mfid: Resource MFID.
            project_id: Target project slug.
            confirm: False previews the reassignment, True applies it.
            project_mfid: Target project MFID; preferred over project_id.
        """
        from ..models import ProjectReassignment

        provided = [value for value in (project_id, project_mfid)
                    if value is not None]
        if len(provided) != 1:
            raise ValueError("Provide exactly one target project identifier.")
        body = ({'project_mfid': project_mfid} if project_mfid is not None
                else {'project_id': project_id})
        raw = self._request(
            'post',
            f'/resources/{self._resource_mfid(mfid)}/project',
            params={'confirm': confirm},
            json=body,
        )
        return ProjectReassignment.model_validate(raw)


class InstrumentAssignmentMixin:
    """Instrument-assignment operations for instrument-scoped resources."""

    _request: Callable[..., Any]

    def assign_instrument(self, dataset_mfid: str, instrument_id: Optional[str] = None,
                          instrument_mfid: Optional[str] = None) -> 'InstrumentAssignment':
        """Assign or reassign the dataset's instrument, by slug or MFID.

        Sets instrument_id, instrument_mfid, and instrument_name together from
        the resolved instrument, and grants the instrument's access group
        contributor on the dataset. Reassignment drops the outgoing
        instrument's grant only. Requires manage_acl on the dataset.

        instrument_name is not settable: it is a label derived from the
        instrument, so the server always overwrites it.

        Args:
            dataset_mfid: Dataset MFID.
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
        raw = self._request('put', f'/datasets/{dataset_mfid}/instrument', json=body)
        return InstrumentAssignment.model_validate(raw)
