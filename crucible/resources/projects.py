#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project resource operations for Crucible API.

Provides organized access to project-related API endpoints.
"""

import logging
from typing import Optional, List, Dict, Union
from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..models import Project

logger = logging.getLogger(__name__)


def _build_project_from_args(project_id, organization, project_lead_email):
    """Default function to build project info from arguments."""
    return {
        "project_id": project_id,
        "organization": organization,
        "project_lead_email": project_lead_email
    }


class ProjectOperations(BaseResource):
    """Project-related API operations.

    Access via: client.projects.get(), client.projects.list(), etc.
    """

    def get(self, project_id: str) -> Dict:
        """Get details of a specific project.

        Args:
            project_id (str): Unique project identifier

        Returns:
            Dict: Complete project information
        """
        return self._request('get', f'/projects/{project_id}')

    def list(self, orcid: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List all accessible projects.

        Args:
            orcid (str, optional): Filter projects by those associated with a certain user
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Project metadata including project_id, project_name, description, project_lead_email
        """
        if orcid is None:
            return self._request('get', '/projects')
        else:
            return self._request('get', f'/users/{orcid}/projects')

    def create(self, project: Union[Project, Dict]) -> Dict:
        """Create a new project.

        **Requires admin permissions.**

        Args:
            project: A Project model instance or a dict with project_id,
                     organization, and project_lead_email.

        Returns:
            Dict: Created project object

        Example:
            >>> from crucible.models import Project
            >>> project = Project(
            ...     project_id="my-project",
            ...     organization="Molecular Foundry",
            ...     project_lead_email="lead@lbl.gov"
            ... )
            >>> result = client.projects.create(project)
        """
        if isinstance(project, Project):
            project_details = project.model_dump(exclude_none=True)
        else:
            project_details = dict(project)
        return self._request('post', "/projects", json=project_details)

    def get_users(self, project_id: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get users associated with a project.

        **Requires admin permissions.**

        Args:
            project_id (str): Unique project identifier
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Project team members (excludes project lead)
        """
        result = self._request('get', f'/projects/{project_id}/users')
        return result

    def add_user(self, orcid: str, project_id: str) -> List[Dict]:
        """Add a user to a project.

        **Requires admin permissions.**

        Args:
            orcid (str): User's ORCID identifier
            project_id (str): Unique project identifier

        Returns:
            List[Dict]: Updated list of project users
        """
        updated_project_users = self._request('post', f'/projects/{project_id}/users/{orcid}')
        return updated_project_users

    def get_or_create(self, project_id: str, get_project_info_function=_build_project_from_args,
                     **kwargs) -> Dict:
        """Get an existing project or create a new one if it doesn't exist.

        **Requires admin permissions for project creation.**

        Args:
            project_id (str): ID of the Crucible project
            get_project_info_function (callable): Function to retrieve project info if not found
            **kwargs: Additional arguments to pass to get_project_info_function.
                     If relying on the default, provide: organization, project_lead_email

        Returns:
            Dict: Project information (existing or newly created)

        Raises:
            ValueError: If project info cannot be found or created

        Example:
            >>> # Using default builder
            >>> project = client.projects.get_or_create(
            ...     "my-project",
            ...     organization="My Lab",
            ...     project_lead_email="lead@example.com"
            ... )
        """
        proj = self.get(project_id)
        if proj is not None:
            return proj

        project_info = get_project_info_function(project_id=project_id, **kwargs)

        if project_info:
            proj = self.create(project_info)
            return proj
        else:
            raise ValueError(f"Project info for {project_id} not found in database or using the provided get_project_info_function")
