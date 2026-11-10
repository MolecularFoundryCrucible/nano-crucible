#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project join-request operations.

Lets a user request to join a project, follow and withdraw the request, and
lets anyone who may add members to the project (editors and above, and
platform admins) review it. Join requests are a flat collection with their
own int id, modeled after DeletionRequest, not a primary content resource.
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Union

import requests

from .base import BaseResource, ListResult
from ..constants import (DEFAULT_LIMIT, JOIN_REQUEST_FACET_FIELDS,
                         JOIN_REQUEST_SCOPES, JOIN_REQUEST_SORTS,
                         JOIN_REQUEST_STATUSES, PROJECT_MEMBER_ROLES,
                         SORT_DIRECTIONS)
from ..models import FacetResponse, JoinRequest
from ..utils.deprecation import _removed_parameter

TimeBound = Union[str, date, datetime]


class AccessGroupOperations(BaseResource):
    """Operations for the project join-request workflow.

    Access via: client.access_groups.*
    """

    @staticmethod
    def _parse(data: dict) -> Dict:
        return JoinRequest(**data).model_dump()

    @_removed_parameter('group_name', 'project_ref')
    def request_join(self, project_ref: str, reason: Optional[str] = None) -> Dict:
        """Request to join a project. Any signed-in user who is not a member.

        Args:
            project_ref: Project slug (project_id) or MFID.
            reason: Optional explanation for the request (at most 2000 characters).

        Returns:
            Dict: The created JoinRequest record (status will be "pending").

        Raises:
            HTTPError 404: Project doesn't exist.
            HTTPError 409: Already a member, already has a pending request
                for this project, has too many pending requests, or the
                project is pending deletion.
        """
        body = {'reason': reason} if reason is not None else {}
        raw = self._request('post', f'/projects/{project_ref}/join_requests', json=body)
        return self._parse(raw)

    def _filter_params(self, scope, status, project_mfid, group_name,
                       requester_id, reviewer_id, requested_after,
                       requested_before, reviewed_after, reviewed_before,
                       q) -> dict:
        if group_name is not None:
            from ..errors import RemovedError
            from ..utils.deprecation import removed_message
            raise RemovedError(removed_message(
                "The 'group_name' keyword of list_join_requests()", "use 'project_mfid' instead."))
        statuses = [status] if isinstance(status, str) else list(status or [])
        for value in statuses:
            if value not in JOIN_REQUEST_STATUSES:
                raise ValueError(
                    f"status must be one of: {', '.join(JOIN_REQUEST_STATUSES)}.")
        params = self._choice_params(scope=(scope, JOIN_REQUEST_SCOPES))
        if statuses:
            params['status'] = statuses
        if project_mfid is not None:
            params['project_mfid'] = project_mfid
        if requester_id is not None:
            params['requester_id'] = requester_id
        if reviewer_id is not None:
            params['reviewer_id'] = reviewer_id
        if q is not None:
            params['q'] = q
        params.update(self._time_range_params(
            requested_after=requested_after, requested_before=requested_before,
            reviewed_after=reviewed_after, reviewed_before=reviewed_before))
        return params

    def _list_mode(self, scope, privilege_mode):
        if privilege_mode is not None or scope == 'submitted':
            return privilege_mode
        return self._client._admin_mode()

    def list_join_requests(self, group_name: Optional[str] = None,
                           status: Optional[Union[str, Sequence[str]]] = None,
                           requester_id: Optional[str] = None,
                           limit: int = DEFAULT_LIMIT, offset: int = 0,
                           privilege_mode: Optional[str] = None,
                           cursor: Optional[str] = None,
                           scope: Optional[str] = None,
                           project_mfid: Optional[Union[str, Sequence[str]]] = None,
                           reviewer_id: Optional[str] = None,
                           requested_after: Optional[TimeBound] = None,
                           requested_before: Optional[TimeBound] = None,
                           reviewed_after: Optional[TimeBound] = None,
                           reviewed_before: Optional[TimeBound] = None,
                           q: Optional[str] = None,
                           sort: Optional[str] = None,
                           direction: Optional[str] = None) -> List[Dict]:
        """List join requests visible to the caller.

        Args:
            group_name: Removed in 4.0.0; passing it raises RemovedError. Use project_mfid.
            status: One status or a list of them, from
                crucible.constants.JOIN_REQUEST_STATUSES.
            requester_id: Only requests by this user (ORCID or MFID).
            limit: Maximum number of results (default 100, max 1000).
            offset: Starting position in the full result set.
            privilege_mode: Per-call privilege mode. Defaults to elevated
                for callers who can elevate, except with scope "submitted".
            cursor (str, optional): Continuation token from a previous
                result's next_cursor; the listing resumes there.
            scope: One of crucible.constants.JOIN_REQUEST_SCOPES. The server
                defaults to "accessible" (your own requests plus those you
                may review); "submitted" returns only yours and "reviewable"
                only those you may review.
            project_mfid: One project MFID or a list of them.
            reviewer_id: Only requests closed by this user.
            requested_after: Only requests made at or after this time
                (datetime, date, or ISO 8601 string; naive values are UTC).
            requested_before: Only requests made before this time.
            reviewed_after: Only requests closed at or after this time.
            reviewed_before: Only requests closed before this time.
            q: Matches the requester's name, username, or ORCID.
            sort: One of crucible.constants.JOIN_REQUEST_SORTS
                (server default: request_time).
            direction: "asc" or "desc" (server default: desc).

        Returns:
            List[Dict]: Matching JoinRequest records.
        """
        params = self._filter_params(
            scope, status, project_mfid, group_name, requester_id, reviewer_id,
            requested_after, requested_before, reviewed_after, reviewed_before, q)
        params.update(self._choice_params(
            sort=(sort, JOIN_REQUEST_SORTS), direction=(direction, SORT_DIRECTIONS)))
        raw = self._paginate('/join_requests', params, limit, offset,
                             privilege_mode=self._list_mode(scope, privilege_mode),
                             cursor=cursor)
        return ListResult.like(raw, [self._parse(r) for r in raw])

    def join_request_facets(self, field: str, limit: int = 50,
                            scope: Optional[str] = None,
                            status: Optional[Union[str, Sequence[str]]] = None,
                            project_mfid: Optional[Union[str, Sequence[str]]] = None,
                            requester_id: Optional[str] = None,
                            reviewer_id: Optional[str] = None,
                            requested_after: Optional[TimeBound] = None,
                            requested_before: Optional[TimeBound] = None,
                            reviewed_after: Optional[TimeBound] = None,
                            reviewed_before: Optional[TimeBound] = None,
                            q: Optional[str] = None,
                            privilege_mode: Optional[str] = None) -> Dict:
        """Count join requests by status, project, or requester.

        Takes the same scope and filters as list_join_requests(). Buckets
        are ordered by count, largest first.

        Args:
            field: One of crucible.constants.JOIN_REQUEST_FACET_FIELDS.
            limit: Maximum number of buckets (default 50, max 200).

        Returns:
            Dict: field, items (buckets with value, label, count, and a
                  project or requester reference where applicable), limit.
        """
        if field not in JOIN_REQUEST_FACET_FIELDS:
            raise ValueError(
                f"field must be one of: {', '.join(JOIN_REQUEST_FACET_FIELDS)}.")
        params = self._filter_params(
            scope, status, project_mfid, None, requester_id, reviewer_id,
            requested_after, requested_before, reviewed_after, reviewed_before, q)
        params.update(field=field, limit=limit)
        raw = self._request('get', '/join_requests/facets', params=params,
                            privilege_mode=self._list_mode(scope, privilege_mode))
        return FacetResponse.model_validate(raw).model_dump()

    def get(self, request_id: int) -> Optional[Dict]:
        """Fetch a single join request by ID.

        Visible to its requester, to those who may review it, and to
        platform admins.

        Args:
            request_id: Integer id of the JoinRequest.

        Returns:
            Dict: The JoinRequest record, or None if it does not exist or
                is not visible to the caller.
        """
        try:
            raw = self._request('get', f'/join_requests/{request_id}',
                                privilege_mode=self._client._admin_mode())
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise
        return self._parse(raw)

    def approve_join_request(self, request_id: int, reviewer_notes: Optional[str] = None,
                             role: Optional[str] = None) -> Dict:
        """Approve a pending join request. Project editors and above, or admin.

        On approval, the requester is added to the project at ``role``.

        Args:
            request_id: Integer id of the JoinRequest to approve.
            reviewer_notes: Optional notes explaining the decision.
            role: Role to grant, one of crucible.constants.PROJECT_MEMBER_ROLES
                and strictly below your own role in the project. The server
                defaults to contributor.

        Returns:
            Dict: The updated JoinRequest record.

        Raises:
            HTTPError 403: Not allowed to review, or the role is not below yours.
            HTTPError 409: Request is already closed, or the project is gone
                or pending deletion.
        """
        if role is not None and role not in PROJECT_MEMBER_ROLES:
            raise ValueError(f"role must be one of: {', '.join(PROJECT_MEMBER_ROLES)}.")
        return self._review(request_id, status='approved',
                            reviewer_notes=reviewer_notes, role=role)

    def reject_join_request(self, request_id: int, reviewer_notes: Optional[str] = None) -> Dict:
        """Reject a pending join request. Project editors and above, or admin.

        No membership change occurs.

        Args:
            request_id: Integer id of the JoinRequest to reject.
            reviewer_notes: Optional notes explaining the decision.

        Returns:
            Dict: The updated JoinRequest record.

        Raises:
            HTTPError 409: Request is already closed.
        """
        return self._review(request_id, status='rejected', reviewer_notes=reviewer_notes)

    def withdraw_join_request(self, request_id: int) -> Dict:
        """Withdraw your own pending join request.

        Args:
            request_id: Integer id of the JoinRequest to withdraw.

        Returns:
            Dict: The updated JoinRequest record (status "withdrawn").

        Raises:
            HTTPError 403: Only the requester can withdraw.
            HTTPError 409: Request is already closed.
        """
        raw = self._request('post', f'/join_requests/{request_id}/withdraw')
        return self._parse(raw)

    def _review(self, request_id: int, status: str,
                reviewer_notes: Optional[str] = None,
                role: Optional[str] = None) -> Dict:
        """Internal: send a review decision to the API."""
        body = {'status': status}
        if role is not None:
            body['role'] = role
        if reviewer_notes is not None:
            body['reviewer_notes'] = reviewer_notes
        raw = self._request('patch', f'/join_requests/{request_id}', json=body,
                            privilege_mode=self._client._admin_mode())
        return self._parse(raw)
