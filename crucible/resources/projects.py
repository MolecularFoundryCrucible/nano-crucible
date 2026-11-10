#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project resource operations for Crucible API.

Provides organized access to project-related API endpoints.
"""

import logging
from typing import Any, Optional, List, Dict, Sequence, Union
from .base import BaseResource, ListResult
from .capabilities import AccessControlMixin, OwnershipMixin
from .users import _as_query_list
from ..constants import DEFAULT_LIMIT, PROJECT_ACCESS_ROLES, PROJECT_MEMBER_ROLES, PROJECT_SORTS
from ..models import Project, ProjectMember
from ..errors import RemovedError
from ..utils.deprecation import _deprecated_parameter, _deprecated, _removed, _removed_parameter, removed_message
from ..utils.identifiers import (
    classify_slug_reference,
    collapse_exact_lookup,
    is_mfid,
    require_canonical_identifier,
    validate_slug,
)

logger = logging.getLogger(__name__)


def _build_project_from_args(project_id, organization, project_lead_orcid):
    """Default function to build project info from arguments."""
    return {
        "project_id": project_id,
        "organization": organization,
        "project_lead_orcid": project_lead_orcid,
    }


class ProjectOperations(OwnershipMixin, AccessControlMixin, BaseResource):
    """Project-related API operations.

    Access via: client.projects.get(), client.projects.list(), etc.
    """

    def get(self, project_ref: Optional[str] = None,
            include_metadata: bool = False,
            include_members: bool = False,
            project_id: Optional[str] = None,
            project_mfid: Optional[str] = None) -> Dict:
        """Get a project by canonical MFID or human-readable project slug.

        The response always includes project_id, organization, status, title.

        The ``lead`` field is a public-safe user record containing canonical
        identity, username, and name, but never email.

        ``scientific_metadata`` is only ever populated for members/admins —
        include_metadata is silently ignored for non-members. Same gating
        applies to ``members`` (list of {unique_id, username, first_name,
        last_name, role}) with include_members - non-members always get
        ``members: None`` regardless of the flag.

        Args:
            project_ref (str, optional): Project MFID or project slug. Lookup accepts
                                         legacy slugs outside the current write limits.
            project_id (str, optional): Explicit project slug
            project_mfid (str, optional): Explicit project MFID
            include_metadata (bool): Whether to include scientific metadata
                                      (members/admins only)
            include_members (bool): Whether to include the member list
                                     (members/admins only)

        Returns:
            Dict: Project information, with membership-gated fields as described above
        """
        provided = [value for value in (project_ref, project_id, project_mfid) if value is not None]
        if len(provided) != 1:
            raise ValueError("Provide exactly one project reference.")
        if project_mfid is not None:
            return self._get_by_mfid(
                project_mfid,
                include_metadata=include_metadata,
                include_members=include_members,
            )
        if project_id is not None:
            return self._get_by_project_id(
                project_id,
                include_metadata=include_metadata,
                include_members=include_members,
            )
        assert project_ref is not None
        reference_kind = classify_slug_reference(project_ref, 'project')
        if reference_kind == 'mfid':
            return self._get_by_mfid(
                project_ref,
                include_metadata=include_metadata,
                include_members=include_members,
            )
        return self._get_by_project_id(
            project_ref,
            include_metadata=include_metadata,
            include_members=include_members,
        )

    def _resource_mfid(self, project_ref: str) -> str:
        """Return the MFID for a project MFID or slug (slugs ignore case)."""
        if is_mfid(project_ref):
            return project_ref
        return self._get_by_project_id(project_ref)['unique_id']

    def _get_by_mfid(self, project_mfid: str, include_metadata: bool = False,
                     include_members: bool = False) -> Dict:
        """Get a project through its canonical single-resource route."""
        if not is_mfid(project_mfid):
            raise ValueError("project_mfid must be an exact 26-character MFID.")
        params = {}
        if include_metadata:
            params['include_metadata'] = True
        if include_members:
            params['include_members'] = True
        raw = self._request('get', f'/projects/{project_mfid}', params=params or None)
        return require_canonical_identifier(raw, 'project')

    def _get_by_project_id(self, project_id: str, include_metadata: bool = False,
                           include_members: bool = False) -> Dict:
        """Resolve an exact project slug through the collection route."""
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("project_id must be a non-empty string.")
        params = {'project_id': project_id, 'limit': 2}
        if include_metadata:
            params['include_metadata'] = True
        if include_members:
            params['include_members'] = True
        raw = self._request('get', '/projects', params=params)
        return collapse_exact_lookup(raw, 'project', project_id)

    def list(self, orcid: Optional[str] = None, include_metadata: bool = False,
             limit: int = DEFAULT_LIMIT, offset: int = 0,
             accessible_to_user: Optional[Union[str, Sequence[str]]] = None,
             accessible_to_project: Optional[Union[str, Sequence[str]]] = None,
             sort: Optional[str] = None, direction: Optional[str] = None,
             member_ref: Optional[Union[str, Sequence[str]]] = None,
             member_role: Optional[Union[str, Sequence[str]]] = None,
             cursor: Optional[str] = None,
             mfid: Optional[Union[str, Sequence[str]]] = None) -> List[Dict]:
        """List all accessible projects.

        Each project dict includes a ``lead`` key with the project lead's
        public-safe user record and a ``role`` key with the caller's
        membership role (None when the project is only visible through
        platform role or resource grants).

        Args:
            orcid: Removed in 4.0.0; passing it raises RemovedError. Use member_ref or
                client.users.list_projects().
            include_metadata (bool): Include scientific metadata in results
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            cursor (str, optional): Continuation token from a previous
                result's next_cursor; the listing resumes there.
            accessible_to_user: User reference or references whose effective access
                                must include every result
            accessible_to_project: Project reference or references whose direct access
                                   must include every result
            sort: Explicit ordering, one of crucible.constants.PROJECT_SORTS.
            direction: Sort direction, asc or desc. Requires sort. Without it,
                       dates default to desc and everything else to asc.
            member_ref: User reference or references (ORCID, service-account
                        MFID, username, or email) whose membership must include
                        every result. Repeated values use AND semantics.
            member_role: Restrict member_ref to these project roles. Repeated
                         values use OR semantics and require member_ref.
            mfid: Only these project MFIDs (up to 100). Applies to /projects
                  only. Unreadable or missing MFIDs are left out.

        Returns:
            List[Dict]: Project metadata including project_id, title, organization, lead, role
        """
        if orcid is not None:
            raise RemovedError(removed_message(
                "The 'orcid' argument of projects.list()",
                "use member_ref=... or client.users.list_projects() instead."))
        params = self._access_selector_params(
            accessible_to_user, accessible_to_project)
        member_selectors = _as_query_list(member_ref)
        member_roles = _as_query_list(member_role)
        if member_roles and not member_selectors:
            raise ValueError("member_role requires member_ref.")
        invalid = [role for role in (member_roles or [])
                   if role not in PROJECT_ACCESS_ROLES]
        if invalid:
            raise ValueError(
                f"member_role must be one of: {', '.join(PROJECT_ACCESS_ROLES)}.")
        if include_metadata:
            params['include_metadata'] = True
        params.update(self._ordering_params(sort, direction, sorts=PROJECT_SORTS))
        if member_selectors:
            params['member_ref'] = member_selectors
        if member_roles:
            params['member_role'] = member_roles
        self._apply_mfid_filter(params, mfid)
        return self._paginate('/projects', params, limit, offset, cursor=cursor)

    def create(self, project: Union[Project, Dict],
               scientific_metadata: Optional[Dict] = None) -> Dict:
        """Create a new project.

        Any authenticated user may create a project. The selected lead must be
        an existing user.

        Args:
            project: A Project model instance or a dict with project_id,
                     organization, and project_lead_email. Alternatively, pass
                     a flexible `project_lead` field (ORCID, username, or
                     email - resolved server-side) instead of the three
                     explicit `project_lead_orcid`/`project_lead_email`/
                     `project_lead_username` fields; providing both is a 400,
                     as is providing neither.
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
            project_details = project.model_dump(
                exclude={'capabilities'},
                exclude_none=True,
            )
        else:
            project_details = dict(project)
            project_details.pop('capabilities', None)

        validate_slug(project_details.get('project_id'), 'project')

        flexible_lead = project_details.get('project_lead')
        explicit_leads = [
            project_details.get('project_lead_orcid'),
            project_details.get('project_lead_email'),
            project_details.get('project_lead_username'),
        ]
        if flexible_lead and any(explicit_leads):
            raise ValueError(
                "Pass 'project_lead' or one explicit project lead field, not both."
            )
        if sum(lead is not None for lead in explicit_leads) > 1:
            raise ValueError("Pass only one explicit project lead field.")
        if not flexible_lead and not any(explicit_leads):
            raise ValueError("A project lead is required.")

        result = self._request('post', "/projects", json=project_details)
        if scientific_metadata:
            self._add_first_scientific_metadata(result.get('unique_id') or result['project_id'],
                                                scientific_metadata)
        return result

    @_deprecated("client.projects.list_users()")
    def get_users(self, *args, **kwargs):
        """Deprecated: use list_users()."""
        return self.list_users(*args, **kwargs)

    def list_users(self, project_id: str, limit: int = DEFAULT_LIMIT,
                  offset: int = 0,
                  cursor: Optional[str] = None) -> List[ProjectMember]:
        """Get users associated with a project.

        **Requires admin permissions.**

        Args:
            project_id (str): Unique project identifier
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            cursor (str, optional): Continuation token from a previous
                result's next_cursor; the listing resumes there.

        Returns:
            List[ProjectMember]: Project team members (excludes project lead)
        """
        raw = self._paginate(f'/projects/{project_id}/users', {}, limit, offset, cursor=cursor)
        return ListResult.like(raw, [ProjectMember.model_validate(m) for m in raw])

    def update(self, proj_id: str, **kwargs: Any) -> Dict:
        """Partially update a project record.

        **Requires admin permissions.**

        Leadership changes are not accepted here (422) - use
        transfer_ownership() instead, which moves owner standing and the
        denormalized lead pointer atomically.

        Note the identifying parameter is named `proj_id`, not `project_id` -
        `project_id` is itself now a valid field in `**kwargs` (it renames the
        project), and the two would collide if both were named the same.

        Args:
            proj_id (str): Unique project identifier
            **kwargs: Fields to update. Accepted: project_id (renames the
                      project), organization, status, title.

        Returns:
            Dict: Updated project object
        """
        if kwargs.get('project_id') is not None:
            validate_slug(kwargs['project_id'], 'project')
        if 'capabilities' in kwargs:
            raise ValueError("Project capabilities are response-only.")
        return self._request('patch', f'/projects/{proj_id}', json=kwargs)

    @staticmethod
    def _parse_members(raw) -> List[ProjectMember]:
        """Validate a project member list returned by a mutation endpoint."""
        return [ProjectMember.model_validate(member) for member in raw]

    @staticmethod
    def _validate_member_role(role: str) -> str:
        if role not in PROJECT_MEMBER_ROLES:
            allowed = ', '.join(PROJECT_MEMBER_ROLES)
            raise ValueError(f"Project member role must be one of: {allowed}.")
        return role

    def _resolve_member_unique_id(self, user_unique_id: Optional[str] = None,
                                  email: Optional[str] = None,
                                  username: Optional[str] = None) -> str:
        """Return a project membership target for the {user_ref} path segment.

        ORCID, service-account MFID, and username pass straight through. Email
        is deprecated in path segments, so it is resolved to the canonical
        unique_id with a user lookup first.
        """
        provided = [value for value in (user_unique_id, email, username) if value is not None]
        if len(provided) != 1:
            raise ValueError("Provide exactly one user identifier")
        if user_unique_id is not None:
            return user_unique_id
        if username is not None:
            return username

        user = self._client.users.get(email=email)
        resolved = user.get('unique_id') if isinstance(user, dict) else None
        if not resolved:
            raise ValueError("Resolved user is missing a canonical unique_id")
        return resolved

    @_deprecated_parameter('user_unique_id', 'user_ref')
    @_removed_parameter('orcid', 'user_unique_id')
    def remove_user(self, project_id: str, user_ref: Optional[str] = None,
                    email: Optional[str] = None,
                    username: Optional[str] = None) -> List[ProjectMember]:
        """Remove a user from a project.

        Project owners and platform administrators may remove members. A member
        may also remove themselves.

        Email and username inputs are resolved before the canonical membership request.

        Args:
            project_id (str): Unique project identifier
            user_ref (str, optional): Canonical user ORCID or MFID
            email (str, optional): User's email address
            username (str, optional): User's username

        Returns:
            List[ProjectMember]: Updated list of project users
        """
        canonical_id = self._resolve_member_unique_id(user_ref, email, username)
        raw = self._request('delete', f'/projects/{project_id}/users/{canonical_id}')
        return self._parse_members(raw)

    @_deprecated_parameter('user_unique_id', 'user_ref')
    @_removed_parameter('orcid', 'user_unique_id')
    def add_user(self, user_ref: Optional[str] = None, project_id: Optional[str] = None,
                email: Optional[str] = None, username: Optional[str] = None,
                role: Optional[str] = None) -> List[ProjectMember]:
        """Add a user to a project.

        **Requires editor or above in the project.** The granted role must be
        strictly below the caller's role. Editors may grant contributor or
        viewer, admins may also grant editor, and owners may also grant admin.
        Platform administrators retain their bypass. Ownership changes use
        transfer_ownership().

        Email and username inputs are resolved before the canonical membership request.

        Args:
            user_ref (str, optional): Canonical user ORCID or MFID
            project_id (str): Unique project identifier
            email (str, optional): User's email address
            username (str, optional): User's username
            role (str, optional): Role to grant (default: contributor)

        Returns:
            List[ProjectMember]: Updated list of project users
        """
        canonical_id = self._resolve_member_unique_id(user_ref, email, username)
        params = {'role': self._validate_member_role(role)} if role is not None else {}
        raw = self._request(
            'post', f'/projects/{project_id}/users/{canonical_id}', params=params)
        return self._parse_members(raw)

    @_deprecated_parameter('user_unique_id', 'user_ref')
    @_removed_parameter('orcid', 'user_unique_id')
    def update_user_role(self, project_id: str, user_ref: str,
                         role: str) -> List[ProjectMember]:
        """Change a member's role in a project.

        **Requires editor or above in the project.** Both the member's current
        role and their requested role must be strictly below the caller's role.
        Platform administrators retain their bypass. Ownership changes use
        transfer_ownership().

        Args:
            project_id (str): Unique project identifier
            user_ref (str): Canonical user ORCID or MFID
            role (str): New role to grant

        Returns:
            List[ProjectMember]: Updated list of project users
        """
        role = self._validate_member_role(role)
        raw = self._request(
            'patch', f'/projects/{project_id}/users/{user_ref}',
            params={'role': role})
        return self._parse_members(raw)

    def search(self, q: str, limit: int = 20) -> List[Dict]:
        """Fuzzy search across all projects (not just the caller's). Available
        to all authenticated users — supports project discovery ahead of
        request_join().

        Matches against both title and project_id. Results never include
        lead or scientific_metadata, regardless of membership.

        Args:
            q: Search term (min 3 chars). Typo-tolerant.
            limit: Max results (default 20, max 50).

        Returns:
            List[Dict]: Matching ProjectRead records, ranked by relevance.
        """
        result = self._request('get', '/projects/search', params={'q': q, 'limit': limit})
        return result.get('items', result) if isinstance(result, dict) else result

    def request_join(self, project_id: str, reason: Optional[str] = None) -> Dict:
        """Request to join this project. Any authenticated user.

        Delegates to client.access_groups.request_join() — see there for full
        list/approve/reject operations on join requests.

        Args:
            project_id: Project slug or MFID.
            reason: Optional explanation for the request.

        Returns:
            Dict: The created JoinRequest record (status will be "pending").

        Raises:
            HTTPError 404: Project doesn't exist.
            HTTPError 409: Already a member, already has a pending request,
                or the project is pending deletion.
        """
        return self._client.access_groups.request_join(project_id, reason=reason)

    def list_join_requests(self, project_id: str, status: Optional[str] = None,
                           limit: int = DEFAULT_LIMIT, offset: int = 0,
                           **filters) -> List[Dict]:
        """List join requests for this project visible to the caller.

        Project editors and above (and platform admins) see every request;
        others see only their own. Delegates to
        client.access_groups.list_join_requests(project_mfid=...), which
        takes the other filters and sorts.

        Args:
            project_id: Project slug or MFID.
            status: One status or a list of them, from
                crucible.constants.JOIN_REQUEST_STATUSES.
            limit: Maximum number of results.
            offset: Starting position in the full result set.
            **filters (Any): Any other list_join_requests() keyword, such
                as scope, sort, direction, or cursor.

        Returns:
            List[Dict]: Matching JoinRequest records, most recent first.
        """
        return self._client.access_groups.list_join_requests(
            project_mfid=self._resource_mfid(project_id), status=status,
            limit=limit, offset=offset, **filters)

    @_removed("use create() instead; it finds an existing project itself.")
    def get_or_create(self, *args, **kwargs):
        """Removed in 4.0.0: use create() instead."""

