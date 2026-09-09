#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base resource class for Crucible API operations.

Provides shared functionality for all resource operation classes.
"""

# typing
from typing import Optional, Sequence, Union

# internal modules
from ..constants import DEFAULT_LIMIT
from ..utils.deprecation import _deprecated, _deprecated_parameter

class BaseResource:
    """Base class for resource-specific operations.

    All resource classes inherit from this and get access to the
    parent client's _request method for making API calls.
    """

    def __init__(self, client):
        """
        Initialize resource operations.

        Args:
            client: Parent CrucibleClient instance
        """
        self._client = client
        self._request = client._request  # Delegate HTTP requests to main client

    @staticmethod
    def _access_selector_params(
        accessible_to_user: Optional[Union[str, Sequence[str]]] = None,
        accessible_to_project: Optional[Union[str, Sequence[str]]] = None,
    ) -> dict:
        """Build repeated typed access-selector query parameters."""
        def normalize(value, name):
            if value is None:
                return []
            values = [value] if isinstance(value, str) else list(value)
            if any(not isinstance(item, str) or not item for item in values):
                raise ValueError(f"{name} values must be non-empty strings")
            return values

        users = normalize(accessible_to_user, 'accessible_to_user')
        projects = normalize(accessible_to_project, 'accessible_to_project')
        if len(users) + len(projects) > 10:
            raise ValueError("At most 10 access selectors may be supplied")

        params = {}
        if users:
            params['accessible_to_user'] = users
        if projects:
            params['accessible_to_project'] = projects
        return params

    @staticmethod
    def _project_scope_params(
        project_id: Optional[str] = None,
        project_mfid: Optional[str] = None,
        project_scope: Optional[str] = None,
    ) -> dict:
        from ..constants import PROJECT_SCOPES
        from ..utils.identifiers import is_mfid

        if project_scope is not None and project_id is None and project_mfid is None:
            raise ValueError("project_scope requires project_id or project_mfid.")
        if project_scope is not None and project_scope not in PROJECT_SCOPES:
            raise ValueError(
                f"project_scope must be one of: {', '.join(PROJECT_SCOPES)}.")
        if project_id is not None and (
                not isinstance(project_id, str) or not project_id):
            raise ValueError("project_id must be a non-empty string.")
        if project_mfid is not None and not is_mfid(project_mfid):
            raise ValueError("project_mfid must be an exact 26-character MFID.")

        params = {}
        if project_id is not None:
            params['project_id'] = project_id
        if project_mfid is not None:
            params['project_mfid'] = project_mfid
        if project_scope is not None:
            params['project_scope'] = project_scope
        return params

    def _paginate(self, endpoint: str, params: dict,
                  limit: int = DEFAULT_LIMIT, offset: int = 0) -> list:
        """Fetch all matching records from a paginated envelope endpoint.

        Supports both pagination styles transparently, detected from the first
        response:

        * Keyset (cursor) pagination — used by '/datasets' and '/samples'. The
          response carries a 'next_cursor' token; pages are followed
          sequentially until the cursor is exhausted.
        * Offset pagination — every other endpoint. The first response carries
          'total'; remaining pages are fetched in parallel by offset.

        Args:
            endpoint: API path (e.g. '/datasets')
            params:   Query parameters (must NOT include 'limit', 'offset', or 'cursor')
            limit:    Maximum number of records to return. Pass None to fetch all.
            offset:   Starting position in the full result set. Ignored by keyset
                      endpoints, which no longer accept an offset.

        Returns:
            list: Raw item dicts, up to limit items (or all items if limit is None)

        Raises:
            ValueError: If limit is negative
        """
        from concurrent.futures import ThreadPoolExecutor
        from ..constants import API_PAGE_MAX

        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        if limit == 0:
            return []

        page_size = API_PAGE_MAX if limit is None else min(API_PAGE_MAX, limit)
        first_params = {**params, 'limit': page_size}
        if offset:
            first_params['offset'] = offset
        first = self._request('get', endpoint, params=first_params)
        items = list(first['items'])

        # Keyset (cursor) pagination — '/datasets' and '/samples'.
        if 'next_cursor' in first:
            cursor = first.get('next_cursor')
            while cursor and (limit is None or len(items) < limit):
                request_limit = (
                    API_PAGE_MAX if limit is None
                    else min(API_PAGE_MAX, limit - len(items))
                )
                resp = self._request('get', endpoint,
                                     params={**params, 'limit': request_limit,
                                             'cursor': cursor})
                page = list(resp['items'])
                if not page:
                    break
                items.extend(page)
                cursor = resp.get('next_cursor')
            return items if limit is None else items[:limit]

        # Offset pagination — all other endpoints.
        total = first['total']
        need = total - offset if limit is None else min(total - offset, limit)
        if len(items) >= need:
            return items[:need]

        remaining_offsets = range(offset + page_size, offset + need, API_PAGE_MAX)

        def _fetch(off):
            request_limit = min(API_PAGE_MAX, offset + need - off)
            r = self._request('get', endpoint,
                              params={**params, 'limit': request_limit, 'offset': off})
            return r['items']

        with ThreadPoolExecutor(max_workers=min(len(remaining_offsets), 8)) as pool:
            for page in pool.map(_fetch, remaining_offsets):
                items.extend(page)

        return items[:need]

    def search_metadata(self, q: str, limit: int = 20) -> list:
        """Full-text search across scientific metadata of all accessible resources.

        Results are ranked by relevance (rank field) and include resource_type, name,
        owner_orcid, creation_time, modification_time, and scientific_metadata.
        Resources with pending or approved deletion requests are excluded.

        Args:
            q: Plain-text search query (English-language stemmed).
            limit: Max results to return (default 20, max 50).

        Returns:
            List of result dicts with unique_id, resource_type, name, owner_orcid,
            creation_time, modification_time, rank, and scientific_metadata.
        """
        resp = self._request('get', '/resources/metadata/search',
                             params={"q": q, "limit": limit})
        if isinstance(resp, dict) and 'items' in resp:
            return resp['items']
        return resp or []

    @_deprecated("search_metadata()")
    def search_scientific_metadata(self, q: str, limit: int = 50) -> list:
        """Deprecated: use search_metadata() instead."""
        return self.search_metadata(q, limit=limit)

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def get_scientific_metadata(self, resource_mfid: str) -> dict:
        """Get scientific metadata for a resource."""
        return self._request('get', f'/resources/{resource_mfid}/metadata')

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def replace_scientific_metadata(self, resource_mfid: str, metadata: dict) -> dict:
        """Create new scientific metadata entry for a resource."""
        # this is kind of redundant with API but its better here? #TODO
        return self._request(
            'post', f'/resources/{resource_mfid}/metadata',
            json=metadata, params={'overwrite': True})

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def update_scientific_metadata(self, resource_mfid: str, metadata: dict,
                                   overwrite: bool = False) -> dict:
        """Add or Update scientific metadata for a resource.

        Args:
            overwrite: If True, replace all metadata (POST); if False, merge with existing (PATCH)
        """
        if overwrite:
            return self._request(
                'post', f'/resources/{resource_mfid}/metadata',
                json=metadata, params={'overwrite': overwrite})
        return self._request(
            'patch', f'/resources/{resource_mfid}/metadata', json=metadata)
