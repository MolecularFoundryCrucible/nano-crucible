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
