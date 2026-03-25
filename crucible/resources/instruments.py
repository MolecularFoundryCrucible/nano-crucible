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

    def create(self, instrument) -> Dict:
        """Create a new instrument, returning the existing one if it already exists.

        **Requires admin permissions.**

        Args:
            instrument: Instrument model or dict with instrument details.
                        Required fields: instrument_name, owner, location.

        Returns:
            Dict: Created (or existing) instrument object
        """
        import warnings
        from ..models import Instrument
        if isinstance(instrument, Instrument):
            payload = instrument.model_dump(exclude_none=True, exclude={'id', 'unique_id'})
        else:
            payload = dict(instrument)

        instrument_name = payload.get('instrument_name')
        if instrument_name:
            existing = self.get(instrument_name=instrument_name)
            if existing:
                warnings.warn(
                    f"Instrument '{instrument_name}' already exists; returning existing record.",
                    UserWarning, stacklevel=2,
                )
                return existing

        return self._request('post', '/instruments', json=payload)

    def get_or_create(self, instrument_name: str, location: Optional[str] = None,
                     instrument_owner: Optional[str] = None) -> Dict:
        """Deprecated: use create() instead.

        .. deprecated::
            Use :meth:`create` with an :class:`~crucible.models.Instrument` model.
            ``create()`` now checks for an existing instrument before posting.
        """
        import warnings
        warnings.warn(
            "get_or_create() is deprecated; use create() instead — "
            "it now checks for an existing instrument automatically.",
            DeprecationWarning, stacklevel=2,
        )
        from ..models import Instrument
        return self.create(Instrument(
            instrument_name=instrument_name,
            location=location,
            owner=instrument_owner,
        ))
