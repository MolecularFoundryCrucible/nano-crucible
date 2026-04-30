#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base resource class for Crucible API operations.

Provides shared functionality for all resource operation classes.
"""


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
                  limit: int, offset: int = 0) -> list:
        """Fetch all matching records from a paginated envelope endpoint.

        Fires the first request to get the total count, then fetches all
        remaining pages in parallel. Each response must be a paginated envelope
        with 'total', 'limit', 'offset', and 'items' fields.

        Args:
            endpoint: API path (e.g. '/datasets')
            params:   Query parameters (must NOT include 'limit' or 'offset')
            limit:    Maximum number of records to return (user-facing limit)
            offset:   Starting position in the full result set

        Returns:
            list: Raw item dicts, up to limit items
        """
        from concurrent.futures import ThreadPoolExecutor
        from ..constants import API_PAGE_MAX

        page_size = min(limit, API_PAGE_MAX)
        first = self._request('get', endpoint,
                              params={**params, 'limit': page_size, 'offset': offset})
        total = first['total']
        items = list(first['items'])

        need = min(total - offset, limit)
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
