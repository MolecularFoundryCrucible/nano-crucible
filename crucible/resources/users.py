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

logger = logging.getLogger(__name__)


class UserOperations(BaseResource):
    """User-related API operations.

    Access via: client.users.get(), client.users.create(), etc.
    """

    def get(self, orcid: Optional[str] = None, email: Optional[str] = None) -> Dict:
        """Get user details by unique ID (ORCID for real users) or email.

        **Requires admin permissions.**

        Args:
            orcid (str, optional): User unique ID (ORCID for real users)
            email (str, optional): User's email address

        Returns:
            Dict: User profile with unique_id, name, email, is_service_account

        Raises:
            ValueError: If neither orcid nor email is provided, no user is found,
                or email matches multiple accounts (use ORCID in that case).

        Note:
            ORCID is the canonical user identifier. Email is not guaranteed unique -
            if both are provided, orcid takes precedence.
        """
        if orcid:
            return self._request('get', f'/users/{orcid}')
        elif email:
            matches = self._paginate('/users', {'email': email, 'permissive': False})
            if not matches:
                raise ValueError(f"No user found with email: {email}")
            if len(matches) > 1:
                raise ValueError(
                    f"Multiple users match email '{email}' - use ORCID to identify unambiguously"
                )
            return matches[0]
        else:
            raise ValueError('please provide orcid or email')

    def list(self, limit: int = DEFAULT_LIMIT, offset: int = 0, **kwargs) -> List[Dict]:
        """List all users in the system.

        **Requires admin permissions.**

        Args:
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Additional query parameters for filtering

        Returns:
            List[Dict]: List of user objects with unique_id, name, email, is_service_account

        Example:
            >>> users = client.users.list(limit=50)
            >>> for user in users:
            ...     print(f"{user['first_name']} {user['last_name']} ({user['orcid']})")
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        users = self._paginate('/users', params, limit, offset)
        return sorted(users, key=lambda u: u.get('id') or 0)

    def create(self, user, project_ids=None) -> Dict:
        """Add or update a user in the system (upsert by ORCID).

        If a user with the given ORCID already exists their record is updated.
        Project memberships and access groups are always re-applied.

        **Requires admin permissions.**

        Args:
            user: User model or dict with user information.
                  Required fields: first_name, last_name, orcid.
                  Optional: email, is_service_account.
                  If a dict, may include a 'projects' key (list of project IDs)
                  as an alternative to the project_ids parameter.
            project_ids (list, optional): Project IDs to associate with the user.

        Returns:
            Dict: Created or updated user object

        Example:
            >>> from crucible.models import User
            >>> user = User(first_name="Jane", last_name="Doe", orcid="0000-0000-0000-0000")
            >>> new_user = client.users.create(user, project_ids=["project1"])
        """
        from ..models import User
        if isinstance(user, User):
            user_data = user.model_dump(exclude_none=True, exclude={'id'})
            user_projects = project_ids or []
        else:
            user_data = dict(user)
            user_projects = user_data.pop("projects", project_ids or [])

        # API expects 'orcid', not 'unique_id'
        if 'unique_id' in user_data:
            user_data['orcid'] = user_data.pop('unique_id')

        return self._request('post', "/users", json={"user_info": user_data, "project_ids": user_projects})

    def list_datasets(self, orcid: str) -> List[str]:
        """List dataset IDs accessible to a user.

        **Requires admin permissions.**

        Args:
            orcid (str): User ORCID identifier

        Returns:
            List[str]: Dataset unique IDs the user has access to
        """
        return self._request('get', f'/users/{orcid}/datasets')

    def check_dataset_access(self, orcid: str, dsid: str) -> Dict:
        """Check a user's read/write access to a specific dataset.

        **Requires admin permissions.**

        Args:
            orcid (str): User ORCID identifier
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Permissions dict with 'read' and 'write' boolean keys
        """
        return self._request('get', f'/users/{orcid}/datasets/{dsid}')

    def list_access_groups(self, orcid: str) -> List[str]:
        """List access group names for a user.

        Args:
            orcid (str): User ORCID identifier

        Returns:
            List[str]: Access group names the user belongs to
        """
        return self._request('get', f'/users/{orcid}/access_groups')

    def add_to_access_group(self, orcid: str, group_name: str) -> Dict:
        """Add a user to an access group.

        **Requires admin permissions.**

        Args:
            orcid (str): User ORCID identifier
            group_name (str): Name of the access group

        Returns:
            Dict: Updated access group object
        """
        return self._request('post', f'/users/{orcid}/access_groups/{group_name}')

    def get_projects(self, orcid: str) -> List[Dict]:
        """List projects associated with a user.

        Args:
            orcid (str): User ORCID identifier

        Returns:
            List[Dict]: Project objects the user is associated with
        """
        return self._request('get', f'/users/{orcid}/projects')

    def update(self, orcid: str, **kwargs) -> Dict:
        """Partially update a user record.

        **Requires admin permissions.**

        Args:
            orcid (str): User ORCID identifier
            **kwargs: Fields to update. Accepted: first_name, last_name,
                      email, is_service_account.

        Returns:
            Dict: Updated user object
        """
        return self._request('patch', f'/users/{orcid}', json=kwargs)

    def get_api_key(self) -> str:
        """Return the caller's own Crucible API key.

        Returns:
            str: The caller's API key
        """
        result = self._request('get', '/account/apikey')
        return result['api_key']

    def remove_from_access_group(self, orcid: str, group_name: str) -> Dict:
        """Remove a user from an access group.

        **Requires admin permissions.**

        Args:
            orcid (str): User ORCID identifier
            group_name (str): Name of the access group

        Returns:
            Dict: Response message
        """
        return self._request('delete', f'/users/{orcid}/access_groups/{group_name}')