#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Access group join-request operations.

Lets a user request to join an access group (currently only projects produce
these) and lets admins/group leads review the request. Join requests are a
flat, admin/lead-reviewed collection with their own int id — modeled after
DeletionRequest, not a primary content resource.
"""

from typing import Dict, List, Optional

from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..models import JoinRequest


class AccessGroupOperations(BaseResource):
    """Operations for the access-group join-request workflow.

    Access via: client.access_groups.*
    """

    @staticmethod
    def _parse(data: dict) -> Dict:
        return JoinRequest(**data).model_dump()

    def request_join(self, group_name: str, reason: Optional[str] = None) -> Dict:
        """Request to join an access group. Any authenticated user.

        Args:
            group_name: Name of the access group to join (currently always a project_id).
            reason: Optional explanation for the request.

        Returns:
            Dict: The created JoinRequest record (status will be "pending").

        Raises:
            HTTPError 404: Group/project doesn't exist.
            HTTPError 409: Already a member, or already has a pending request for this group.
        """
        body = {'reason': reason}
        raw = self._request('post', f'/access_groups/{group_name}/join', json=body)
        return self._parse(raw)

    def list_join_requests(self, group_name: Optional[str] = None,
                           status: Optional[str] = None,
                           requester_id: Optional[str] = None,
                           limit: int = DEFAULT_LIMIT, offset: int = 0,
                           privilege_mode: Optional[str] = None) -> List[Dict]:
        """List join requests. Admin, or the lead of the given group_name.

        Args:
            group_name: Filter to one group. Required for a non-admin lead to
                        get any results back — omitting it requires admin.
            status: Filter by "pending", "approved", or "rejected".
            requester_id: Filter to one user's requests (admin use).
            limit: Maximum number of results (default 100, max 1000).
            offset: Starting position in the full result set.
            privilege_mode: Per-call privilege mode.

        Returns:
            List[Dict]: Matching JoinRequest records, most recent first.

        Raises:
            HTTPError 403: Caller is neither admin nor lead of group_name.
        """
        params = {}
        if group_name is not None:
            params['group_name'] = group_name
        if status is not None:
            params['status'] = status
        if requester_id is not None:
            params['requester_id'] = requester_id
        raw = self._paginate('/join_requests', params, limit, offset,
                             privilege_mode=privilege_mode)
        return [self._parse(r) for r in raw]

    def get(self, request_id: int) -> Optional[Dict]:
        """Fetch a single join request by ID. Admin only.

        There is no dedicated single-record endpoint — this scans the admin
        list view (GET /join_requests, no group_name) and filters by id.
        A group lead who is not also admin cannot use this; use
        list_join_requests(group_name=...) instead.

        Args:
            request_id: Integer id of the JoinRequest.

        Returns:
            Dict: The JoinRequest record, or None if not found.

        Raises:
            HTTPError 403: Caller is not admin.
        """
        for r in self.list_join_requests(limit=1000,
                                         privilege_mode=self._client._admin_mode()):
            if r.get('id') == request_id:
                return r
        return None

    def approve_join_request(self, request_id: int, reviewer_notes: Optional[str] = None) -> Dict:
        """Approve a pending join request. Admin or lead of the request's group.

        On approval, the requester is added to the group's membership and access group.

        Args:
            request_id: Integer id of the JoinRequest to approve.
            reviewer_notes: Optional notes explaining the decision.

        Returns:
            Dict: The updated JoinRequest record.

        Raises:
            HTTPError 409: Request has already been reviewed.
        """
        return self._review(request_id, status='approved', reviewer_notes=reviewer_notes)

    def reject_join_request(self, request_id: int, reviewer_notes: Optional[str] = None) -> Dict:
        """Reject a pending join request. Admin or lead of the request's group.

        No membership change occurs.

        Args:
            request_id: Integer id of the JoinRequest to reject.
            reviewer_notes: Optional notes explaining the decision.

        Returns:
            Dict: The updated JoinRequest record.

        Raises:
            HTTPError 409: Request has already been reviewed.
        """
        return self._review(request_id, status='rejected', reviewer_notes=reviewer_notes)

    def _review(self, request_id: int, status: str,
               reviewer_notes: Optional[str] = None) -> Dict:
        """Internal: send a review decision to the API."""
        body = {'status': status}
        if reviewer_notes is not None:
            body['reviewer_notes'] = reviewer_notes
        raw = self._request('patch', f'/join_requests/{request_id}', json=body)
        return self._parse(raw)
