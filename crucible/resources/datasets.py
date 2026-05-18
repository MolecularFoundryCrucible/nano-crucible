#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset resource operations for Crucible API.

Provides organized access to dataset-related API endpoints.
"""

import logging
from typing import Optional, List, Dict

# internal modules
from .files import FileOperations
from ..constants import DEFAULT_LIMIT
from ..utils.deprecation import _deprecated

# set up logging
logger = logging.getLogger(__name__)


class DatasetOperations(FileOperations):
    """Dataset-related API operations.

    Access via: client.datasets.get(), client.datasets.list(), etc.
    File operations (upload, download, thumbnails, ingestion) are inherited
    from FileOperations and also available via client.files.*.
    """

    @staticmethod
    def _parse(raw: Dict) -> Dict:
        """Validate a raw API response dict through the Dataset Pydantic model.

        Normalises field aliases (e.g. creation_date → timestamp) and preserves
        any extra fields returned by the server (keywords, scientific_metadata, …).
        """
        from ..models import Dataset
        return Dataset.model_validate(raw).model_dump()

    def get(self, dsid: str, include_metadata: bool = False,
            include_links: bool = False) -> Dict:
        """Get dataset details, optionally including scientific metadata and links.

        Args:
            dsid (str): Dataset unique identifier
            include_metadata (bool): Whether to include scientific metadata
            include_links (bool): Whether to include immediate parent/child/associated links

        Returns:
            Dict: Dataset object with optional metadata and links
        """
        params = {}
        if include_links:
            params['include_links'] = True

        if include_metadata:
            params['include_metadata'] = True

        raw = self._request('get', f'/datasets/{dsid}', params=params or None)
        if raw is None:
            return None

        return self._parse(raw)


    def list(self, sample_id: Optional[str] = None, include_metadata: bool = False,
             include_links: bool = False, limit: int = DEFAULT_LIMIT,
             offset: int = 0, **kwargs) -> List[Dict]:
        """List datasets with optional filtering and automatic pagination.

        Args:
            sample_id (str, optional): If provided, returns datasets for this sample
            limit (int): Maximum total results to return (default: 100). Requests
                         above API_PAGE_MAX (1000) are handled transparently via
                         parallel pagination.
            offset (int): Starting position in the full result set (default: 0)
            include_metadata (bool): Include scientific metadata in results
            include_links (bool): Include linked resources (parents, children, associated) per dataset
            **kwargs: Query parameters for filtering. Supported fields include:
                        keyword, unique_id, public, dataset_name, file_to_upload, owner_orcid,
                        project_id, instrument_name, source_folder, timestamp,
                        size, data_format, data_type, measurement, session_name, sha256_hash_file_to_upload

            Note:   Filters expect exact matches (case sensitive) except for keywords.
                    Keywords are case insensitive and match substrings.

        Returns:
            List[Dict]: Dataset objects matching filter criteria
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if include_metadata:
            params['include_metadata'] = True
        if include_links:
            params['include_links'] = True
        if sample_id:
            if limit:
                params['limit'] = limit
            raw = self._request('get', f'/samples/{sample_id}/datasets', params=params)
        else:
            raw = self._paginate('/datasets', params, limit, offset)
        return [self._parse(d) for d in raw]

    def count(self, **kwargs) -> int:
        """Return the total number of datasets matching the given filters without fetching items."""
        params = {k: v for k, v in kwargs.items() if v is not None}
        result = self._request('get', '/datasets', params={**params, 'limit': 1, 'offset': 0})
        return result['total']


    def create(self, dataset, scientific_metadata: Optional[Dict] = None,
               keywords: Optional[List[str]] = None,
               files_to_upload: Optional[List[str]] = None,
               ingestor: Optional[str] = None,
               verbose: bool = False,
               wait_for_ingestion_response: bool = False) -> Dict:
        """Create a new dataset record with scientific metadata and keywords.

        Args:
            dataset: Dataset object with dataset details
            scientific_metadata (dict, optional): Scientific metadata
            keywords (list, optional): Keywords to associate with dataset
        Returns:
            Dict: created_record, scientific_metadata_record, dsid
        """
        if scientific_metadata is None:
            scientific_metadata = {}

        if keywords is None:
            keywords = []
        if files_to_upload is None:
            files_to_upload = []

        dataset_details = dataset.model_dump()

        logger.debug('Creating new dataset record...')

        clean_dataset = {k: v for k, v in dataset_details.items() if v is not None}
        new_ds_record = self._request('post', '/datasets', json=clean_dataset)
        dsid = new_ds_record['unique_id']

        # add scientific metadata
        scimd = None
        if scientific_metadata:
            logger.debug(f'Adding scientific metadata record for {dsid}')
            scimd = self.add_scientific_metadata(dsid, scientific_metadata)

            
        # add keywords
        if keywords:
            logger.debug(f'Adding keywords to dataset {dsid}: {keywords}')
            for kw in keywords:
                self.add_keyword(dsid, kw)

        for file in files_to_upload:
            logger.debug(f'Adding {file} to dataset {dsid}')
            self.add_file_to_dataset(dsid, file, ingestion_class=ingestor, wait_for_ingestion_response=wait_for_ingestion_response)

        result = {"created_record": new_ds_record, "scientific_metadata_record": scimd, "dsid": dsid}
        return result

    def update(self, dsid: str, **updates) -> Dict:
        """Update an existing dataset with new field values.

        Args:
            dsid (str): Dataset unique identifier
            **updates: Fields to update (e.g., dataset_name="New Name", public=True)

        Returns:
            Dict: Updated dataset object

        Example:
            >>> client.datasets.update("my-dataset-id", dataset_name="Updated Name", public=True)
        """
        return self._request('patch', f'/datasets/{dsid}', json=updates)

    def delete(self, dsid: str) -> Dict:
        """Delete a dataset.

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Deletion confirmation
        """
        return self._request('delete', f'/datasets/{dsid}')

    def get_access_groups(self, dsid: str) -> List[str]:
        """Get list of access groups for a dataset.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            List[str]: Access group names
        """
        groups = self._request('get', f'/datasets/{dsid}/access_groups')
        return [group['group_name'] for group in groups]

    def add_access_group(self, dsid: str, group_name: str,
                         read: bool = True, write: bool = False) -> Dict:
        """Add an access group to a dataset.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset unique identifier
            group_name (str): Name of the access group to add
            read (bool): Grant read access (default: True)
            write (bool): Grant write access (default: False)

        Returns:
            Dict: Created ACL entry
        """
        params = {"group_name": group_name, "read": read, "write": write}
        return self._request('post', f'/datasets/{dsid}/access_groups', params=params)

    @_deprecated("create() with files_to_upload parameter")
    def create_from_files(self, dataset, files_to_upload: List[str],
                         scientific_metadata: Optional[Dict] = None,
                         keywords: Optional[List[str]] = None,
                         get_user_info_function=None,
                         ingestor: str = 'ApiUploadIngestor',
                         verbose: bool = False,
                         wait_for_ingestion_response: bool = True) -> Dict:
        """Build a new dataset with file upload and ingestion.

        .. deprecated::
            Use :meth:`create` with files_to_upload parameter instead.

        Args:
            dataset: Dataset object with dataset details
            files_to_upload (List[str]): List of file paths to upload
            scientific_metadata (dict, optional): Scientific metadata
            keywords (list, optional): Keywords to associate with dataset
            get_user_info_function (callable, optional): Function to get user info
            ingestor (str): Ingestion class to use (default: 'ApiUploadIngestor')
            verbose (bool): Enable verbose output
            wait_for_ingestion_response (bool): Wait for ingestion to complete

        Returns:
            Dict: created_record, scientific_metadata_record, ingestion_request, uploaded_files
        """
        return self.create(dataset=dataset,
                          scientific_metadata=scientific_metadata,
                          keywords=keywords,
                          verbose=verbose,
                          files_to_upload=files_to_upload,
                          ingestor=ingestor,
                          wait_for_ingestion_response=wait_for_ingestion_response)

    # Keyword Methods
    def get_keywords(self, dsid: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List keywords, optionally filtered by dataset.

        Args:
            dsid (str, optional): Dataset unique identifier to filter keywords
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: Keyword objects with keyword text and num_datasets counts
        """
        if dsid is None:
            return self._request('get', '/keywords')
        else:
            return self._request('get', f'/datasets/{dsid}/keywords')

    def add_keyword(self, dsid: str, keyword: str) -> Dict:
        """Add a keyword to a dataset.

        Args:
            dsid (str): Dataset unique identifier
            keyword (str): Keyword/tag to associate with dataset

        Returns:
            Dict: Keyword object with updated usage count
        """
        return self._request('post', f'/datasets/{dsid}/keywords', params={'keyword': keyword})


    # Dataset Linking Methods
    def add_sample(self, dataset_id: str, sample_id: str) -> Dict:
        """Link a sample to a dataset.

        Args:
            dataset_id (str): Dataset unique identifier
            sample_id (str): Sample unique identifier

        Returns:
            Dict: Information about the created link
        """
        return self._request('post', f"/datasets/{dataset_id}/samples/{sample_id}")

    def remove_sample(self, dataset_id: str, sample_id: str) -> Dict:
        """Remove the link between a dataset and a sample.

        **Requires admin permissions.**

        Args:
            dataset_id (str): Dataset unique identifier
            sample_id (str): Sample unique identifier

        Returns:
            Dict: Deletion confirmation
        """
        return self._request('delete', f"/datasets/{dataset_id}/samples/{sample_id}")

    def remove_child(self, parent_dataset_id: str, child_dataset_id: str) -> Dict:
        """Remove the parent-child link between two datasets.

        Args:
            parent_dataset_id (str): The unique ID of the parent dataset
            child_dataset_id (str): The unique ID of the child dataset

        Returns:
            Dict: Deletion confirmation
        """
        return self._request('delete', f"/datasets/{parent_dataset_id}/children/{child_dataset_id}")

    def link_parent_child(self, parent_dataset_id: str, child_dataset_id: str) -> Dict:
        """Link a derived dataset to a parent dataset.

        Args:
            parent_dataset_id (str): The unique ID for the parent dataset
            child_dataset_id (str): The unique ID for the derived dataset

        Returns:
            Dict: Information about the created link
        """
        new_link = self._request('post', f"/datasets/{parent_dataset_id}/children/{child_dataset_id}")
        return new_link

    def list_children(self, parent_dataset_id: str, limit: int = DEFAULT_LIMIT,
                      offset: int = 0, **kwargs) -> List[Dict]:
        """List the children of a given dataset with optional filtering.

        Args:
            parent_dataset_id (str): The unique ID of the dataset for which you want to find the children
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Query parameters for filtering datasets

        Returns:
            List[Dict]: Children datasets
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self._paginate(f"/datasets/{parent_dataset_id}/children", params, limit, offset)

    def list_parents(self, child_dataset_id: str, limit: int = DEFAULT_LIMIT,
                     offset: int = 0, **kwargs) -> List[Dict]:
        """List the parents of a given dataset with optional filtering.

        Args:
            child_dataset_id (str): The unique ID of the dataset for which you want to find the parents
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)
            **kwargs: Query parameters for filtering datasets

        Returns:
            List[Dict]: Parent datasets
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self._paginate(f"/datasets/{child_dataset_id}/parents", params, limit, offset)

    # Special Processing Methods
    def request_carrier_segmentation(self, dsid: str) -> Dict:
        """Request carrier segmentation for a dataset.

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Carrier segmentation request information
        """
        result = self._request('post', f"/datasets/{dsid}/carrier_segmentation")
        return result

    def request_insitu_aggregation(self, dsid: str) -> Dict:
        """Request insitu spectroscopy data aggregation for a dataset.

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Data processing request information
        """
        result = self._request('post', f"/datasets/{dsid}/insitu_spec_aggregation")
        return result
    

    def graph(self, dataset_id: str, recursive: bool = False, as_networkx: bool = False):
        """Return the graph of entities connected to this dataset.

        Delegates to client.graphs.get(). See GraphOperations.get() for full docs.

        Args:
            dataset_id (str): Dataset unique identifier.
            recursive (bool): If True, traverse the full connected component.
            as_networkx (bool): Return a networkx DiGraph if True.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        return self._client.graphs.get(dataset_id, recursive=recursive, as_networkx=as_networkx)
