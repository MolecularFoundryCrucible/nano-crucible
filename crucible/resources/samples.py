#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample resource operations for Crucible API.

Provides organized access to sample-related API endpoints.
"""

import logging
from typing import Optional, List, Dict
from .base import BaseResource
from ..constants import DEFAULT_LIMIT, API_PAGE_MAX

logger = logging.getLogger(__name__)


class SampleOperations(BaseResource):
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

    def get(self, sample_id: str, include_links: bool = False,
            include_metadata: bool = False) -> Dict:
        """Get sample information by ID.

        Args:
            sample_id (str): Sample unique identifier
            include_links (bool): Whether to include immediate parent/child/associated links
            include_metadata (bool): Whether to include scientific metadata

        Returns:
            Dict: Sample information with optional links and metadata
        """
        params = {}
        if include_links:
            params['include_links'] = True
        if include_metadata:
            params['include_metadata'] = True
        raw = self._request('get', f"/samples/{sample_id}", params=params or None)
        return self._parse(raw) if raw is not None else None

    def list(self, dataset_id: Optional[str] = None, parent_id: Optional[str] = None,
             include_metadata: bool = False, limit: int = DEFAULT_LIMIT,
             offset: int = 0, **kwargs) -> List[Dict]:
        """List samples with optional filtering and automatic pagination.

        Args:
            dataset_id (str, optional): Get samples from specific dataset
            parent_id (str, optional): Get child samples from parent (deprecated)
            include_metadata (bool): Include scientific metadata in results
            limit (int): Maximum total results to return (default: 100). Requests
                         above API_PAGE_MAX (1000) are handled transparently via
                         parallel pagination.
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Sample information
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if include_metadata:
            params['include_metadata'] = True
        if dataset_id:
            endpoint = f"/datasets/{dataset_id}/samples"
        elif parent_id:
            logger.warning('Using parent_id with list() is deprecated. Please use list_children() instead.')
            endpoint = f"/samples/{parent_id}/children"
        else:
            endpoint = "/samples"
        raw = self._paginate(endpoint, params, limit, offset)
        return [self._parse(s) for s in raw]

    def list_parents(self, sample_id: str, limit: int = DEFAULT_LIMIT,
                     offset: int = 0, **kwargs) -> List[Dict]:
        """List the parents of a given sample with optional filtering.

        Args:
            sample_id (str): The unique ID of the sample for which you want to find the parents
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Parent samples
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self._paginate(f"/samples/{sample_id}/parents", params, limit, offset)

    def list_children(self, sample_id: str, limit: int = DEFAULT_LIMIT,
                      offset: int = 0, **kwargs) -> List[Dict]:
        """List the children of a given sample with optional filtering.

        Args:
            sample_id (str): The unique ID of the sample for which you want to find the children
            limit (int): Maximum number of results to return (default: 100)
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Children samples
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self._paginate(f"/samples/{sample_id}/children", params, limit, offset)

    def create(self, unique_id: Optional[str] = None, sample_name: Optional[str] = None,
               description: Optional[str] = None, timestamp: Optional[str] = None,
               owner_orcid: Optional[str] = None, owner_user_id: Optional[int] = None,
               project_id: Optional[str] = None, sample_type: Optional[str] = None,
               public: Optional[bool] = None,
               parents: List[Dict] = [], children: List[Dict] = [],
               scientific_metadata: Optional[Dict] = None,
               # deprecated aliases (creation_time/modification_time are server-assigned)
               date_created: Optional[str] = None, creation_date: Optional[str] = None,
               owner_id: Optional[int] = None) -> Dict:
        """Add a new sample with optional parent-child relationships.

        Args:
            unique_id (str, optional): Unique sample identifier
            sample_name (str, optional): Human-readable sample name
            sample_type (str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            timestamp (str, optional): User-defined timestamp
            owner_orcid (str, optional): Owner's ORCID
            owner_user_id (int, optional): Owner's user ID
            project_id (str, optional): Project ID (Name)
            parents (List[Dict], optional): Parent samples
            children (List[Dict], optional): Child samples
            scientific_metadata (Dict, optional): Scientific metadata to attach after creation

        Returns:
            Dict: Created sample object

        Raises:
            Exception: If neither unique_id nor sample_name is provided
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
        if owner_id is not None:
            warnings.warn(
                "Parameter 'owner_id' is deprecated; use 'owner_user_id' instead.",
                DeprecationWarning, stacklevel=2
            )
            if owner_user_id is None:
                owner_user_id = owner_id

        sample_info = {
            "unique_id": unique_id,
            "sample_name": sample_name,
            "sample_type": sample_type,
            "owner_orcid": owner_orcid,
            "owner_user_id": owner_user_id,
            "description": description,
            "project_id": project_id,
            "timestamp": timestamp,
        }
        if public is not None:
            sample_info["public"] = public

        if unique_id is None and sample_name is None:
            raise Exception('Please provide either a unique ID or a sample name for your sample')

        new_samp = self._request('post', "/samples", json=sample_info)
        sid = new_samp['unique_id']

        for p in parents:
            self._request('post', f"/samples/{p['unique_id']}/children/{sid}")

        for chd in children:
            self._request('post', f"/samples/{sid}/children/{chd['unique_id']}")

        if scientific_metadata:
            self.add_scientific_metadata(sid, scientific_metadata)

        return new_samp

    def update(self, unique_id: str, sample_name: Optional[str] = None,
               description: Optional[str] = None, timestamp: Optional[str] = None,
               owner_orcid: Optional[str] = None, owner_user_id: Optional[int] = None,
               project_id: Optional[str] = None, sample_type: Optional[str] = None,
               parents: List[Dict] = [], children: List[Dict] = [],
               # deprecated aliases (creation_time/modification_time are server-assigned)
               date_created: Optional[str] = None, creation_date: Optional[str] = None,
               owner_id: Optional[int] = None) -> Dict:
        """Update an existing sample.

        Args:
            unique_id (str): Sample unique identifier (required)
            sample_name (str, optional): Human-readable sample name
            sample_type (str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            timestamp (str, optional): User-defined timestamp
            owner_orcid (str, optional): Owner's ORCID
            owner_user_id (int, optional): Owner's user ID
            project_id (str, optional): Project ID (Name)
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
        if owner_id is not None:
            warnings.warn(
                "Parameter 'owner_id' is deprecated; use 'owner_user_id' instead.",
                DeprecationWarning, stacklevel=2
            )
            if owner_user_id is None:
                owner_user_id = owner_id

        sample_info = {
            "unique_id": unique_id,
            "sample_name": sample_name,
            "owner_orcid": owner_orcid,
            "owner_user_id": owner_user_id,
            "sample_type": sample_type,
            "description": description,
            "project_id": project_id,
            "timestamp": timestamp,
        }

        sample_info = {k: v for k, v in sample_info.items() if v is not None}

        upd_samp = self._request('patch', f"/samples/{unique_id}", json=sample_info)

        for p in parents:
            parent_id = p['unique_id']
            child_id = upd_samp['unique_id']
            self._request('post', f"/samples/{parent_id}/children/{child_id}")

        for chd in children:
            parent_id = upd_samp['unique_id']
            child_id = chd['unique_id']
            self._request('post', f"/samples/{parent_id}/children/{child_id}")

        return upd_samp

    def add_scientific_metadata(self, sample_id: str, metadata: Dict) -> Dict:
        """Create scientific metadata for a sample.

        Args:
            sample_id (str): Sample unique identifier
            metadata (Dict): Scientific metadata dictionary

        Returns:
            Dict: Created metadata object
        """
        return self._request('post', f'/resources/{sample_id}/metadata', json=metadata)

    def update_scientific_metadata(self, sample_id: str, metadata: Dict,
                                   overwrite: bool = False) -> Dict:
        """Update scientific metadata for a sample.

        Args:
            sample_id (str): Sample unique identifier
            metadata (Dict): Scientific metadata dictionary
            overwrite (bool): If True, replace all metadata (POST); if False, merge with existing (PATCH)

        Returns:
            Dict: Updated metadata object
        """
        if overwrite:
            return self._request('post', f'/resources/{sample_id}/metadata', json=metadata)
        return self._request('patch', f'/resources/{sample_id}/metadata', json=metadata)

    def add_dataset(self, sample_id: str, dataset_id: str) -> Dict:
        """Link a dataset to this sample.

        Delegates to DatasetOperations.add_sample — single implementation.

        Args:
            sample_id (str): Sample unique identifier
            dataset_id (str): Dataset unique identifier

        Returns:
            Dict: Information about the created link
        """
        return self._client.datasets.add_sample(dataset_id, sample_id)

    def remove_dataset(self, sample_id: str, dataset_id: str) -> Dict:
        """Remove the link between a sample and a dataset.

        **Requires admin permissions.**

        Args:
            sample_id (str): Sample unique identifier
            dataset_id (str): Dataset unique identifier

        Returns:
            Dict: Deletion confirmation
        """
        return self._client.datasets.remove_sample(dataset_id, sample_id)

    def add_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Deprecated: use add_dataset(sample_id, dataset_id) instead."""
        import warnings
        warnings.warn(
            "add_to_dataset() is deprecated; use add_dataset(sample_id, dataset_id) instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.add_dataset(sample_id, dataset_id)

    def remove_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Deprecated: use remove_dataset(sample_id, dataset_id) instead."""
        import warnings
        warnings.warn(
            "remove_from_dataset() is deprecated; use remove_dataset(sample_id, dataset_id) instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.remove_dataset(sample_id, dataset_id)

    def remove_child(self, parent_id: str, child_id: str) -> Dict:
        """Remove the parent-child link between two samples.

        Args:
            parent_id (str): Unique sample identifier of parent sample
            child_id (str): Unique sample identifier of child sample

        Returns:
            Dict: Deletion confirmation
        """
        return self._request('delete', f"/samples/{parent_id}/children/{child_id}")

    def link(self, parent_id: str, child_id: str) -> Dict:
        """Link two samples with a parent-child relationship.

        Args:
            parent_id (str): Unique sample identifier of parent sample
            child_id (str): Unique sample identifier of child sample

        Returns:
            Dict: Created link object
        """
        return self._request('post', f"/samples/{parent_id}/children/{child_id}")

    def graph(self, sample_id: str, recursive: bool = False, as_networkx: bool = False):
        """Return the graph of entities connected to this sample.

        Delegates to client.graphs.get(). See GraphOperations.get() for full docs.

        Args:
            sample_id (str): Sample unique identifier.
            recursive (bool): If True, traverse the full connected component.
            as_networkx (bool): Return a networkx DiGraph if True.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        return self._client.graphs.get(sample_id, recursive=recursive, as_networkx=as_networkx)
