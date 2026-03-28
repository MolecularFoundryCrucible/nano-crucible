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
        """Get user details by ORCID or email.

        **Requires admin permissions.**

        Args:
            orcid (str, optional): ORCID identifier (format: 0000-0000-0000-000X)
            email (str, optional): User's email address

        Returns:
            Dict: User profile with orcid, name, email, timestamps

        Raises:
            ValueError: If neither orcid nor email is provided

        Note:
            If both orcid and email are provided, only orcid will be used.
        """
        if orcid:
            return self._request('get', f'/users/{orcid}')
        elif email:
            params = {"email": email}
            result = self._request('get', '/users', params=params)
            if not result:
                params = {"lbl_email": email}
                result = self._request('get', '/users', params=params)
            if len(result) > 0:
                return result[-1]
            else:
                return None
        else:
            raise ValueError('please provide orcid or email')

    def list(self, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List all users in the system.

        **Requires admin permissions.**

        Args:
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Additional query parameters for filtering

        Returns:
            List[Dict]: List of user objects with orcid, name, email, timestamps

        Example:
            >>> users = client.users.list(limit=50)
            >>> for user in users:
            ...     print(f"{user['first_name']} {user['last_name']} ({user['orcid']})")
        """
        params = kwargs
        params['limit'] = limit
        users = self._request('get', '/users', params=params)
        return sorted(users, key=lambda u: u.get('id') or 0)

    def create(self, user, project_ids=None) -> Dict:
        """Add or update a user in the system (upsert by ORCID).

        If a user with the given ORCID already exists their record is updated.
        Project memberships and access groups are always re-applied.

        **Requires admin permissions.**

        Args:
            user: User model or dict with user information.
                  Required fields: first_name, last_name, orcid.
                  Optional: email, lbl_email, employee_number.
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
            user_info = user.model_dump(exclude_none=True, exclude={'id'})
            user_projects = project_ids or []
        else:
            # backward compat: dict with optional 'projects' key
            user_info = dict(user)
            user_projects = user_info.pop("projects", project_ids or [])

        return self._request('post', "/users",
                             json={"user_info": user_info,
                                   "project_ids": user_projects})

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

    def get_or_create(self, orcid: str, get_user_info_function, **kwargs) -> Dict:
        """Get an existing user or create a new one if they don't exist.

        **Requires admin permissions.**

        Args:
            orcid (str): ORCID of the user
            get_user_info_function (callable): Function to retrieve user info if not found.
                                              Should accept orcid (str) and return a dictionary
                                              with keys: 'first_name', 'last_name', 'orcid',
                                              'email' (optional), 'lbl_email' (optional),
                                              'projects' (optional list of project IDs)
            **kwargs: Additional arguments to pass to get_user_info_function

        Returns:
            Dict: User information (existing or newly created)

        Raises:
            ValueError: If user info cannot be found or created

        Example:
            >>> def get_user_from_api(orcid):
            ...     # Fetch user info from external API
            ...     return {
            ...         "first_name": "Jane",
            ...         "last_name": "Doe",
            ...         "orcid": orcid,
            ...         "email": "jane@example.com",
            ...         "projects": ["project1"]
            ...     }
            >>> user = client.users.get_or_create("0000-0000-0000-0000", get_user_from_api)
        """
        user = self.get(orcid)
        if user:
            return user

        user_info = get_user_info_function(orcid, **kwargs)
        if user_info:
            user = self.create(user_info)
            return user
        else:
            raise ValueError(f"User info for {orcid} not found in database or using the get_user_info_function")
