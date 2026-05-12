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


def _build_project_from_args(project_id, organization, project_lead_orcid):
    """Default function to build project info from arguments."""
    return {
        "project_id": project_id,
        "organization": organization,
        "project_lead_orcid": project_lead_orcid,
    }


class ProjectOperations(BaseResource):
    """Project-related API operations.

    Access via: client.projects.get(), client.projects.list(), etc.
    """

    def get(self, project_id: str, include_metadata: bool = False) -> Dict:
        """Get details of a specific project.

        The response includes a ``lead`` key with the project lead's full user
        record (orcid, first_name, last_name, email, lbl_email).

        Args:
            project_id (str): Unique project identifier
            include_metadata (bool): Whether to include scientific metadata

        Returns:
            Dict: Complete project information including embedded lead user
        """
        params = {'include_metadata': True} if include_metadata else {}
        return self._request('get', f'/projects/{project_id}', params=params or None)

    def list(self, orcid: Optional[str] = None, include_metadata: bool = False,
             limit: int = DEFAULT_LIMIT, offset: int = 0) -> List[Dict]:
        """List all accessible projects.

        Each project dict includes a ``lead`` key with the project lead's full
        user record (orcid, first_name, last_name, email, lbl_email).

        Args:
            orcid (str, optional): Filter projects by those associated with a certain user
            include_metadata (bool): Include scientific metadata in results
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)

        Returns:
            List[Dict]: Project metadata including project_id, title, organization, lead
        """
        params = {'include_metadata': True} if include_metadata else {}
        endpoint = f'/users/{orcid}/projects' if orcid else '/projects'
        return self._paginate(endpoint, params, limit, offset)

    def create(self, project: Union[Project, Dict],
               scientific_metadata: Optional[Dict] = None) -> Dict:
        """Create a new project.

        **Requires admin permissions.**

        Args:
            project: A Project model instance or a dict with project_id,
                     organization, and project_lead_email.
            scientific_metadata (Dict, optional): Scientific metadata to attach after creation.

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

        result = self._request('post', "/projects", json=project_details)
        if scientific_metadata:
            self.add_scientific_metadata(result['project_id'], scientific_metadata)
        return result

    def add_scientific_metadata(self, project_id: str, metadata: Dict) -> Dict:
        """Create scientific metadata for a project.

        Args:
            project_id (str): Project unique identifier
            metadata (Dict): Scientific metadata dictionary

        Returns:
            Dict: Created metadata object
        """
        return self._request('post', f'/resources/{project_id}/metadata', json=metadata)

    def update_scientific_metadata(self, project_id: str, metadata: Dict,
                                   overwrite: bool = False) -> Dict:
        """Update scientific metadata for a project.

        Args:
            project_id (str): Project unique identifier
            metadata (Dict): Scientific metadata dictionary
            overwrite (bool): If True, replace all metadata (POST); if False, merge (PATCH)

        Returns:
            Dict: Updated metadata object
        """
        if overwrite:
            return self._request('post', f'/resources/{project_id}/metadata', json=metadata)
        return self._request('patch', f'/resources/{project_id}/metadata', json=metadata)

    def get_users(self, project_id: str, limit: int = DEFAULT_LIMIT,
                  offset: int = 0) -> List[Dict]:
        """Get users associated with a project.

        **Requires admin permissions.**

        Args:
            project_id (str): Unique project identifier
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)

        Returns:
            List[Dict]: Project team members (excludes project lead)
        """
        return self._paginate(f'/projects/{project_id}/users', {}, limit, offset)

    def update(self, project_id: str, **kwargs) -> Dict:
        """Partially update a project record.

        **Requires admin permissions.**

        Args:
            project_id (str): Unique project identifier
            **kwargs: Fields to update. Accepted: organization, status, title,
                      project_lead_email, project_lead_orcid.

        Returns:
            Dict: Updated project object
        """
        return self._request('patch', f'/projects/{project_id}', json=kwargs)

    def remove_user(self, project_id: str, orcid: Optional[str] = None,
                    email: Optional[str] = None) -> Dict:
        """Remove a user from a project.

        **Requires admin permissions.**

        Provide either ``orcid`` or ``email`` to identify the user.
        When ``email`` is given, the ORCID is resolved automatically.

        Args:
            project_id (str): Unique project identifier
            orcid (str, optional): User's ORCID identifier
            email (str, optional): User's email address (alternative to orcid)

        Returns:
            Dict: Response message
        """
        if not orcid and not email:
            raise ValueError("provide either orcid or email")
        if not orcid:
            user = self._client.users.get(email=email)
            orcid = user.get('orcid') or user.get('unique_id')
            if not orcid:
                raise ValueError(f"could not resolve ORCID for email: {email}")
        return self._request('delete', f'/projects/{project_id}/users/{orcid}')

    def add_user(self, orcid: Optional[str] = None, project_id: str = None,
                email: Optional[str] = None) -> List[Dict]:
        """Add a user to a project.

        **Requires admin permissions.**

        Provide either ``orcid`` or ``email`` to identify the user.
        When ``email`` is given, the ORCID is resolved automatically.

        Args:
            orcid (str, optional): User's ORCID identifier
            project_id (str): Unique project identifier
            email (str, optional): User's email address (alternative to orcid)

        Returns:
            List[Dict]: Updated list of project users
        """
        if not orcid and not email:
            raise ValueError("provide either orcid or email")
        if not orcid:
            user = self._client.users.get(email=email)
            orcid = user.get('orcid') or user.get('unique_id')
            if not orcid:
                raise ValueError(f"could not resolve ORCID for email: {email}")
        return self._request('post', f'/projects/{project_id}/users/{orcid}')

    def get_or_create(self, project_id: str, get_project_info_function=_build_project_from_args,
                     **kwargs) -> Dict:
        """Deprecated: use create() instead.

        .. deprecated::
            Use :meth:`create` with a :class:`~crucible.models.Project` model.
            ``create()`` now checks for an existing project before posting.
        """
        import warnings
        warnings.warn(
            "get_or_create() is deprecated; use create() instead — "
            "it now checks for an existing project automatically.",
            DeprecationWarning, stacklevel=2,
        )
        project_info = get_project_info_function(project_id=project_id, **kwargs)
        return self.create(project_info)
