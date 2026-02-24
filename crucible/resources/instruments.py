#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument resource operations for Crucible API.

Provides organized access to instrument-related API endpoints.
"""

import logging
from typing import Optional, List, Dict
from .base import BaseResource
from ..constants import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class InstrumentOperations(BaseResource):
    """Instrument-related API operations.

    Access via: client.instruments.get(), client.instruments.list(), etc.
    """

    def list(self, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List all available instruments.

        Args:
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: Instrument objects with specifications and metadata
        """
        result = self._request('get', '/instruments')
        return result

    def get(self, instrument_name: Optional[str] = None, instrument_id: Optional[str] = None) -> Dict:
        """Get instrument information by name or ID.

        Args:
            instrument_name (str, optional): Name of the instrument
            instrument_id (str, optional): Unique ID of the instrument

        Returns:
            Dict or None: Instrument information if found, None otherwise

        Raises:
            ValueError: If neither parameter is provided
        """
        if not instrument_name and not instrument_id:
            raise ValueError("Either instrument_name or instrument_id must be provided")

        if instrument_id:
            logger.debug("Using Instrument ID to find Instrument")
            params = {"unique_id": instrument_id}
        else:
            params = {"instrument_name": instrument_name}

        found_inst = self._request('get', '/instruments', params=params)

        if len(found_inst) > 0:
            return found_inst[-1]
        else:
            return None

    def get_or_create(self, instrument_name: str, location: Optional[str] = None,
                     instrument_owner: Optional[str] = None) -> Dict:
        """Get an existing instrument or create a new one if it doesn't exist.

        **Requires admin permissions for instrument creation.**

        Args:
            instrument_name (str): Name of the instrument
            location (str, optional): Location where instrument was created
            instrument_owner (str, optional): Owner of the instrument

        Returns:
            Dict: Instrument information (existing or newly created)

        Raises:
            ValueError: If instrument doesn't exist and location/owner not provided

        Example:
            >>> # Get existing instrument
            >>> inst = client.instruments.get_or_create("TEM-2100")

            >>> # Create new instrument if it doesn't exist
            >>> inst = client.instruments.get_or_create(
            ...     "New-Microscope",
            ...     location="Building 67",
            ...     instrument_owner="Lab Manager"
            ... )
        """
        found_inst = self.get(instrument_name)

        if found_inst:
            return found_inst
        elif any([location is None, instrument_owner is None]):
            raise ValueError('Instrument does not exist, please provide location and owner')
        else:
            new_instrum = {
                "instrument_name": instrument_name,
                "location": location,
                "owner": instrument_owner
            }
            logger.debug(f"Creating new instrument: {new_instrum}")
            instrument = self._request('post', '/instruments', json=new_instrum)
            return instrument
