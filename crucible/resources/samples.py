#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample resource operations for Crucible API.

Provides organized access to sample-related API endpoints.
"""

import logging
from typing import Optional, List, Dict, Sequence, Union
from .base import BaseResource
from .capabilities import AccessControlMixin, OwnershipMixin, ProjectAssignmentMixin
from ..constants import DEFAULT_LIMIT, API_PAGE_MAX
from ..utils.deprecation import _deprecated_parameter
from ..utils.identifiers import is_mfid, require_canonical_identifier

logger = logging.getLogger(__name__)


class SampleOperations(ProjectAssignmentMixin, OwnershipMixin, AccessControlMixin, BaseResource):
    """Sample-related API operations.

    Access via: client.samples.get(), client.samples.list(), etc.
    """

    @staticmethod
    def _parse(raw: Dict) -> Dict:
        """Validate a raw API response dict through the Sample Pydantic model.

        Normalises field aliases (e.g. date_created → timestamp) and preserves
        any extra fields returned by the server (datasets, keywords, …).
        """
        from ..models import Sample
        return Sample.model_validate(raw).model_dump()

    @_deprecated_parameter('sample_id', 'sample_mfid')
    def get(self, sample_mfid: str, include_links: bool = False,
            include_metadata: bool = False, include_owner: bool = True,
            include_datasets: bool = True) -> Dict:
        """Get a sample by its canonical MFID.

        Args:
            sample_mfid (str): Sample MFID
            include_links (bool): Whether to include immediate parent/child/associated links
            include_metadata (bool): Whether to include scientific metadata
            include_owner (bool): Resolve owner_orcid into a public-safe user object (default: True)
            include_datasets (bool): Include deprecated embedded dataset records (default: True). Set False and use include_links or client.datasets.list(sample_mfid=...) instead.

        Returns:
            Dict: Sample information with optional links and metadata
        """
        return self._get_by_mfid(
            sample_mfid,
            include_links=include_links,
            include_metadata=include_metadata,
            include_owner=include_owner,
            include_datasets=include_datasets,
        )

    def _get_by_mfid(self, sample_mfid: str, include_links: bool = False,
                     include_metadata: bool = False,
                     include_owner: bool = True,
                     include_datasets: bool = True) -> Dict:
        """Get a sample through its canonical single-resource route."""
        if not is_mfid(sample_mfid):
            raise ValueError("sample_mfid must be an exact 26-character MFID.")
        params = {}
        if include_links:
            params['include_links'] = True
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True
        if not include_datasets:
            params['include_datasets'] = False
        raw = self._request('get', f"/samples/{sample_mfid}", params=params or None)
        if raw is None:
            return None
        return self._parse(require_canonical_identifier(raw, 'sample'))

    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    @_deprecated_parameter('parent_id', 'parent_mfid')
    @_deprecated_parameter('parent_sample_mfid', 'parent_mfid')
    def list(self, dataset_mfid: Optional[str] = None,
             parent_mfid: Optional[str] = None,
             include_metadata: bool = False, include_links: bool = False,
             include_owner: bool = False, limit: int = DEFAULT_LIMIT,
             offset: int = 0,
             accessible_to_user: Optional[Union[str, Sequence[str]]] = None,
             accessible_to_project: Optional[Union[str, Sequence[str]]] = None,
             **kwargs) -> List[Dict]:
        """List samples with optional filtering and automatic pagination.

        Args:
            dataset_mfid (str, optional): Get samples linked to this dataset MFID
            parent_mfid (str, optional): Get child samples from this parent MFID
            include_metadata (bool): Include scientific metadata in results
            include_links (bool): Include linked resources (parents, children, associated) per sample
            include_owner (bool): Resolve owner_orcid into a public-safe user object per sample
            limit (int): Maximum total results to return (default: 100). Larger
                         requests are handled transparently by following the
                         server's keyset cursor. Pass None to fetch all matches.
            offset (int): Deprecated for the /samples collection, which uses
                          keyset pagination and ignores offset. Still honored for
                          the parent-child sub-listing.
            accessible_to_user: User reference or references whose effective access
                                must include every result
            accessible_to_project: Project reference or references whose direct access
                                   must include every result
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Sample information
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        selectors = self._access_selector_params(
            accessible_to_user, accessible_to_project)
        if parent_mfid and selectors:
            raise ValueError("Access selectors are supported only by the top-level sample list")
        params.update(selectors)
        if dataset_mfid is not None:
            params['dataset_mfid'] = dataset_mfid
        if include_metadata:
            params['include_metadata'] = True
        if include_links:
            params['include_links'] = True
        if include_owner:
            params['include_owner'] = True
        if parent_mfid and dataset_mfid is None:
            endpoint = f"/samples/{parent_mfid}/children"
        else:
            endpoint = "/samples"
            if offset:
                import warnings
                warnings.warn(
                    "'offset' is ignored by /samples, which now uses keyset "
                    "pagination; results start from the newest sample.",
                    DeprecationWarning, stacklevel=2,
                )
        raw = self._paginate(endpoint, params, limit, offset)
        return [self._parse(s) for s in raw]

    def count(self, **kwargs) -> int:
        """Return the total number of samples matching the given filters without fetching items."""
        params = {k: v for k, v in kwargs.items() if v is not None}
        result = self._request('get', '/samples', params={**params, 'limit': 1})
        return result['total']

    @_deprecated_parameter('sample_id', 'child_mfid')
    @_deprecated_parameter('sample_mfid', 'child_mfid')
    def list_parents(self, child_mfid: str, limit: int = DEFAULT_LIMIT,
                     offset: int = 0, relationship_type: Optional[str] = None,
                     **kwargs) -> List[Dict]:
        """List the parents of a given sample with optional filtering.

        Args:
            child_mfid (str): Child sample MFID
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            relationship_type (str, optional): Only return parents linked with
                this kind of link, one of crucible.constants.RELATIONSHIP_TYPES.
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Parent samples
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if relationship_type is not None:
            params['relationship_type'] = relationship_type
        return self._paginate(f"/samples/{child_mfid}/parents", params, limit, offset)

    @_deprecated_parameter('sample_id', 'parent_mfid')
    @_deprecated_parameter('sample_mfid', 'parent_mfid')
    def list_children(self, parent_mfid: str, limit: int = DEFAULT_LIMIT,
                      offset: int = 0, relationship_type: Optional[str] = None,
                      **kwargs) -> List[Dict]:
        """List the children of a given sample with optional filtering.

        Args:
            parent_mfid (str): Parent sample MFID
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            relationship_type (str, optional): Only return children linked with
                this kind of link, one of crucible.constants.RELATIONSHIP_TYPES.
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Children samples
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if relationship_type is not None:
            params['relationship_type'] = relationship_type
        return self._paginate(f"/samples/{parent_mfid}/children", params, limit, offset)

    def create(self, sample=None, scientific_metadata: Optional[Dict] = None,
               parents: List[Dict] = [], children: List[Dict] = [],
               **kwargs) -> Dict:
        """Create a new sample record.

        Args:
            sample (Sample): Sample model instance with the desired fields. Use
                `owner` with an ORCID, MFID, username, or email to
                create for a specific owner. `owner_orcid` is deprecated for
                creation. Providing both fields is invalid.
            scientific_metadata (dict, optional): Scientific metadata to attach after creation.
            parents (list, optional): Parent samples to link ({unique_id: ...}).
            children (list, optional): Child samples to link ({unique_id: ...}).

        Returns:
            Dict: Created sample record.
        """
        import warnings
        from crucible.models import Sample

        if sample is None or not isinstance(sample, Sample):
            if sample is not None:
                # positional arg was not a Sample — treat it as a mistake
                raise TypeError(
                    f"Expected a Sample model, got {type(sample).__name__}. "
                    "Use: samples.create(Sample(sample_name=..., project_id=...))"
                )
            if kwargs:
                warnings.warn(
                    "Passing keyword arguments to samples.create() is deprecated. "
                    "Pass a Sample model instead: samples.create(Sample(...))",
                    DeprecationWarning, stacklevel=2
                )
                # strip keys the model doesn't know
                _dropped = {'date_created', 'creation_date', 'owner_id', 'owner_user_id'}
                kwargs = {k: v for k, v in kwargs.items() if k not in _dropped}
                sample = Sample(**kwargs)
            else:
                raise ValueError("Pass a Sample model: samples.create(Sample(...))")

        sample_info = {
            k: v for k, v in sample.model_dump(
                exclude={'capabilities', 'project'}).items()
            if v is not None
        }

        if sample_info.get('owner') is not None and sample_info.get('owner_orcid') is not None:
            raise ValueError("Pass either 'owner' or 'owner_orcid', not both.")
        if sample_info.get('owner_orcid') is not None:
            warnings.warn(
                "Sample.owner_orcid is deprecated for creation; use Sample.owner "
                "with an ORCID, MFID, username, or email instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if sample_info.get('owner') is not None and not isinstance(sample_info['owner'], str):
            raise ValueError("Sample.owner must be a string identifier when creating a sample.")

        new_samp = self._parse(
            self._request('post', "/samples", json=sample_info))
        sample_mfid = new_samp['unique_id']

        for p in parents:
            self._request('post', f"/samples/{p['unique_id']}/children/{sample_mfid}")
        for chd in children:
            self._request('post', f"/samples/{sample_mfid}/children/{chd['unique_id']}")

        if scientific_metadata:
            self.update_scientific_metadata(sample_mfid, scientific_metadata)

        return new_samp

    @_deprecated_parameter('unique_id', 'sample_mfid')
    def update(self, sample_mfid: str, sample_name: Optional[str] = None,
               description: Optional[str] = None, timestamp: Optional[str] = None,
               owner_orcid: Optional[str] = None,
               project_id: Optional[str] = None, sample_type: Optional[str] = None,
               public: Optional[bool] = None,
               parents: List[Dict] = [], children: List[Dict] = [],
               # deprecated aliases (creation_time/modification_time are server-assigned)
               date_created: Optional[str] = None, creation_date: Optional[str] = None,
               owner_id: Optional[int] = None,
               owner_user_id: Optional[int] = None) -> Dict:
        """Update an existing sample.

        Args:
            sample_mfid (str): Sample MFID
            sample_name (str, optional): Human-readable sample name
            sample_type (str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            timestamp (str, optional): User-defined timestamp
            owner_orcid (str, optional): Deprecated - the API no longer accepts this
                field here; use client.samples.transfer_ownership() instead.
            public (bool, optional): Whether the sample is publicly visible
            project_id (str, optional): Deprecated - the API no longer accepts this
                field here; use client.samples.reassign_project() instead.
            parents (List[Dict], optional): Parent samples to link
            children (List[Dict], optional): Child samples to link

        Returns:
            Dict: Updated sample object
        """
        import warnings
        if date_created is not None:
            warnings.warn(
                "Parameter 'date_created' is deprecated and ignored; "
                "creation_time is now assigned server-side.",
                DeprecationWarning, stacklevel=2
            )
        if creation_date is not None:
            warnings.warn(
                "Parameter 'creation_date' is deprecated and ignored; "
                "creation_time is now assigned server-side.",
                DeprecationWarning, stacklevel=2
            )
        if owner_id is not None or owner_user_id is not None:
            warnings.warn(
                "Parameters 'owner_id'/'owner_user_id' are deprecated and ignored; "
                "use 'owner_orcid' instead.",
                DeprecationWarning, stacklevel=2
            )
        if owner_orcid is not None:
            warnings.warn(
                "Parameter 'owner_orcid' is no longer accepted by PATCH /samples/{id} "
                "and is ignored; use client.samples.transfer_ownership() instead.",
                DeprecationWarning, stacklevel=2
            )
        if project_id is not None:
            warnings.warn(
                "Parameter 'project_id' is no longer accepted by PATCH /samples/{id} "
                "and is ignored; use client.samples.reassign_project() instead.",
                DeprecationWarning, stacklevel=2
            )

        sample_info = {
            "sample_name": sample_name,
            "sample_type": sample_type,
            "public": public,
            "description": description,
            "timestamp": timestamp,
        }

        sample_info = {k: v for k, v in sample_info.items() if v is not None}

        upd_samp = self._request('patch', f"/samples/{sample_mfid}", json=sample_info)

        for p in parents:
            parent_sample_mfid = p['unique_id']
            child_sample_mfid = upd_samp['unique_id']
            self._request(
                'post', f"/samples/{parent_sample_mfid}/children/{child_sample_mfid}")

        for chd in children:
            parent_sample_mfid = upd_samp['unique_id']
            child_sample_mfid = chd['unique_id']
            self._request(
                'post', f"/samples/{parent_sample_mfid}/children/{child_sample_mfid}")

        return upd_samp

    @_deprecated_parameter('sample_id', 'sample_mfid')
    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    def add_dataset(self, sample_mfid: str, dataset_mfid: str) -> Dict:
        """Link a dataset to this sample.

        Delegates to DatasetOperations.add_sample — single implementation.

        Args:
            sample_mfid (str): Sample MFID
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: Information about the created link
        """
        return self._client.datasets.add_sample(dataset_mfid, sample_mfid)

    @_deprecated_parameter('sample_id', 'sample_mfid')
    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    def remove_dataset(self, sample_mfid: str, dataset_mfid: str) -> Dict:
        """Remove the link between a sample and a dataset.

        **Requires admin permissions.**

        Args:
            sample_mfid (str): Sample MFID
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: Deletion confirmation
        """
        return self._client.datasets.remove_sample(dataset_mfid, sample_mfid)

    def add_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Deprecated: use add_dataset(sample_mfid, dataset_mfid) instead."""
        import warnings
        warnings.warn(
            "add_to_dataset() is deprecated; use add_dataset(sample_mfid, dataset_mfid) instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.add_dataset(sample_id, dataset_id)

    def remove_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Deprecated: use remove_dataset(sample_mfid, dataset_mfid) instead."""
        import warnings
        warnings.warn(
            "remove_from_dataset() is deprecated; use remove_dataset(sample_mfid, dataset_mfid) instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.remove_dataset(sample_id, dataset_id)

    @_deprecated_parameter('parent_id', 'parent_mfid')
    @_deprecated_parameter('parent_sample_mfid', 'parent_mfid')
    @_deprecated_parameter('child_id', 'child_mfid')
    @_deprecated_parameter('child_sample_mfid', 'child_mfid')
    def remove_child(self, parent_mfid: str, child_mfid: str) -> Dict:
        """Remove the parent-child link between two samples.

        Args:
            parent_mfid (str): Parent sample MFID
            child_mfid (str): Child sample MFID

        Returns:
            Dict: Deletion confirmation
        """
        return self._request(
            'delete', f"/samples/{parent_mfid}/children/{child_mfid}")

    @_deprecated_parameter('parent_id', 'parent_mfid')
    @_deprecated_parameter('parent_sample_mfid', 'parent_mfid')
    @_deprecated_parameter('child_id', 'child_mfid')
    @_deprecated_parameter('child_sample_mfid', 'child_mfid')
    def link(self, parent_mfid: str, child_mfid: str,
             relationship_type: Optional[str] = None) -> Dict:
        """Link two samples with a parent-child relationship.

        Args:
            parent_mfid (str): Parent sample MFID
            child_mfid (str): Child sample MFID
            relationship_type (str, optional): Kind of link, one of
                crucible.constants.RELATIONSHIP_TYPES. Describes the child
                relative to the parent, so 'is_part_of' reads "child
                is_part_of parent". Omit to leave the kind unspecified; on a
                link that already exists, omitting it preserves the type
                already stored rather than clearing it.

        Returns:
            Dict: Created link object
        """
        # Send the parameter only when the caller set it: the server treats a
        # supplied relationship_type as an overwrite, so an unconditional
        # param would clear the stored type on a re-link that just meant
        # "make sure this link exists".
        extra = ({'params': {'relationship_type': relationship_type}}
                 if relationship_type is not None else {})
        return self._request(
            'post', f"/samples/{parent_mfid}/children/{child_mfid}", **extra)

    def search(self, q: str, project_id: Optional[str] = None,
               limit: int = 20) -> List[Dict]:
        """Fuzzy name search across samples. Available to all authenticated users.

        Matches against sample_name. Returns samples the caller can read.
        For scientific metadata search use search_metadata().

        Args:
            q: Search term (min 3 chars). Typo-tolerant.
            project_id: Optional project to scope results to.
            limit: Max results (default 20, max 50).

        Returns:
            List[Dict]: Matching SampleResponse records, ranked by relevance.
        """
        params = {'q': q, 'limit': limit}
        if project_id:
            params['project_id'] = project_id
        result = self._request('get', '/samples/search', params=params)
        return result.get('items', result) if isinstance(result, dict) else result

    @_deprecated_parameter('sample_id', 'sample_mfid')
    def graph(self, sample_mfid: str, recursive: bool = False,
              as_networkx: bool = False):
        """Return the graph of entities connected to this sample.

        Delegates to client.graphs.get(). See GraphOperations.get() for full docs.

        Args:
            sample_mfid (str): Sample MFID.
            recursive (bool): If True, traverse the full connected component.
            as_networkx (bool): Return a networkx DiGraph if True.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        return self._client.graphs.get(
            sample_mfid, recursive=recursive, as_networkx=as_networkx)

    @_deprecated_parameter('sample_id', 'sample_mfid')
    def download(self, sample_mfid: str,
                 output_dir: str = 'crucible-downloads') -> List[str]:
        """Save the sample record as record.json.

        Args:
            sample_mfid: Sample MFID
            output_dir: Directory to save the record (default: 'crucible-downloads/')

        Returns:
            List[str]: Path to the saved record.json
        """
        import json as _json
        import os

        record = self.get(sample_mfid, include_metadata=True)
        record_dir = os.path.join(output_dir, sample_mfid)
        os.makedirs(record_dir, exist_ok=True)
        json_path  = os.path.join(record_dir, 'record.json')
        with open(json_path, 'w') as fh:
            _json.dump(record, fh, indent=2)
        logger.info(f"Saved record to {json_path}")
        return [json_path]
