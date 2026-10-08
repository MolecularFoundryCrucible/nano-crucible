#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Account resource operations — self-service endpoints for the authenticated caller.

All methods operate on the caller's own account via Bearer token.
For admin operations on other users, use UserOperations (client.users).
"""

import logging
from typing import Dict, List, Optional

from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..models import JoinRequest

logger = logging.getLogger(__name__)


class AccountOperations(BaseResource):
    """Self-service account operations.

    Access via: client.account.profile(), client.account.api_key(), etc.
    All methods require a valid API key but do not require admin permissions.
    """

    def whoami(self) -> Dict:
        """Return full auth context for the current API key.

        Returns ORCID, access group list, and user profile in one response.
        For just the user profile use account.profile().

        Returns:
            Dict: user_unique_id, access_group_ids, user_info (UserRead)
        """
        return self._request('get', '/account')

    def profile(self, privilege_mode: Optional[str] = None) -> Dict:
        """Return the authenticated caller's own user profile.

        Args:
            privilege_mode: Per-call privilege mode. The capability flags
                describe the authority of the mode they were fetched under.

        Returns:
            Dict: UserRead with unique_id, username, first_name, last_name, and
                  email, plus the authorization and capabilities blocks.
        """
        return self._request('get', '/account/profile',
                             privilege_mode=privilege_mode)

    def update_profile(self, **kwargs) -> Dict:
        """Partially update the authenticated caller's own profile.

        Accepted fields: first_name, last_name, email, username.
        Pass username=None to clear the username.
        Account type cannot be changed through profile updates.

        Returns:
            Dict: Updated UserRead profile
        """
        if 'is_service_account' in kwargs:
            raise ValueError("is_service_account cannot be changed through account profile updates.")
        return self._request('patch', '/account/profile', json=kwargs)

    def api_key(self) -> str:
        """Return the caller's own API key.

        Raises:
            HTTPError 404: No API key exists for this account yet.

        Returns:
            str: The caller's API key
        """
        result = self._request('get', '/account/apikey')
        return result['api_key']

    def verify(self) -> Dict:
        """Return the validity and expiry info for the caller's API key.

        Returns:
            Dict: {valid: bool, created_at: str, expires_at: str}
        """
        return self._request('get', '/account/verify')

    def sync_projects(self) -> Dict:
        """Refresh the caller's project memberships from the MF proposal database.

        Additive — projects are only ever added, never removed.

        Returns:
            Dict: {orcid, projects_added, projects_already_member, projects_not_found}
        """
        return self._request('post', '/account/sync-projects')

    def join_requests(self, status: Optional[str] = None,
                      limit: int = DEFAULT_LIMIT, offset: int = 0) -> List[Dict]:
        """Return the caller's own join-request history, across all groups.

        Args:
            status: Filter by "pending", "approved", or "rejected".
            limit: Maximum number of results.
            offset: Starting position in the full result set.

        Returns:
            List[Dict]: JoinRequest records where requester_id == caller.
        """
        params = {}
        if status is not None:
            params['status'] = status
        raw = self._paginate('/account/join_requests', params, limit, offset)
        return [JoinRequest(**r).model_dump() for r in raw]
