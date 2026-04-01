#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main client for Crucible API.

Provides organized access to API endpoints.
"""

import time
import requests
import json
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, List, Dict, Any, Union
from .models import Dataset, Project
from .constants import DEFAULT_LIMIT
from .utils.deprecation import _deprecated, _removed

logger = logging.getLogger(__name__)

#%%

class CrucibleClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Crucible API client.

        Args:
            api_url: Base URL for the Crucible API (loads from config if not provided)
            api_key: API key for authentication (loads from config if not provided)

        Raises:
            ValueError: If api_url or api_key not provided and not found in config
        """
        # Load from config if not provided
        from .config import config as _config
        self._config = _config
        if api_url is None:
            api_url = _config.api_url
        if api_key is None:
            api_key = _config.api_key

        if not api_url:
            raise ValueError("api_url is required. Provide it directly or run 'crucible config init'")
        if not api_key:
            raise ValueError("api_key is required. Provide it directly or run 'crucible config init'")

        self.api_url = api_url.rstrip('/')
        self.api_key = api_key

        # Session with automatic retry on transient server/network errors
        retry = Retry(
            total            = 3,
            backoff_factor   = 1,            # waits 1s, 2s, 4s between retries
            status_forcelist = {429, 502, 503, 504},
            allowed_methods  = False,        # retry all HTTP methods, including POST
            raise_on_status  = False,        # let raise_for_status() handle final failure
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Initialize resource operations
        from .resources import DatasetOperations, SampleOperations, ProjectOperations,\
        UserOperations, InstrumentOperations, DeletionOperations, GraphOperations

        self.datasets = DatasetOperations(self)
        self.samples = SampleOperations(self)
        self.projects = ProjectOperations(self)
        self.users = UserOperations(self)
        self.instruments = InstrumentOperations(self)
        self.deletions = DeletionOperations(self)
        self.graphs = GraphOperations(self)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            Parsed JSON response

        Raises:
            requests.exceptions.HTTPError: For HTTP errors (4xx, 5xx)
            requests.exceptions.ConnectionError: For connection failures
            requests.exceptions.Timeout: For timeout errors
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        logger.debug(f"{method.upper()} {url}")
        timeout = (self._config.connect_timeout, self._config.read_timeout)
        response = self._session.request(method, url, timeout=timeout, **kwargs)
        logger.debug(f"Status: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        if not response.ok:
            # Try to surface the server's error detail from the response body
            detail = None
            try:
                body = response.json()
                detail = body.get("detail") or body.get("message") or body.get("error")
            except (json.JSONDecodeError, ValueError, AttributeError):
                pass
            if detail:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} {response.reason}: {detail}",
                    response=response,
                )
            response.raise_for_status()
        try:
            if response.content:
                return response.json()
            else:
                return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response from {url}: {e}")
            return response
    
    def _wait_for_request_completion(self, dsid: str, reqid: str, request_type: str,
                                  sleep_interval: int = 5) -> Dict:
        """Wait for a request to complete by polling its status.

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID
            request_type (str): Type of request ('ingest' or 'scicat_update')
            sleep_interval (int): Seconds between status checks

        Returns:
            Dict: Final request status information
        """
        req_info = self._get_request_status(dsid, reqid, request_type)
        logger.info(f"Waiting for {request_type} request to complete...")

        while req_info['status'] in ['requested', 'started']:
            time.sleep(sleep_interval)
            req_info = self._get_request_status(dsid, reqid, request_type)
            logger.debug(f"Current status: {req_info['status']}")

        logger.info(f"Request completed with status: {req_info['status']}")
        return req_info
    
    def _get_request_status(self, dsid: str, reqid: str, request_type: str) -> Dict:
        """Get the status of any type of request.

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID
            request_type (str): Type of request ('ingest' or 'scicat_update')

        Returns:
            Dict: Request status information

        Raises:
            ValueError: If unsupported request_type is provided
        """
        if request_type == 'ingest':
            return self._request('get', f'/datasets/{dsid}/ingest/{reqid}')
        elif request_type == 'scicat_update':
            return self._request('get', f'/datasets/{dsid}/scicat_update/{reqid}')
        else:
            raise ValueError(f"Unsupported request_type: {request_type}")
    
    #%% GENERIC METHODS

    def health(self) -> Dict:
        """Check API and database health without requiring authentication.

        Returns:
            Dict: {"status": "ok"|"degraded", "db": "ok"|"error", "version": str|None}
                  Raises requests.exceptions.ConnectionError if the host is unreachable.
        """
        import requests as _requests
        url = f"{self.api_url}/health"
        timeout = (self._config.connect_timeout, self._config.read_timeout)
        resp = _requests.get(url, timeout=timeout)
        return resp.json()

    def whoami(self) -> Dict:
        """Return account info for the current API key.

        Returns:
            Dict: access_group_name (ORCID), access_group_ids, and user_info
                  with full user profile fields.
        """
        return self._request('get', '/account')

    def get_resource_type(self, resource_id: str) -> dict:
        """
        Determine the type of a resource.

        Args:
            resource_id (str): The unique identifier (mfid) of the resource

        Returns:
            str: resource_type
        """
        response = self._request('get', f"/idtype/{resource_id}")
        return response.get('resource_type') or response['object_type']

    def get(self, resource_id: str, resource_type: str = None,
            include_metadata: bool = False) -> Dict:
        """
        Get a resource by ID with automatic type detection.

        Automatically determines if the resource is a sample or dataset
        and returns the appropriate data.

        Args:
            resource_id (str): The unique identifier (mfid) of the resource
            resource_type (str, optional): Resource type ('sample' or 'dataset').
                                          If not provided, will be auto-detected.

        Returns:
            Dict: Resource data (sample or dataset)

        Raises:
            ValueError: If resource type is unknown or not supported

        Example:
            >>> resource = client.get('abc123')
            >>> print(resource['project_id'])

            >>> # Skip detection if you already know the type
            >>> resource = client.get('abc123', resource_type='sample')
        """
        if resource_type is None:
            resource_type = self.get_resource_type(resource_id)

        if resource_type == "sample":
            return self.samples.get(resource_id)
        elif resource_type == "dataset":
            return self.datasets.get(resource_id, include_metadata=include_metadata)
        else:
            raise ValueError(f"Unknown or unsupported resource type: {resource_type}")

    def link(self, parent_id: str, child_id: str) -> Dict:
        """
        Link two resources with automatic type detection.

        Automatically determines resource types and creates appropriate link:
        - Both datasets: Creates parent-child dataset relationship
        - Both samples: Creates parent-child sample relationship
        - Dataset + sample: Links sample to dataset

        Args:
            parent_id (str): Parent resource unique identifier
            child_id (str): Child resource unique identifier

        Returns:
            Dict: Information about the created link

        Raises:
            ValueError: If resource types cannot be determined or combination is invalid

        Example:
            >>> # Link two datasets
            >>> client.link('parent_dataset_id', 'child_dataset_id')

            >>> # Link two samples
            >>> client.link('parent_sample_id', 'child_sample_id')

            >>> # Link sample to dataset
            >>> client.link('dataset_id', 'sample_id')
        """
        parent_type = self.get_resource_type(parent_id)
        child_type = self.get_resource_type(child_id)

        # Both are datasets
        if parent_type == "dataset" and child_type == "dataset":
            logger.info(f"Linking datasets: {parent_id} (parent) -> {child_id} (child)")
            return self.datasets.link_parent_child(parent_id, child_id)

        # Both are samples
        elif parent_type == "sample" and child_type == "sample":
            logger.info(f"Linking samples: {parent_id} (parent) -> {child_id} (child)")
            return self.samples.link(parent_id, child_id)

        # Mixed: dataset and sample
        elif parent_type == "dataset" and child_type == "sample":
            logger.info(f"Linking sample {child_id} to dataset {parent_id}")
            return self.datasets.add_sample(parent_id, child_id)

        elif parent_type == "sample" and child_type == "dataset":
            logger.info(f"Linking sample {parent_id} to dataset {child_id}")
            return self.datasets.add_sample(child_id, parent_id)

        else:
            raise ValueError(
                f"Cannot link resources: parent is {parent_type}, child is {child_type}. "
                f"Valid combinations: dataset-dataset, sample-sample, or dataset-sample."
            )

    def unlink(self, id_a: str, id_b: str) -> Dict:
        """Unlink two resources with automatic type detection.

        Only dataset-sample unlinking is supported by the API.
        Parent-child relationships (dataset-dataset, sample-sample) cannot
        be removed via the API.

        Args:
            id_a (str): First resource unique identifier (dataset or sample)
            id_b (str): Second resource unique identifier (dataset or sample)

        Returns:
            Dict: Deletion confirmation

        Raises:
            ValueError: If the combination is not a dataset-sample pair, or if
                        the resource types cannot be determined.
        """
        type_a = self.get_resource_type(id_a)
        type_b = self.get_resource_type(id_b)

        if type_a == "dataset" and type_b == "sample":
            logger.info(f"Unlinking sample {id_b} from dataset {id_a}")
            return self.datasets.remove_sample(id_a, id_b)

        elif type_a == "sample" and type_b == "dataset":
            logger.info(f"Unlinking sample {id_a} from dataset {id_b}")
            return self.datasets.remove_sample(id_b, id_a)

        elif type_a == "dataset" and type_b == "dataset":
            logger.info(f"Unlinking child dataset {id_b} from parent dataset {id_a}")
            return self.datasets.remove_child(id_a, id_b)

        elif type_a == "sample" and type_b == "sample":
            logger.info(f"Unlinking child sample {id_b} from parent sample {id_a}")
            return self.samples.remove_child(id_a, id_b)

        else:
            raise ValueError(
                f"Cannot unlink resources: {id_a} is {type_a}, {id_b} is {type_b}."
            )
    
    def download(self, resource_id: str, output_dir: str = 'crucible-downloads',
                 no_files: bool = False, no_record: bool = False,
                 overwrite_existing: bool = True,
                 include: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None) -> List[str]:
        """Download a resource record and, for datasets, its files.

        Args:
            resource_id (str): Sample or dataset unique identifier
            output_dir (str): Directory to save files (default: 'crucible-downloads')
            no_files (bool): Skip file download, save record JSON only
            no_record (bool): Skip saving record.json
            overwrite_existing (bool): Overwrite existing files (default: True)
            include (list, optional): Glob patterns — only download matching files
            exclude (list, optional): Glob patterns — skip matching files

        Returns:
            List[str]: Paths of all downloaded files (record.json + data files)
        """
        import os

        resource_type = self.get_resource_type(resource_id)
        if resource_type == 'dataset':
            record = self.datasets.get(resource_id, include_metadata=True)
        elif resource_type == 'sample':
            record = self.samples.get(resource_id)
        else:
            raise ValueError(f"Cannot download resource of type: {resource_type}")

        try:
            os.makedirs(output_dir, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot create output directory '{output_dir}'.") from e

        downloaded = []

        if not no_record:
            record_dir = os.path.join(output_dir, resource_id)
            os.makedirs(record_dir, exist_ok=True)
            json_path = os.path.join(record_dir, 'record.json')
            with open(json_path, 'w') as f:
                json.dump(record, f, indent=2)
            logger.info(f"Saved record to {json_path}")
            downloaded.append(json_path)

        if resource_type == 'dataset' and not no_files:
            files = self.datasets._fetch_files(resource_id, output_dir=output_dir,
                                               overwrite_existing=overwrite_existing,
                                               include=include, exclude=exclude)
            downloaded.extend(files)
            if files:
                logger.info(f"Downloaded {len(files)} file(s) to {output_dir}")

        return downloaded

    #%% PROJECT METHODS (DEPRECATED)

    @_deprecated("client.projects.create()")
    def create_project(self, project: Union[Project, Dict]) -> Dict:
        """Backward compatible: Use client.projects.create() instead."""
        return self.projects.create(project)

    @_deprecated("client.projects.get()")
    def get_project(self, project_id: str) -> Dict:
        """Backward compatible: Use client.projects.get() instead."""
        return self.projects.get(project_id)

    @_deprecated("client.projects.list()")
    def list_projects(self, orcid: str = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.projects.list() instead."""
        return self.projects.list(orcid=orcid, limit=limit)

    @_deprecated("client.projects.get_users()")
    def get_project_users(self, project_id: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.projects.get_users() instead."""
        return self.projects.get_users(project_id, limit=limit)

    @_deprecated("client.projects.add_user()")
    def add_user_to_project(self, orcid, project_id):
        """Backward compatible: Use client.projects.add_user() instead."""
        return self.projects.add_user(orcid, project_id)
    
    @_deprecated("client.projects.get_or_create()")
    def get_or_add_project(self, project_id, get_project_info_function = None, **kwargs):
        """Backward compatible: Use client.projects.get_or_create() instead."""
        if get_project_info_function is None:
            from .resources.projects import _build_project_from_args
            get_project_info_function = _build_project_from_args
        return self.projects.get_or_create(project_id, get_project_info_function=get_project_info_function, **kwargs)
    
    #%% SAMPLE METHODS (DEPRECATED)

    @_deprecated("client.samples.get()")
    def get_sample(self, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.get() instead."""
        return self.samples.get(sample_id)
    
    @_deprecated("client.samples.list_parents()")
    def list_parents_of_sample(self, sample_id, limit = DEFAULT_LIMIT, **kwargs)-> List[Dict]:
        """Backward compatible: Use client.samples.list_parents() instead."""
        return self.samples.list_parents(sample_id, limit=limit, **kwargs)
    
    @_deprecated("client.samples.list_children()")
    def list_children_of_sample(self, sample_id, limit = DEFAULT_LIMIT, **kwargs)-> List[Dict]:
        """Backward compatible: Use client.samples.list_children() instead."""
        return self.samples.list_children(sample_id, limit=limit, **kwargs)
    
    @_deprecated("client.samples.list()")
    def list_samples(self, dataset_id: str = None, parent_id: str = None, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.samples.list() instead."""
        return self.samples.list(dataset_id=dataset_id, parent_id=parent_id, limit=limit, **kwargs)
        
    @_deprecated("client.samples.update()")
    def update_sample(self, unique_id: str = None, sample_name: str = None, description: str = None,
                   creation_date: str = None, owner_orcid: str = None, owner_id: int = None,
                   project_id: str = None, sample_type: str = None,
                   parents: List[Dict] = [], children: List[Dict] = []):
        """Backward compatible: Use client.samples.update() instead."""
        return self.samples.update(unique_id=unique_id, sample_name=sample_name,
                                   description=description, creation_date=creation_date,
                                   owner_orcid=owner_orcid, owner_id=owner_id,
                                   project_id=project_id, sample_type=sample_type,
                                   parents=parents, children=children)

    @_deprecated("client.samples.create()")
    def add_sample(self, unique_id: str = None, sample_name: str = None, description: str = None,
                   creation_date: str = None, owner_orcid: str = None, owner_id: int = None,
                   project_id: str = None, sample_type: str = None,
                   parents: List[Dict] = [], children: List[Dict] = []) -> Dict:
        """Backward compatible: Use client.samples.create() instead."""
        return self.samples.create(unique_id=unique_id, sample_name=sample_name,
                                   description=description, creation_date=creation_date,
                                   owner_orcid=owner_orcid, owner_id=owner_id,
                                   project_id=project_id, sample_type=sample_type,
                                   parents=parents, children=children)
    
    @_deprecated("client.samples.remove_from_dataset()")
    def remove_sample_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.remove_from_dataset() instead."""
        return self.samples.remove_from_dataset(dataset_id, sample_id)
    

    @_deprecated("client.samples.add_to_dataset()")
    def add_sample_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.add_to_dataset() instead."""
        return self.samples.add_to_dataset(dataset_id, sample_id)
    
    # make them methods mirrored
    add_dataset_to_sample = add_sample_to_dataset
    remove_dataset_from_sample = remove_sample_from_dataset

    @_deprecated("client.samples.link()")
    def link_samples(self, parent_id: str, child_id: str):
        """Backward compatible: Use client.samples.link() instead."""
        return self.samples.link(parent_id, child_id)
    
    #%% DATASET METHODS (DEPRECATED)

    @_deprecated("client.datasets.get()")
    def get_dataset(self, dsid: str, include_metadata: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.get() instead."""
        return self.datasets.get(dsid, include_metadata=include_metadata)
    
    @_deprecated("client.datasets.create()")
    def create_new_dataset(self,
                            dataset: Dataset,
                            scientific_metadata: Optional[dict] = {},
                            keywords: List[str] = [],
                            get_user_info_function = None,
                            verbose: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.create() instead."""
        return self.datasets.create(dataset,
                                   scientific_metadata=scientific_metadata,
                                   keywords=keywords,
                                   get_user_info_function=get_user_info_function,
                                   verbose=verbose)

    @_deprecated("client.datasets.create()")
    def create_new_dataset_from_files(self,
                                     dataset: Dataset,
                                     files_to_upload: List[str],
                                     scientific_metadata: Optional[dict] = None,
                                     keywords: List[str] = [],
                                     get_user_info_function = None,
                                     ingestor: str = 'ApiUploadIngestor',
                                     verbose: bool = False,
                                     wait_for_ingestion_response: bool = True) -> Dict:
        """Backward compatible: Use client.datasets.create() with files_to_upload instead."""
        return self.datasets.create(dataset,
                                   scientific_metadata=scientific_metadata,
                                   keywords=keywords,
                                   get_user_info_function=get_user_info_function,
                                   verbose=verbose,
                                   files_to_upload=files_to_upload,
                                   ingestor=ingestor,
                                   wait_for_ingestion_response=wait_for_ingestion_response)
    
    @_deprecated("client.datasets.list_children()")
    def list_children_of_dataset(self, parent_dataset_id: str, limit = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list_children() instead."""
        return self.datasets.list_children(parent_dataset_id, limit=limit, **kwargs)


    @_deprecated("client.datasets.list_parents()")
    def list_parents_of_dataset(self, child_dataset_id: str, limit = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list_parents() instead."""
        return self.datasets.list_parents(child_dataset_id, limit=limit, **kwargs)
    
    @_deprecated("client.datasets.list()")
    def list_datasets(self, sample_id: Optional[str] = None, include_metadata: bool = False,
                     limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list() instead."""
        return self.datasets.list(sample_id=sample_id, include_metadata=include_metadata,
                                 limit=limit, **kwargs)

    @_deprecated("client.datasets.update()")
    def update_dataset(self, dsid: str, **updates) -> Dict:
        """Backward compatible: Use client.datasets.update() instead."""
        return self.datasets.update(dsid, **updates)


    @_deprecated("client.datasets.upload_file()")
    def upload_dataset_file(self, dsid: str, file_path: str, verbose=True) -> Dict:
        """Backward compatible: Use client.datasets.upload_file() instead."""
        return self.datasets.upload_file(dsid, file_path, verbose=verbose)


    @_deprecated("client.datasets.get_download_links()")
    def get_dataset_download_links(self, dsid: str):
        """Backward compatible: Use client.datasets.get_download_links() instead."""
        return self.datasets.get_download_links(dsid)

    @_deprecated("client.datasets.download()")
    def download_dataset(self, dsid: str, file_name: Optional[str] = None,
                        output_dir: Optional[str] = 'crucible-downloads',
                        overwrite_existing: bool = True) -> List[str]:
        """Backward compatible: Use client.datasets.download() instead."""
        return self.datasets.download(dsid, file_name=file_name,
                                     output_dir=output_dir,
                                     overwrite_existing=overwrite_existing)
        
    @_deprecated("client.datasets.request_ingestion()")
    def request_ingestion(self, dsid: str, file_to_upload: Optional[str] = None,
                         ingestion_class: Optional[str] = None,
                         wait_for_response: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.request_ingestion() instead."""
        return self.datasets.request_ingestion(dsid, file_to_upload=file_to_upload,
                                              ingestion_class=ingestion_class,
                                              wait_for_response=wait_for_response)

    @_removed("SciCat upload functionality has been removed from the Crucible API.")
    def request_scicat_upload(self, dsid: str, wait_for_response: bool = False, overwrite_data: bool = False) -> Dict:
        pass

    @_deprecated("client.datasets.get_access_groups()")
    def get_dataset_access_groups(self, dsid: str) -> List[str]:
        """Backward compatible: Use client.datasets.get_access_groups() instead."""
        return self.datasets.get_access_groups(dsid)

    @_deprecated("client.datasets.get_scientific_metadata()")
    def get_scientific_metadata(self, dsid: str) -> Dict:
        """Backward compatible: Use client.datasets.get_scientific_metadata() instead."""
        return self.datasets.get_scientific_metadata(dsid)

    @_deprecated("client.datasets.update_scientific_metadata()")
    def update_scientific_metadata(self, dsid: str, metadata: Dict, overwrite = False) -> Dict:
        """Backward compatible: Use client.datasets.update_scientific_metadata() instead."""
        return self.datasets.update_scientific_metadata(dsid, metadata, overwrite=overwrite)

    @_deprecated("client.datasets.get_thumbnails()")
    def get_thumbnails(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_thumbnails() instead."""
        return self.datasets.get_thumbnails(dsid, limit=limit)

    @_deprecated("client.datasets.add_thumbnail()")
    def add_thumbnail(self, dsid: str, file_path: str, thumbnail_name: str = None) -> Dict:
        """Backward compatible: Use client.datasets.add_thumbnail() instead."""
        return self.datasets.add_thumbnail(dsid, file_path, thumbnail_name=thumbnail_name)
    
    @_deprecated("client.datasets.get_associated_files()")
    def get_associated_files(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_associated_files() instead."""
        return self.datasets.get_associated_files(dsid, limit=limit)

    @_deprecated("client.datasets.add_associated_file()")
    def add_associated_file(self, dsid: str, file_path: str, filename: str = None) -> Dict:
        """Backward compatible: Use client.datasets.add_associated_file() instead."""
        return self.datasets.add_associated_file(dsid, file_path, filename=filename)
    
    @_deprecated("client.datasets.get_keywords()")
    def get_keywords(self, dsid: str = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_keywords() instead."""
        return self.datasets.get_keywords(dsid=dsid, limit=limit)

    @_deprecated("client.datasets.add_keyword()")
    def add_dataset_keyword(self, dsid: str, keyword: str) -> Dict:
        """Backward compatible: Use client.datasets.add_keyword() instead."""
        return self.datasets.add_keyword(dsid, keyword)

    @_deprecated("client.datasets.delete()")
    def delete_dataset(self, dsid: str) -> Dict:
        """Backward compatible: Use client.datasets.delete() instead."""
        return self.datasets.delete(dsid)

    @_removed("Google Drive location functionality has been removed from the Crucible API.")
    def get_google_drive_location(self, dsid: str) -> List[Dict]:
        pass

    @_removed("Google Drive location functionality has been removed from the Crucible API.")
    def add_google_drive_location(self, dsid: str, drive_info: Dict) -> None:
        pass

    @_deprecated("client.datasets.update_ingestion_status()")
    def update_ingestion_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Backward compatible: Use client.datasets.update_ingestion_status() instead."""
        return self.datasets.update_ingestion_status(dsid, reqid, status, timezone=timezone)

    @_removed("SciCat upload status functionality has been removed from the Crucible API.")
    def update_scicat_upload_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        pass

    @_removed("Transfer status functionality has been removed from the Crucible API.")
    def update_transfer_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        pass
    
    @_deprecated("client.datasets.link_parent_child()")
    def link_datasets(self, parent_dataset_id: str, child_dataset_id: str) -> Dict:
        """Backward compatible: Use client.datasets.link_parent_child() instead."""
        return self.datasets.link_parent_child(parent_dataset_id, child_dataset_id)
    
    @_deprecated("client.datasets.request_carrier_segmentation()")
    def request_carrier_segmentation(self, dataset_id):
        """Backward compatible: Use client.datasets.request_carrier_segmentation() instead."""
        return self.datasets.request_carrier_segmentation(dataset_id)
    
    #%% INSTRUMENT METHODS (DEPRECATED)

    @_deprecated("client.instruments.list()")
    def list_instruments(self, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.instruments.list() instead."""
        return self.instruments.list(limit=limit)


    @_deprecated("client.instruments.get()")
    def get_instrument(self, instrument_name: str = None, instrument_id: str = None) -> Dict:
        """Backward compatible: Use client.instruments.get() instead."""
        return self.instruments.get(instrument_name=instrument_name, instrument_id=instrument_id)


    @_deprecated("client.instruments.get_or_create()")
    def get_or_add_instrument(self, instrument_name: str, location: str = None, instrument_owner: str = None) -> Dict:
        """Backward compatible: Use client.instruments.get_or_create() instead."""
        return self.instruments.get_or_create(instrument_name, location=location, instrument_owner=instrument_owner)
    
    #%% USER METHODS (DEPRECATED)

    @_deprecated("client.users.get()")
    def get_user(self, orcid: str = None, email: str = None) -> Dict:
        """Backward compatible: Use client.users.get() instead."""
        return self.users.get(orcid=orcid, email=email)

    @_deprecated("client.users.create()")
    def add_user(self, user_info: Dict) -> Dict:
        """Backward compatible: Use client.users.create() instead."""
        return self.users.create(user_info)

    @_deprecated("client.users.get_or_create()")
    def get_or_add_user(self, orcid, get_user_info_function, **kwargs):
        """Backward compatible: Use client.users.get_or_create() instead."""
        return self.users.get_or_create(orcid, get_user_info_function, **kwargs)