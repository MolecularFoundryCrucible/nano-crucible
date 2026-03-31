#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletion request operations for the Crucible API.

Provides the soft-deletion workflow: users submit deletion requests,
admins approve or reject them via /deletion_requests endpoints.
"""

from typing import Dict, List, Optional

from .base import BaseResource
from ..models import DeletionRequest


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
        params = {"resource_id": resource_id}
        if reason is not None:
            params["reason"] = reason
        raw = self._request("post", "/deletion_requests", params=params)
        return self._parse(raw)

    def list(self, status: Optional[str] = None) -> List[Dict]:
        """List deletion requests. Admin only.

        Args:
            status: Filter by status — "pending", "approved", or "rejected".
                    Omit to return all requests.

        Returns:
            List[Dict]: Matching DeletionRequest records.
        """
        params = {}
        if status is not None:
            params["status"] = status
        result = self._request("get", "/deletion_requests", params=params)
        return [self._parse(r) for r in result] if result else []

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

    def _review(self, request_id: int, status: str,
                reviewer_notes: Optional[str] = None) -> Dict:
        """Internal: send a review decision to the API."""
        params = {"status": status}
        if reviewer_notes is not None:
            params["reviewer_notes"] = reviewer_notes
        raw = self._request("patch", f"/deletion_requests/{request_id}", params=params)
        return self._parse(raw)
