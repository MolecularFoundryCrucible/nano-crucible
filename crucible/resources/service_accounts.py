#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service account operations.

Service accounts are non-human users that authenticate with an API key.
Created and managed via /service_accounts — admin only.
"""

import logging
from typing import Dict, List, Optional

from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..utils.identifiers import validate_mfid, validate_username

logger = logging.getLogger(__name__)


class ServiceAccountOperations(BaseResource):
    """Operations for service accounts.

    Access via: client.service_accounts.*
    """

    def create(self, username: str, unique_id: Optional[str] = None) -> Dict:
        """Create a new service account.

        The API key is returned once only — store it immediately.

        Args:
            username: Unique 3-to-24-character username.
            unique_id: Optional MFID. Server generates one if omitted.

        Returns:
            Dict with unique_id, username, is_service_account, and api_key.

        Raises:
            HTTPError 409: username or unique_id already exists.
        """
        body = {'username': validate_username(username)}
        if unique_id:
            body['unique_id'] = validate_mfid(unique_id)
        return self._request('post', '/service_accounts', json=body)

    def rotate_key(self, unique_id: str) -> Dict:
        """Generate a new API key for a service account, invalidating the old one.

        The new key is returned once only — store it immediately.

        Args:
            unique_id: Service account MFID.

        Returns:
            Dict with unique_id, username, is_service_account, and api_key.

        Raises:
            HTTPError 404: unique_id does not correspond to a service account.
        """
        return self._request('post', f'/service_accounts/{unique_id}/rotate_key')

    def get(self, service_account_mfid: Optional[str] = None,
            username: Optional[str] = None,
            *, unique_id: Optional[str] = None) -> Optional[Dict]:
        """Get a service account by MFID or username.

        Args:
            service_account_mfid: Service account MFID.
            username: Service account username.
            unique_id: Deprecated alias for ``service_account_mfid``.

        Returns:
            Dict: User record, or None if not found.
        """
        provided = [
            value for value in (service_account_mfid, username, unique_id)
            if value is not None
        ]
        if len(provided) != 1:
            raise ValueError("Provide exactly one service-account identifier.")
        if unique_id is not None:
            import warnings
            warnings.warn(
                "The unique_id keyword is deprecated; use service_account_mfid instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            service_account_mfid = unique_id
        if service_account_mfid is not None:
            return self._client.users.get(user_unique_id=service_account_mfid)
        return self._client.users.get(username=username)

    def list(self, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List all service accounts.

        Args:
            limit: Maximum number of results.

        Returns:
            List of user records with is_service_account=True.
        """
        return self._client.users.list(limit=limit, is_service_account=True)

    def update(self, unique_id: str, **kwargs) -> Dict:
        """Update a service account record.

        Args:
            unique_id: Service account MFID.
            **kwargs: Fields to update. Accepted: username, first_name, last_name.

        Returns:
            Dict: Updated user record.
        """
        return self._client.users.update(unique_id, **kwargs)

    def list_access_groups(self, unique_id: str) -> List[str]:
        """List access group names a service account belongs to.

        Args:
            unique_id: Service account MFID.

        Returns:
            List[str]: Access group names.
        """
        return self._client.users.list_access_groups(unique_id)

    def add_to_access_group(self, unique_id: str, group_name: str) -> Dict:
        """Add a service account to an access group.

        Args:
            unique_id: Service account MFID.
            group_name: Name of the access group.
        """
        return self._client.users.add_to_access_group(unique_id, group_name)

    def remove_from_access_group(self, unique_id: str, group_name: str) -> Dict:
        """Remove a service account from an access group.

        Args:
            unique_id: Service account MFID.
            group_name: Name of the access group.
        """
        return self._client.users.remove_from_access_group(unique_id, group_name)
