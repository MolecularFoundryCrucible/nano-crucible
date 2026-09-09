#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User resource operations for Crucible API.

Provides organized access to user-related API endpoints.
"""

import logging
from typing import Optional, Dict, List
from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..utils.deprecation import _deprecated, _deprecated_parameter
from ..utils.identifiers import (
    classify_user_reference,
    collapse_exact_lookup,
    is_mfid,
    is_orcid,
    require_canonical_identifier,
    validate_username,
)

logger = logging.getLogger(__name__)


class UserOperations(BaseResource):
    """User-related API operations.

    Access via: client.users.get(), client.users.create(), etc.
    """

    def get(self, user_ref: Optional[str] = None,
            email: Optional[str] = None, username: Optional[str] = None,
            *, orcid: Optional[str] = None,
            user_unique_id: Optional[str] = None) -> Dict:
        """Get a user by canonical unique ID, username, or email.

        Username and email references use exact collection filters and return
        the caller-authorized representation without a second request. Self
        and platform-administrator lookups may include email; other callers
        receive the public-safe representation.
        ``orcid``, ``email``, and ``username`` remain supported keyword forms.

        Args:
            user_ref (str, optional): ORCID, user MFID, username, or email
            email (str, optional): User's email address
            username (str, optional): User's username
            orcid (str, optional): Explicit person ORCID
            user_unique_id (str, optional): Explicit canonical ORCID or user MFID

        Returns:
            Dict: UserRead for a canonical lookup or the exact collection item

        Raises:
            ValueError: If no identifier or multiple identifiers are provided
        """
        provided = [
            value for value in (user_ref, email, username, orcid, user_unique_id)
            if value is not None
        ]
        if len(provided) != 1:
            raise ValueError("Provide exactly one user reference.")
        if user_unique_id is not None:
            return self._get_by_unique_id(user_unique_id)
        if orcid is not None:
            return self._get_by_unique_id(orcid)
        if username is not None:
            return self._get_by_username(username)
        if email is not None:
            return self._get_by_email(email)

        reference_kind, normalized = classify_user_reference(user_ref)
        if reference_kind == 'unique_id':
            return self._get_by_unique_id(normalized)
        if reference_kind == 'username':
            return self._get_by_username(normalized)
        return self._get_by_email(normalized)

    def _get_by_unique_id(self, unique_id: str) -> Dict:
        """Get a user by canonical ORCID or MFID."""
        if not is_orcid(unique_id) and not is_mfid(unique_id):
            raise ValueError("unique_id must be an ORCID or user MFID.")
        raw = self._request('get', f'/users/{unique_id}')
        return require_canonical_identifier(raw, 'user')

    def _get_by_username(self, username: str) -> Dict:
        """Resolve an exact username through the user collection route."""
        reference_kind, normalized = classify_user_reference(username)
        if reference_kind != 'username':
            raise ValueError("username must be a valid 3-to-24-character username.")
        raw = self._request(
            'get',
            '/users',
            params={'username': normalized, 'limit': 2},
        )
        return collapse_exact_lookup(raw, 'user', username)

    def _get_by_email(self, email: str) -> Dict:
        """Resolve an exact email through the user collection route."""
        reference_kind, normalized = classify_user_reference(email)
        if reference_kind != 'email':
            raise ValueError("email must contain '@'.")
        raw = self._request(
            'get',
            '/users',
            params={'email': normalized, 'limit': 2},
        )
        return collapse_exact_lookup(raw, 'user', email)

    def search(self, q: str, limit: int = 20) -> List[Dict]:
        """Search for users by name or username. Available to all authenticated users.

        Matches the query term against username, first name, and last name
        simultaneously (case-insensitive). Returns UserPublicRead — no email
        exposed. Hard-capped at 50 results.

        Use client.users.list() for admin-level field-specific filtering.

        Args:
            q: Search term (e.g. "fabrice", "ron")

        Returns:
            List[Dict]: Matching users (username, first_name, last_name, orcid)
        """
        result = self._request('get', '/users/search', params={'q': q, 'limit': limit})
        return result.get('items', result) if isinstance(result, dict) else result

    @_deprecated("client.account.profile()")
    def me(self) -> Dict:
        """Deprecated: use client.account.profile() instead."""
        return self._client.account.profile()

    @_deprecated("client.account.update_profile()")
    def update_me(self, **kwargs) -> Dict:
        """Deprecated: use client.account.update_profile() instead."""
        return self._client.account.update_profile(**kwargs)

    @_deprecated_parameter('orcid', 'user_unique_id')
    def verify_api_key(self, user_unique_id: str) -> Dict:
        """Verify the API key for any user. Admin only.

        Args:
            user_unique_id: Canonical user ORCID or MFID

        Returns:
            Dict: {valid: bool, created_at: str, expires_at: str}
        """
        return self._request('get', f'/users/{user_unique_id}/apikey/verify')

    @_deprecated_parameter('orcids', 'user_unique_ids')
    def resolve(self, user_unique_ids: Optional[List[str]] = None,
                usernames: Optional[List[str]] = None,
                emails: Optional[List[str]] = None) -> Dict:
        """Batch-resolve users by canonical IDs, usernames, or emails.

        Open to all authenticated users. Returns public profiles (no email).

        Args:
            user_unique_ids: List of canonical user ORCIDs or MFIDs
            usernames: List of username strings
            emails: List of email strings

        Returns:
            Dict: Mapping of canonical user ID to UserPublicRead.
        """
        body = {}
        if user_unique_ids:
            body['orcids'] = user_unique_ids
        if usernames:
            body['usernames'] = usernames
        if emails:
            body['emails'] = emails
        return self._request('post', '/users/resolve', json=body)

    def list(self, limit: int = DEFAULT_LIMIT, offset: int = 0, **kwargs) -> List[Dict]:
        """List users visible to the authenticated caller.

        Platform administrators see the full directory. Other callers see
        users who share an access group with them. Broad collection records
        are public-safe. Exact unique-ID, username, or email filters may include
        email when the caller is that user or a platform administrator.

        Args:
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Additional query parameters for filtering

        Returns:
            List[Dict]: Public-safe user records with canonical identity and name

        Example:
            >>> users = client.users.list(limit=50)
            >>> for user in users:
            ...     print(f"{user['first_name']} {user['last_name']} ({user['orcid']})")
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        users = self._paginate('/users', params, limit, offset)
        return sorted(users, key=lambda u: u.get('id') or 0)

    def create(self, user, project_ids=None) -> Dict:
        """Create a human user with an ORCID or a server-assigned MFID.

        If supplied, the ORCID must be canonical. When it is omitted, the API
        generates an MFID for the user.

        **Requires admin permissions.**

        Args:
            user: User model or dict with user information.
                  Required fields: first_name, last_name, username.
                  Optional: unique_id/orcid and email.
                  If a dict, may include a 'projects' key (list of project IDs)
                  as an alternative to the project_ids parameter.
            project_ids (list, optional): Project IDs to associate with the user.

        Returns:
            Dict: Created or updated user object

        Example:
            >>> from crucible.models import User
            >>> user = User(first_name="Jane", last_name="Doe", username="jane-doe")
            >>> new_user = client.users.create(user, project_ids=["project1"])
        """
        from ..models import User
        if isinstance(user, User):
            user_data = user.model_dump(exclude_none=True, exclude={'id'})
            user_projects = project_ids or []
        else:
            user_data = dict(user)
            user_projects = user_data.pop("projects", project_ids or [])

        if user_data.get('is_service_account') is not None:
            raise ValueError(
                "is_service_account cannot be supplied when creating a human user; "
                "use client.service_accounts.create() for service accounts."
            )
        missing = [
            field for field in ('first_name', 'last_name', 'username')
            if not user_data.get(field)
        ]
        if missing:
            raise ValueError(f"Human user creation requires: {', '.join(missing)}.")
        user_data['username'] = validate_username(user_data['username'])

        # The API accepts the legacy wire alias 'orcid' for an optional unique_id.
        if 'unique_id' in user_data:
            user_data['orcid'] = user_data.pop('unique_id')
        if user_data.get('orcid') is not None and not is_orcid(user_data['orcid']):
            raise ValueError("A supplied human unique_id must be an ORCID; omit it to generate an MFID.")

        return self._request('post', "/users", json={"user_info": user_data, "project_ids": user_projects})

    @_deprecated("client.datasets.list(accessible_to_user=...)")
    def list_datasets(self, user_ref: str) -> List[str]:
        """List dataset MFIDs accessible to a user.

        Inspecting another user requires platform-administrator permissions.

        Args:
            user_ref (str): User MFID, ORCID, username, or email

        Returns:
            List[str]: Dataset unique IDs the user has access to
        """
        records = self._client.datasets.list(
            accessible_to_user=user_ref,
            limit=None,
        )
        return [record['unique_id'] for record in records]

    @_deprecated_parameter('orcid', 'user_ref')
    @_deprecated_parameter('dsid', 'dataset_mfid')
    def check_dataset_access(self, user_ref: str,
                             dataset_mfid: str) -> 'EffectiveResourceAccess':
        """Return a user's effective access role for a dataset.

        Inspecting another user requires platform-administrator permissions.

        Args:
            user_ref (str): User MFID, ORCID, username, or email
            dataset_mfid (str): Dataset MFID

        Returns:
            EffectiveResourceAccess: Canonical user, resource, and effective role
        """
        from ..models import EffectiveResourceAccess

        raw = self._request('get', f'/users/{user_ref}/datasets/{dataset_mfid}')
        return EffectiveResourceAccess.model_validate(raw)

    @_deprecated_parameter('orcid', 'user_unique_id')
    def list_access_groups(self, user_unique_id: str) -> List[str]:
        """List access group names for a user.

        Args:
            user_unique_id (str): Canonical user ORCID or MFID

        Returns:
            List[str]: Access group names the user belongs to
        """
        return self._request('get', f'/users/{user_unique_id}/access_groups')

    @_deprecated("client.projects.add_user() or client.instruments.bind_service_account()")
    @_deprecated_parameter('orcid', 'user_unique_id')
    def add_to_access_group(self, user_unique_id: str, group_name: str) -> Dict:
        """Add a user to an access group.

        **Requires admin permissions.**

        Args:
            user_unique_id (str): Canonical user ORCID or MFID
            group_name (str): Name of the access group

        Returns:
            Dict: Updated access group object
        """
        return self._request('post', f'/users/{user_unique_id}/access_groups/{group_name}')

    @_deprecated_parameter('orcid', 'user_unique_id')
    def get_projects(self, user_unique_id: str, limit: int = DEFAULT_LIMIT,
                     offset: int = 0) -> List[Dict]:
        """List projects associated with a user.

        Args:
            user_unique_id (str): Canonical user ORCID or MFID
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)

        Returns:
            List[Dict]: Project objects the user is associated with
        """
        return self._paginate(f'/users/{user_unique_id}/projects', {}, limit, offset)

    @_deprecated_parameter('orcid', 'user_unique_id')
    def update(self, user_unique_id: str, **kwargs) -> Dict:
        """Partially update a user record.

        **Requires admin permissions.**

        Args:
            user_unique_id (str): Canonical user ORCID or MFID
            **kwargs: Fields to update. Accepted: first_name, last_name,
                      email, username.

        Returns:
            Dict: Updated user object
        """
        if 'is_service_account' in kwargs:
            raise ValueError("is_service_account cannot be changed through user update.")
        return self._request('patch', f'/users/{user_unique_id}', json=kwargs)

    @_deprecated("client.account.api_key()")
    def get_api_key(self) -> str:
        """Deprecated: use client.account.api_key() instead."""
        return self._client.account.api_key()

    @_deprecated("client.projects.remove_user() or client.instruments.unbind_service_account()")
    @_deprecated_parameter('orcid', 'user_unique_id')
    def remove_from_access_group(self, user_unique_id: str, group_name: str) -> Dict:
        """Remove a user from an access group.

        **Requires admin permissions.**

        Args:
            user_unique_id (str): Canonical user ORCID or MFID
            group_name (str): Name of the access group

        Returns:
            Dict: Response message
        """
        return self._request('delete', f'/users/{user_unique_id}/access_groups/{group_name}')
