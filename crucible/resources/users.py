#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User resource operations for Crucible API.

Provides organized access to user-related API endpoints.
"""

import logging
from typing import Optional, Dict
from .base import BaseResource

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

    def create(self, user_info: Dict) -> Dict:
        """Add a new user to the system.

        **Requires admin permissions.**

        Args:
            user_info (Dict): User information including 'projects' key.
                            Expected keys: first_name, last_name, orcid, email (optional),
                            lbl_email (optional), projects (list of project IDs)

        Returns:
            Dict: Created user object

        Example:
            >>> user_info = {
            ...     "first_name": "Jane",
            ...     "last_name": "Doe",
            ...     "orcid": "0000-0000-0000-0000",
            ...     "email": "jane@example.com",
            ...     "projects": ["project1", "project2"]
            ... }
            >>> new_user = client.users.create(user_info)
        """
        user_projects = user_info.pop("projects")

        new_user = self._request('post', "/users",
                                json={"user_info": user_info,
                                      "project_ids": user_projects})
        return new_user

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
