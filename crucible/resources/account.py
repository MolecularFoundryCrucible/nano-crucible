#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Account resource operations — self-service endpoints for the authenticated caller.

All methods operate on the caller's own account via Bearer token.
For admin operations on other users, use UserOperations (client.users).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

from .base import BaseResource, ListResult
from ..constants import API_KEY_PAGE_MAX, API_KEY_STATES, DEFAULT_LIMIT
from ..models import ApiKeyCreated, ApiKeyInfo
from ..utils.deprecation import _removed

logger = logging.getLogger(__name__)


class AccountOperations(BaseResource):
    """Self-service account operations.

    Access via: client.account.profile(), client.account.list_api_keys(), etc.
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

    @_removed("use client.account.create_api_key() instead.")
    def api_key(self, *args, **kwargs):
        """Removed in 4.0.0: use client.account.create_api_key() instead."""

    def create_api_key(self, name: str,
                       expires_at: Optional[Union[datetime, str]] = None) -> Dict:
        """Create another API key for the caller.

        Needs a recent sign-in, not an API key: a key gets 403
        hub_session_required. At most 10 keys can be active (409 too_many_keys).

        Args:
            name: What the key is for, such as the machine or script that uses
                it (1 to 100 characters).
            expires_at: When the key stops working, at most a year away; a
                year when omitted. A datetime should be timezone-aware.

        Returns:
            Dict: ApiKeyCreated. api_key holds the key and is returned only
                here, so store it now.
        """
        body = {'name': name}
        if expires_at is not None:
            body['expires_at'] = (expires_at.isoformat()
                                  if isinstance(expires_at, datetime) else expires_at)
        raw = self._request('post', '/account/apikeys', json=body,
                            retry=False, log_body=False)
        return ApiKeyCreated.model_validate(raw).model_dump()

    def list_api_keys(self, state: str = 'active', limit: Optional[int] = DEFAULT_LIMIT,
                      cursor: Optional[str] = None) -> ListResult:
        """List the caller's API keys, newest first, never the keys themselves.

        Works with an API key.

        Args:
            state: 'active', or 'inactive' for expired and revoked keys.
            limit: Maximum number of keys. None fetches all.
            cursor: Continuation token from a previous result's next_cursor.

        Returns:
            ListResult[Dict]: ApiKeyInfo records. older_routes marks the key
                the deprecated single-key routes show.
        """
        return _key_page(self, '/account/apikeys', state, limit, cursor)

    def rename_api_key(self, key_id: int, name: str) -> Dict:
        """Rename one of the caller's API keys.

        Raises:
            HTTPError 404: The key is not one of the caller's.

        Returns:
            Dict: The updated ApiKeyInfo.
        """
        raw = self._request('patch', f'/account/apikeys/{key_id}', json={'name': name})
        return ApiKeyInfo.model_validate(raw).model_dump()

    def revoke_api_key(self, key_id: int) -> None:
        """Revoke one of the caller's API keys. It stops working within a minute.

        Revoking the key this client uses ends its access too.

        Raises:
            HTTPError 404: The key is not one of the caller's.
        """
        self._request('delete', f'/account/apikeys/{key_id}')

    def verify(self) -> Dict:
        """Return the validity and expiry info for the presented API key.

        With a Hub session instead of a key, describes the newest key, with
        valid False once it has expired.

        Returns:
            Dict: {valid: bool, created_at: str, expires_at: str, last_used_at: str | None}
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
                      limit: int = DEFAULT_LIMIT,
                      offset: int = 0,
                      cursor: Optional[str] = None) -> List[Dict]:
        """Return the caller's own join-request history, across all projects.

        Same as client.access_groups.list_join_requests(scope='submitted'),
        which also takes the other filters and sorts.

        Args:
            status: One status or a list of them, from
                crucible.constants.JOIN_REQUEST_STATUSES.
            limit: Maximum number of results.
            offset: Starting position in the full result set.
            cursor (str, optional): Continuation token from a previous
                result's next_cursor; the listing resumes there.

        Returns:
            List[Dict]: JoinRequest records where requester_id == caller.
        """
        return self._client.access_groups.list_join_requests(
            scope='submitted', status=status, limit=limit, offset=offset,
            cursor=cursor)


def _key_page(resource: BaseResource, endpoint: str, state: str,
              limit: Optional[int], cursor: Optional[str],
              privilege_mode: Optional[str] = None) -> ListResult:
    if state not in API_KEY_STATES:
        raise ValueError(f"state must be one of: {', '.join(API_KEY_STATES)}.")
    raw = resource._paginate(endpoint, {'state': state}, limit, cursor=cursor,
                             privilege_mode=privilege_mode, page_max=API_KEY_PAGE_MAX)
    return ListResult.like(raw, [ApiKeyInfo.model_validate(item).model_dump() for item in raw])
