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

    def list(self, include_metadata: bool = False, limit: int = DEFAULT_LIMIT,
             offset: int = 0) -> List[Dict]:
        """List all available instruments.

        Args:
            include_metadata (bool): Include scientific metadata in results
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)

        Returns:
            List[Dict]: Instrument objects with specifications and metadata
        """
        params = {}
        if include_metadata:
            params['include_metadata'] = True
        return self._paginate('/instruments', params, limit, offset)

    def get(self, instrument_name: Optional[str] = None, instrument_id: Optional[str] = None,
            include_metadata: bool = False) -> Dict:
        """Get instrument information by name or ID.

        Args:
            instrument_name (str, optional): Name of the instrument
            instrument_id (str, optional): Unique ID of the instrument
            include_metadata (bool): Whether to include scientific metadata

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

        if include_metadata:
            params['include_metadata'] = True

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

    def update(self, unique_id: str, **kwargs) -> Dict:
        """Partially update an instrument record.

        **Requires admin permissions.**

        Args:
            unique_id (str): Instrument unique identifier (MFID)
            **kwargs: Fields to update. Accepted: instrument_name, owner, location,
                      manufacturer, model, instrument_type, description.

        Returns:
            Dict: Updated instrument object
        """
        return self._request('patch', f'/instruments/{unique_id}', json=kwargs)

    def add_scientific_metadata(self, instrument_id: str, metadata: Dict) -> Dict:
        """Create scientific metadata for an instrument.

        Args:
            instrument_id (str): Instrument unique identifier
            metadata (Dict): Scientific metadata dictionary

        Returns:
            Dict: Created metadata object
        """
        return self._request('post', f'/metadata/{instrument_id}', json=metadata)

    def update_scientific_metadata(self, instrument_id: str, metadata: Dict,
                                   overwrite: bool = False) -> Dict:
        """Update scientific metadata for an instrument.

        Args:
            instrument_id (str): Instrument unique identifier
            metadata (Dict): Scientific metadata dictionary
            overwrite (bool): If True, replace all metadata (POST); if False, merge with existing (PATCH)

        Returns:
            Dict: Updated metadata object
        """
        if overwrite:
            return self._request('post', f'/metadata/{instrument_id}', json=metadata)
        return self._request('patch', f'/metadata/{instrument_id}', json=metadata)

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
