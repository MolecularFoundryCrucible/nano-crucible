#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletion request operations for the Crucible API.

Provides the soft-deletion workflow: users submit deletion requests via
POST /resources/{id}/delete, admins approve or reject them via /deletion_requests endpoints.
"""

from typing import Dict, List, Optional

from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..models import DeletionRequest, DeletionAuditLog


class DeletionOperations(BaseResource):
    """Operations for the soft-deletion approval workflow."""

    @staticmethod
    def _parse(data: dict) -> Dict:
        return DeletionRequest(**data).model_dump()

    def request(self, resource_id: str, reason: Optional[str] = None) -> Dict:
        """Submit a deletion request for a dataset or sample.

        The resource is immediately hidden from list results (status: pending)
        until an admin approves or rejects the request.

        Args:
            resource_id: The unique_id (MFID) of the dataset or sample to delete.
            reason: Optional explanation for why deletion is requested.

        Returns:
            Dict: The created DeletionRequest record.
        """
        params = {}
        if reason is not None:
            params["reason"] = reason
        raw = self._request("post", f"/resources/{resource_id}/delete", params=params or None)
        return self._parse(raw)

    def list(self, status: Optional[str] = None, limit: int = DEFAULT_LIMIT,
             offset: int = 0) -> List[Dict]:
        """List deletion requests. Admin only.

        Args:
            status: Filter by status — "pending", "approved", or "rejected".
                    Omit to return all requests.
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)

        Returns:
            List[Dict]: Matching DeletionRequest records.
        """
        params = {}
        if status is not None:
            params["status"] = status
        raw = self._paginate("/deletion_requests", params, limit, offset)
        return [self._parse(r) for r in raw]

    def get(self, request_id: int) -> Dict:
        """Fetch a single deletion request by ID. Admin only.

        Args:
            request_id: Integer ID of the DeletionRequest row.

        Returns:
            Dict: The DeletionRequest record.
        """
        raw = self._request("get", f"/deletion_requests/{request_id}")
        return self._parse(raw)

    def approve(self, request_id: int, reviewer_notes: Optional[str] = None) -> Dict:
        """Approve a pending deletion request. Admin only.

        The resource will remain hidden (deletion_status: approved).

        Args:
            request_id: Integer ID of the DeletionRequest to approve.
            reviewer_notes: Optional notes explaining the decision.

        Returns:
            Dict: The updated DeletionRequest record.
        """
        return self._review(request_id, status="approved", reviewer_notes=reviewer_notes)

    def reject(self, request_id: int, reviewer_notes: Optional[str] = None) -> Dict:
        """Reject a pending deletion request. Admin only.

        The resource is restored to active (deletion_status set back to None).

        Args:
            request_id: Integer ID of the DeletionRequest to reject.
            reviewer_notes: Optional notes explaining the decision.

        Returns:
            Dict: The updated DeletionRequest record.
        """
        return self._review(request_id, status="rejected", reviewer_notes=reviewer_notes)

    def list_deleted(self, resource_id: Optional[str] = None,
                   requester_id: Optional[str] = None,
                   reviewer_id: Optional[str] = None,
                   limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List hard-deletion audit log entries. Admin only.

        Returns a permanent record of every resource that was hard-deleted,
        ordered by deletion time descending. Audit entries survive even after
        the original DeletionRequest and Resource rows are gone.

        Args:
            resource_id: Filter by resource MFID.
            requester_id: Filter by the ORCID of who requested deletion.
            reviewer_id: Filter by the ORCID of who approved deletion.
            limit: Maximum number of results.

        Returns:
            List[Dict]: DeletionAuditLog records.
        """
        params = {}
        if resource_id:
            params['resource_id'] = resource_id
        if requester_id:
            params['requester_id'] = requester_id
        if reviewer_id:
            params['reviewer_id'] = reviewer_id
        raw = self._paginate('/deletion_audit', params, limit=limit)
        return [DeletionAuditLog(**r).model_dump() for r in raw]

    def get_deleted(self, audit_id: int) -> Dict:
        """Get a single hard-deletion audit log entry by ID. Admin only.

        Args:
            audit_id: Integer primary key of the audit log entry.

        Returns:
            Dict: DeletionAuditLog record.

        Raises:
            HTTPError 404: Audit entry not found.
        """
        raw = self._request('get', f'/deletion_audit/{audit_id}')
        return DeletionAuditLog(**raw).model_dump()

    def delete(self, resource_id: str, force: bool = False) -> Dict:
        """Permanently delete a resource. Admin only.

        By default requires an existing approved deletion request (409 if none).
        Use force=True to bypass the workflow and hard-delete immediately.

        Args:
            resource_id: MFID of the dataset or sample to permanently delete.
            force: If True, skip the deletion request check and delete immediately.

        Returns:
            Dict: {"detail": "Resource {id} permanently deleted"}

        Raises:
            HTTPError 409: No approved deletion request exists (only when force=False).
            HTTPError 404: Resource not found.
        """
        params = {'force': True} if force else None
        return self._request('delete', f'/resources/{resource_id}', params=params)

    def _review(self, request_id: int, status: str,
                reviewer_notes: Optional[str] = None) -> Dict:
        """Internal: send a review decision to the API."""
        params = {"status": status}
        if reviewer_notes is not None:
            params["reviewer_notes"] = reviewer_notes
        raw = self._request("patch", f"/deletion_requests/{request_id}", params=params)
        return self._parse(raw)
