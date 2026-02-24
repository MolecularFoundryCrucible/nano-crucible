#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample resource operations for Crucible API.

Provides organized access to sample-related API endpoints.
"""

import logging
from typing import Optional, List, Dict
from .base import BaseResource
from ..constants import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class SampleOperations(BaseResource):
    """Sample-related API operations.

    Access via: client.samples.get(), client.samples.list(), etc.
    """

    def get(self, sample_id: str) -> Dict:
        """Get sample information by ID.

        Args:
            sample_id (str): Sample unique identifier

        Returns:
            Dict: Sample information with associated datasets
        """
        return self._request('get', f"/samples/{sample_id}")

    def list(self, dataset_id: Optional[str] = None, parent_id: Optional[str] = None,
             limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List samples with optional filtering.

        Args:
            dataset_id (str, optional): Get samples from specific dataset
            parent_id (str, optional): Get child samples from parent (deprecated)
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Sample information
        """
        params = {**kwargs}
        if dataset_id:
            result = self._request('get', f"/datasets/{dataset_id}/samples", params=params)
        elif parent_id:
            logger.warning('Using parent_id with list() is deprecated. Please use list_children() instead.')
            result = self._request('get', f"/samples/{parent_id}/children", params=params)
        else:
            result = self._request('get', f"/samples", params=params)
        return result

    def list_parents(self, sample_id: str, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List the parents of a given sample with optional filtering.

        Args:
            sample_id (str): The unique ID of the sample for which you want to find the parents
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Parent samples
        """
        params = {**kwargs}
        params['limit'] = limit
        result = self._request('get', f"/samples/{sample_id}/parents", params=params)
        return result

    def list_children(self, sample_id: str, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List the children of a given sample with optional filtering.

        Args:
            sample_id (str): The unique ID of the sample for which you want to find the children
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Children samples
        """
        params = {**kwargs}
        params['limit'] = limit
        result = self._request('get', f"/samples/{sample_id}/children", params=params)
        return result

    def create(self, unique_id: Optional[str] = None, sample_name: Optional[str] = None,
               description: Optional[str] = None, creation_date: Optional[str] = None,
               owner_orcid: Optional[str] = None, owner_id: Optional[int] = None,
               project_id: Optional[str] = None, sample_type: Optional[str] = None,
               parents: List[Dict] = [], children: List[Dict] = []) -> Dict:
        """Add a new sample with optional parent-child relationships.

        Args:
            unique_id (str, optional): Unique sample identifier
            sample_name (str, optional): Human-readable sample name
            sample_type (str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            creation_date (str, optional): Sample creation date
            owner_orcid (str, optional): Owner's ORCID
            owner_id (int, optional): Owner's user ID
            project_id (str, optional): Project ID (Name)
            parents (List[Dict], optional): Parent samples
            children (List[Dict], optional): Child samples

        Returns:
            Dict: Created sample object

        Raises:
            Exception: If neither unique_id nor sample_name is provided
        """
        sample_info = {
            "unique_id": unique_id,
            "sample_name": sample_name,
            "sample_type": sample_type,
            "owner_orcid": owner_orcid,
            "owner_user_id": owner_id,
            "description": description,
            "project_id": project_id,
            "date_created": creation_date
        }

        if unique_id is None and sample_name is None:
            raise Exception('Please provide either a unique ID or a sample name for your sample')

        new_samp = self._request('post', "/samples", json=sample_info)

        for p in parents:
            parent_id = p['unique_id']
            child_id = new_samp['unique_id']
            self._request('post', f"/samples/{parent_id}/children/{child_id}")

        for chd in children:
            parent_id = new_samp['unique_id']
            child_id = chd['unique_id']
            self._request('post', f"/samples/{parent_id}/children/{child_id}")

        return new_samp

    def update(self, unique_id: str, sample_name: Optional[str] = None,
               description: Optional[str] = None, creation_date: Optional[str] = None,
               owner_orcid: Optional[str] = None, owner_id: Optional[int] = None,
               project_id: Optional[str] = None, sample_type: Optional[str] = None,
               parents: List[Dict] = [], children: List[Dict] = []) -> Dict:
        """Update an existing sample.

        Args:
            unique_id (str): Sample unique identifier (required)
            sample_name (str, optional): Human-readable sample name
            sample_type (str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            creation_date (str, optional): Sample creation date
            owner_orcid (str, optional): Owner's ORCID
            owner_id (int, optional): Owner's user ID
            project_id (str, optional): Project ID (Name)
            parents (List[Dict], optional): Parent samples to link
            children (List[Dict], optional): Child samples to link

        Returns:
            Dict: Updated sample object
        """
        sample_info = {
            "unique_id": unique_id,
            "sample_name": sample_name,
            "owner_orcid": owner_orcid,
            "owner_user_id": owner_id,
            "sample_type": sample_type,
            "description": description,
            "project_id": project_id,
            "date_created": creation_date
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

    def add_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Link a sample to a dataset.

        Args:
            dataset_id (str): Dataset ID
            sample_id (str): Sample ID

        Returns:
            Dict: Information about the created link
        """
        new_link = self._request('post', f"/datasets/{dataset_id}/samples/{sample_id}")
        return new_link

    def remove_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Remove a connection between a sample and a dataset.

        **Requires admin permissions.**
        Currently only available in staging API.

        Args:
            dataset_id (str): Dataset ID
            sample_id (str): Sample ID

        Returns:
            Dict: Deletion confirmation
        """
        del_link = self._request('delete', f"/datasets/{dataset_id}/samples/{sample_id}")
        return del_link

    def link(self, parent_id: str, child_id: str) -> Dict:
        """Link two samples with a parent-child relationship.

        Args:
            parent_id (str): Unique sample identifier of parent sample
            child_id (str): Unique sample identifier of child sample

        Returns:
            Dict: Created link object
        """
        return self._request('post', f"/samples/{parent_id}/children/{child_id}")
