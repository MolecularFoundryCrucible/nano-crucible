#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base resource class for Crucible API operations.

Provides shared functionality for all resource operation classes.
"""


from ..constants import DEFAULT_LIMIT


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

    def _paginate(self, endpoint: str, params: dict,
                  limit: int = DEFAULT_LIMIT, offset: int = 0) -> list:
        """Fetch all matching records from a paginated envelope endpoint.

        Fires the first request to get the total count, then fetches all
        remaining pages in parallel. Each response must be a paginated envelope
        with 'total', 'limit', 'offset', and 'items' fields.

        Args:
            endpoint: API path (e.g. '/datasets')
            params:   Query parameters (must NOT include 'limit' or 'offset')
            limit:    Maximum number of records to return. Pass None to fetch all.
            offset:   Starting position in the full result set

        Returns:
            list: Raw item dicts, up to limit items (or all items if limit is None)
        """
        from concurrent.futures import ThreadPoolExecutor
        from ..constants import API_PAGE_MAX

        page_size = API_PAGE_MAX
        first = self._request('get', endpoint,
                              params={**params, 'limit': page_size, 'offset': offset})
        total = first['total']
        items = list(first['items'])

        need = total - offset if limit is None else min(total - offset, limit)
        if len(items) >= need:
            return items[:need]

        remaining_offsets = range(offset + page_size, offset + need, API_PAGE_MAX)

        def _fetch(off):
            r = self._request('get', endpoint,
                              params={**params, 'limit': API_PAGE_MAX, 'offset': off})
            return r['items']

        with ThreadPoolExecutor(max_workers=min(len(remaining_offsets), 8)) as pool:
            for page in pool.map(_fetch, remaining_offsets):
                items.extend(page)

        return items[:need]

    def search_scientific_metadata(self, q: str, limit: int = None) -> list:
        """Full-text search across scientific metadata of all accessible resources.

        Results are ranked by relevance and may include datasets or samples.
        Each result contains 'unique_id' (the resource MFID) and 'scientific_metadata'.

        Args:
            q: Plain-text search query (English-language stemmed).
            limit: Max results to return (default 50, max 200).
        """
        params = {"q": q}
        if limit is not None:
            params["limit"] = limit
        return self._request('get', '/resources/metadata/search', params=params)

    def get_scientific_metadata(self, resource_id: str) -> dict:
        """Get scientific metadata for a resource."""
        return self._request('get', f'/resources/{resource_id}/metadata')

    def add_scientific_metadata(self, resource_id: str, metadata: dict) -> dict:
        """Create scientific metadata for a resource."""
        return self._request('post', f'/resources/{resource_id}/metadata', json=metadata)

    def update_scientific_metadata(self, resource_id: str, metadata: dict,
                                   overwrite: bool = False) -> dict:
        """Update scientific metadata for a resource.

        Args:
            overwrite: If True, replace all metadata (POST); if False, merge with existing (PATCH)
        """
        if overwrite:
            return self._request('post', f'/resources/{resource_id}/metadata', json=metadata)
        return self._request('patch', f'/resources/{resource_id}/metadata', json=metadata)
