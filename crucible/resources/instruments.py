#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument resource operations for Crucible API.

Provides organized access to instrument-related API endpoints.
"""

import logging
from typing import Optional, List, Dict
from .base import BaseResource
from .capabilities import AccessControlMixin, OwnershipMixin
from ..constants import DEFAULT_LIMIT
from ..utils.identifiers import (
    IdentifierNotFoundError,
    classify_slug_reference,
    collapse_exact_lookup,
    is_mfid,
    require_canonical_identifier,
    validate_slug,
)

logger = logging.getLogger(__name__)


class InstrumentOperations(OwnershipMixin, AccessControlMixin, BaseResource):
    """Instrument-related API operations.

    Access via: client.instruments.get(), client.instruments.list(), etc.
    """

    @staticmethod
    def _parse(raw: Dict) -> Dict:
        """Validate an API response through the Instrument model."""
        from ..models import Instrument
        return Instrument.model_validate(raw).model_dump()

    def list(self, include_metadata: bool = False, limit: int = DEFAULT_LIMIT,
             offset: int = 0, include_owner: bool = False,
             status: Optional[str] = None) -> List[Dict]:
        """List instruments, defaulting to the active lifecycle state.

        Args:
            include_metadata (bool): Include scientific metadata in results
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)
            include_owner (bool): Resolve owner_orcid into a public-safe user object
            status (str, optional): Filter by active, maintenance, or decommissioned.
                                    When omitted, the API defaults to active.

        Returns:
            List[Dict]: Instrument objects with specifications and metadata
        """
        params = {}
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True
        if status is not None:
            allowed = {'active', 'maintenance', 'decommissioned'}
            if status not in allowed:
                raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
            params['status'] = status
        return [self._parse(item) for item in self._paginate('/instruments', params, limit, offset)]

    def get(self, instrument_ref: Optional[str] = None,
            instrument_id: Optional[str] = None,
            include_metadata: bool = False, include_owner: bool = True,
            *, instrument_mfid: Optional[str] = None,
            instrument_name: Optional[str] = None) -> Dict:
        """Get an instrument by canonical MFID or human-readable slug.

        ``instrument_id`` explicitly selects the human-readable API identifier.
        An MFID-shaped value remains temporarily compatible with its former
        meaning and emits a deprecation warning.

        Args:
            instrument_ref (str, optional): Instrument MFID or slug
            instrument_id (str, optional): Explicit instrument slug
            include_metadata (bool): Whether to include scientific metadata
            include_owner (bool): Resolve owner_orcid into a public-safe user object (default: True)
            instrument_mfid (str, optional): Explicit instrument MFID
            instrument_name (str, optional): Deprecated display-name lookup

        Returns:
            Dict or None: Instrument information if found, None otherwise

        Raises:
            ValueError: If no reference or multiple references are provided
        """
        provided = [
            value for value in
            (instrument_ref, instrument_id, instrument_mfid, instrument_name)
            if value is not None
        ]
        if len(provided) != 1:
            raise ValueError("Provide exactly one instrument reference.")

        if instrument_name is not None:
            import warnings
            warnings.warn(
                "instrument_name lookup is deprecated because display names are not unique; "
                "pass an instrument MFID or instrument_id slug instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._get_by_name(instrument_name, include_metadata=include_metadata,
                                     include_owner=include_owner)
        if instrument_id is not None:
            if is_mfid(instrument_id):
                import warnings
                warnings.warn(
                    "Passing an MFID as instrument_id is deprecated; use instrument_mfid instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return self._get_by_mfid(instrument_id, include_metadata=include_metadata,
                                         include_owner=include_owner)
            return self._get_by_instrument_id(instrument_id, include_metadata=include_metadata,
                                              include_owner=include_owner)
        if instrument_mfid is not None:
            return self._get_by_mfid(instrument_mfid, include_metadata=include_metadata,
                                     include_owner=include_owner)

        reference_kind = classify_slug_reference(instrument_ref, 'instrument')
        if reference_kind == 'mfid':
            return self._get_by_mfid(instrument_ref, include_metadata=include_metadata,
                                     include_owner=include_owner)
        return self._get_by_instrument_id(instrument_ref, include_metadata=include_metadata,
                                          include_owner=include_owner)

    def _get_by_mfid(self, instrument_mfid: str,
                     include_metadata: bool = False,
                     include_owner: bool = True) -> Dict:
        """Get an instrument through its canonical single-resource route."""
        if not is_mfid(instrument_mfid):
            raise ValueError("instrument_mfid must be an exact 26-character MFID.")
        params = {}
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True
        raw = self._request('get', f'/instruments/{instrument_mfid}', params=params or None)
        if raw is None:
            return None
        return self._parse(require_canonical_identifier(raw, 'instrument'))

    def _get_by_instrument_id(self, instrument_id: str,
                              include_metadata: bool = False,
                              include_owner: bool = True) -> Dict:
        """Resolve an exact instrument slug through the collection route."""
        if not isinstance(instrument_id, str) or not instrument_id:
            raise ValueError("instrument_id must be a non-empty string.")
        params = {'instrument_id': instrument_id, 'limit': 2}
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True
        raw = self._request('get', '/instruments', params=params)
        return self._parse(collapse_exact_lookup(raw, 'instrument', instrument_id))

    def _get_by_name(self, instrument_name: str,
                     include_metadata: bool = False,
                     include_owner: bool = True) -> Dict:
        """Compatibility lookup for a non-unique instrument display name."""
        params = {'instrument_name': instrument_name, 'limit': 2}
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True
        raw = self._request('get', '/instruments', params=params)
        return self._parse(collapse_exact_lookup(raw, 'instrument', instrument_name))

    def create(self, instrument, scientific_metadata: Optional[Dict] = None) -> Dict:
        """Create a new instrument as an authenticated human caller.

        Service accounts cannot create instruments. If the instrument already
        exists, this method returns the existing record.

        Args:
            instrument: Instrument model or dict with instrument details.
                        Required fields: instrument_id, instrument_name, and location.
                        Owner defaults to the authenticated identity.
            scientific_metadata (Dict, optional): Scientific metadata to attach after creation.

        Returns:
            Dict: Created (or existing) instrument object

        Raises:
            ValueError: If instrument_id is missing
        """
        import warnings
        from ..models import Instrument
        if isinstance(instrument, Instrument):
            payload = instrument.model_dump(
                include={
                    'instrument_id',
                    'instrument_name',
                    'manufacturer',
                    'model',
                    'owner_orcid',
                    'owner',
                    'location',
                    'description',
                    'instrument_type',
                    'other_id',
                    'other_id_source',
                },
                exclude_none=True,
            )
        else:
            payload = dict(instrument)
            payload.pop('capabilities', None)

        if not payload.get('instrument_id'):
            raise ValueError(
                "instrument_id is required (a unique slug identifying the instrument, "
                "distinct from its auto-assigned MFID)."
            )
        validate_slug(payload['instrument_id'], 'instrument')
        if payload.get('owner') is not None and payload.get('owner_orcid') is not None:
            raise ValueError("Pass either 'owner' or 'owner_orcid', not both.")
        if payload.get('owner_orcid') is not None:
            warnings.warn(
                "Instrument.owner_orcid is deprecated for creation; use Instrument.owner "
                "with an ORCID, MFID, username, or email instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if payload.get('owner') is not None and not isinstance(payload['owner'], str):
            raise ValueError("Instrument.owner must be a string identifier when creating an instrument.")

        try:
            existing = self._get_by_instrument_id(payload['instrument_id'])
        except IdentifierNotFoundError:
            existing = None
        if existing:
            warnings.warn(
                f"Instrument '{payload['instrument_id']}' already exists; returning existing record.",
                UserWarning, stacklevel=2,
            )
            return existing

        result = self._request('post', '/instruments', json=payload)
        if scientific_metadata:
            self.update_scientific_metadata(result['unique_id'], scientific_metadata)
        return self._parse(result)

    def update(self, unique_id: str, **kwargs) -> Dict:
        """Partially update an instrument record.

        **Requires editor permission.**

        Args:
            unique_id (str): Instrument unique identifier (MFID)
            **kwargs: Fields to update. Accepted: instrument_id, instrument_name,
                      location, manufacturer, model, instrument_type, description,
                      other_id, other_id_source.

        Returns:
            Dict: Updated instrument object
        """
        if 'owner' in kwargs or 'owner_orcid' in kwargs:
            raise ValueError(
                "Instrument ownership cannot be changed with update(); "
                "use transfer_ownership() instead."
            )
        if 'capabilities' in kwargs:
            raise ValueError("Instrument capabilities are response-only.")
        if kwargs.get('instrument_id') is not None:
            validate_slug(kwargs['instrument_id'], 'instrument')
        return self._parse(self._request('patch', f'/instruments/{unique_id}', json=kwargs))

    def bind_service_account(self, instrument_mfid: str, sa_unique_id: str) -> List['ProjectMember']:
        """Bind a service account as an operator of an instrument.

        **Requires admin permissions.**

        Args:
            instrument_mfid (str): Instrument unique identifier (MFID)
            sa_unique_id (str): Service account unique identifier (MFID)

        Returns:
            List[ProjectMember]: The instrument's operator group members
        """
        from ..models import ProjectMember
        raw = self._request('post', f'/instruments/{instrument_mfid}/service_accounts/{sa_unique_id}')
        return [ProjectMember.model_validate(m) for m in raw]

    def unbind_service_account(self, instrument_mfid: str, sa_unique_id: str) -> List['ProjectMember']:
        """Remove a service account as an operator of an instrument.

        **Requires admin permissions.**

        Args:
            instrument_mfid (str): Instrument unique identifier (MFID)
            sa_unique_id (str): Service account unique identifier (MFID)

        Returns:
            List[ProjectMember]: The instrument's operator group members
        """
        from ..models import ProjectMember
        raw = self._request('delete', f'/instruments/{instrument_mfid}/service_accounts/{sa_unique_id}')
        return [ProjectMember.model_validate(m) for m in raw]

    def list_service_accounts(self, instrument_mfid: str) -> List['ProjectMember']:
        """List service accounts bound to an instrument.

        Args:
            instrument_mfid (str): Instrument unique identifier (MFID)

        Returns:
            List[ProjectMember]: Bound service accounts and their operator roles
        """
        from ..models import ProjectMember
        raw = self._request('get', f'/instruments/{instrument_mfid}/service_accounts')
        return [ProjectMember.model_validate(member) for member in raw]

    def set_status(self, instrument_mfid: str, status: str) -> Dict:
        """Change an instrument lifecycle status.

        Args:
            instrument_mfid (str): Instrument unique identifier (MFID)
            status (str): One of active, maintenance, or decommissioned

        Returns:
            Dict: Updated instrument response
        """
        allowed = {'active', 'maintenance', 'decommissioned'}
        if status not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        raw = self._request(
            'post', f'/instruments/{instrument_mfid}/status', params={'status': status})
        return self._parse(raw)

    def search(self, q: str, limit: int = 20,
               include_owner: bool = False,
               status: Optional[str] = None) -> List[Dict]:
        """Fuzzy search across instruments. Available to all authenticated users.

        Matches against instrument_name, instrument_type, and manufacturer
        (best score across the three).

        Args:
            q: Search term (min 3 chars). Typo-tolerant.
            limit: Max results (default 20, max 50).
            include_owner: Resolve owner_orcid into a public-safe user object.
            status: Restrict results to active, maintenance, or decommissioned.

        Returns:
            List[Dict]: Matching instrument records, ranked by relevance.
        """
        params = {'q': q, 'limit': limit}
        if include_owner:
            params['include_owner'] = True
        if status is not None:
            allowed = {'active', 'maintenance', 'decommissioned'}
            if status not in allowed:
                raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
            params['status'] = status
        result = self._request('get', '/instruments/search', params=params)
        items = result.get('items', result) if isinstance(result, dict) else result
        return [self._parse(item) for item in items]

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
