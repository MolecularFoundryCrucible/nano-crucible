import os
import time
import requests
import json
import logging
from typing import Optional, List, Dict, Any
from .models import BaseDataset
from .constants import AVAILABLE_INGESTORS, DEFAULT_TIMEOUT, DEFAULT_LIMIT

logger = logging.getLogger(__name__)

class CrucibleClient:
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize the Crucible API client.

        Args:
            api_url: Base URL for the Crucible API
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

        # Initialize resource operations
        from .resources import DatasetOperations, SampleOperations, ProjectOperations, UserOperations, InstrumentOperations
        self.datasets = DatasetOperations(self)
        self.samples = SampleOperations(self)
        self.projects = ProjectOperations(self)
        self.users = UserOperations(self)
        self.instruments = InstrumentOperations(self)
    
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
        kwargs['headers'] = {**kwargs.get('headers', {}), **self.headers}
        response = requests.request(method, url, timeout=DEFAULT_TIMEOUT, **kwargs)
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
    
    def get_resource_type(self, resource_id: str) -> dict:
        """
        Determine the type of a resource.

        Args:
            resource_id (str): The unique identifier (mfid) of the resource

        Returns:
            str: resource_type
        """
        response = self._request('get', f"/idtype/{resource_id}")
        return response['object_type']

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

    def check_small_files(self, filelist):
        for f in filelist:
            if os.path.getsize(f) < 1e8:
                continue
            else:
                return False
        return True

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
            return self.samples.add_to_dataset(parent_id, child_id)

        elif parent_type == "sample" and child_type == "dataset":
            logger.info(f"Linking sample {parent_id} to dataset {child_id}")
            return self.samples.add_to_dataset(child_id, parent_id)

        else:
            raise ValueError(
                f"Cannot link resources: parent is {parent_type}, child is {child_type}. "
                f"Valid combinations: dataset-dataset, sample-sample, or dataset-sample."
            )
    
    #%% PROJECT METHODS (DEPRECATED)
    
    def get_project(self, project_id: str) -> Dict:
        """Backward compatible: Use client.projects.get() instead."""
        return self.projects.get(project_id)

    def list_projects(self, orcid: str = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.projects.list() instead."""
        return self.projects.list(orcid=orcid, limit=limit)

    def get_project_users(self, project_id: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.projects.get_users() instead."""
        return self.projects.get_users(project_id, limit=limit)

    def add_user_to_project(self, orcid, project_id):
        """Backward compatible: Use client.projects.add_user() instead."""
        return self.projects.add_user(orcid, project_id)
    
    def get_or_add_project(self, project_id, get_project_info_function = None, **kwargs):
        """Backward compatible: Use client.projects.get_or_create() instead."""
        if get_project_info_function is None:
            from .resources.projects import _build_project_from_args
            get_project_info_function = _build_project_from_args
        return self.projects.get_or_create(project_id, get_project_info_function=get_project_info_function, **kwargs)
    
    #%% SAMPLE METHODS (DEPRECATED)
    
    def get_sample(self, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.get() instead."""
        return self.samples.get(sample_id)
    
    def list_parents_of_sample(self, sample_id, limit = DEFAULT_LIMIT, **kwargs)-> List[Dict]:
        """Backward compatible: Use client.samples.list_parents() instead."""
        return self.samples.list_parents(sample_id, limit=limit, **kwargs)
    
    def list_children_of_sample(self, sample_id, limit = DEFAULT_LIMIT, **kwargs)-> List[Dict]:
        """Backward compatible: Use client.samples.list_children() instead."""
        return self.samples.list_children(sample_id, limit=limit, **kwargs)
    
    def list_samples(self, dataset_id: str = None, parent_id: str = None, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.samples.list() instead."""
        return self.samples.list(dataset_id=dataset_id, parent_id=parent_id, limit=limit, **kwargs)
        
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
    
    def remove_sample_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.remove_from_dataset() instead."""
        return self.samples.remove_from_dataset(dataset_id, sample_id)
    

    def add_sample_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Backward compatible: Use client.samples.add_to_dataset() instead."""
        return self.samples.add_to_dataset(dataset_id, sample_id)
    
    # make them methods mirrored
    add_dataset_to_sample = add_sample_to_dataset
    remove_dataset_from_sample = remove_sample_from_dataset

    def link_samples(self, parent_id: str, child_id: str):
        """Backward compatible: Use client.samples.link() instead."""
        return self.samples.link(parent_id, child_id)
    
    #%% DATASET METHODS (DEPRECATED)

    def get_dataset(self, dsid: str, include_metadata: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.get() instead."""
        return self.datasets.get(dsid, include_metadata=include_metadata)
    
    def create_new_dataset(self,
                            dataset: BaseDataset,
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

    def create_new_dataset_from_files(self,
                                     dataset: BaseDataset,
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
    
    def list_children_of_dataset(self, parent_dataset_id: str, limit = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list_children() instead."""
        return self.datasets.list_children(parent_dataset_id, limit=limit, **kwargs)


    def list_parents_of_dataset(self, child_dataset_id: str, limit = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list_parents() instead."""
        return self.datasets.list_parents(child_dataset_id, limit=limit, **kwargs)
    
    def list_datasets(self, sample_id: Optional[str] = None, include_metadata: bool = False,
                     limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """Backward compatible: Use client.datasets.list() instead."""
        return self.datasets.list(sample_id=sample_id, include_metadata=include_metadata,
                                 limit=limit, **kwargs)

    def update_dataset(self, dsid: str, **updates) -> Dict:
        """Backward compatible: Use client.datasets.update() instead."""
        return self.datasets.update(dsid, **updates)


    def upload_dataset_file(self, dsid: str, file_path: str, verbose=True) -> Dict:
        """Backward compatible: Use client.datasets.upload_file() instead."""
        return self.datasets.upload_file(dsid, file_path, verbose=verbose)


    def get_dataset_download_links(self, dsid: str):
        """Backward compatible: Use client.datasets.get_download_links() instead."""
        return self.datasets.get_download_links(dsid)

    def download_dataset(self, dsid: str, file_name: Optional[str] = None,
                        output_dir: Optional[str] = 'crucible-downloads',
                        overwrite_existing: bool = True) -> List[str]:
        """Backward compatible: Use client.datasets.download() instead."""
        return self.datasets.download(dsid, file_name=file_name,
                                     output_dir=output_dir,
                                     overwrite_existing=overwrite_existing)
        
    def request_ingestion(self, dsid: str, file_to_upload: Optional[str] = None,
                         ingestion_class: Optional[str] = None,
                         wait_for_response: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.request_ingestion() instead."""
        return self.datasets.request_ingestion(dsid, file_to_upload=file_to_upload,
                                              ingestion_class=ingestion_class,
                                              wait_for_response=wait_for_response)

    def request_scicat_upload(self, dsid: str, wait_for_response: bool = False, overwrite_data: bool = False) -> Dict:
        """Backward compatible: Use client.datasets.request_scicat_upload() instead."""
        return self.datasets.request_scicat_upload(dsid, wait_for_response=wait_for_response, overwrite_data=overwrite_data)

    def get_dataset_access_groups(self, dsid: str) -> List[str]:
        """Backward compatible: Use client.datasets.get_access_groups() instead."""
        return self.datasets.get_access_groups(dsid)

    def get_scientific_metadata(self, dsid: str) -> Dict:
        """Backward compatible: Use client.datasets.get_scientific_metadata() instead."""
        return self.datasets.get_scientific_metadata(dsid)

    def update_scientific_metadata(self, dsid: str, metadata: Dict, overwrite = False) -> Dict:
        """Backward compatible: Use client.datasets.update_scientific_metadata() instead."""
        return self.datasets.update_scientific_metadata(dsid, metadata, overwrite=overwrite)

    def get_thumbnails(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_thumbnails() instead."""
        return self.datasets.get_thumbnails(dsid, limit=limit)

    def add_thumbnail(self, dsid: str, file_path: str, thumbnail_name: str = None) -> Dict:
        """Backward compatible: Use client.datasets.add_thumbnail() instead."""
        return self.datasets.add_thumbnail(dsid, file_path, thumbnail_name=thumbnail_name)
    
    def get_associated_files(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_associated_files() instead."""
        return self.datasets.get_associated_files(dsid, limit=limit)

    def add_associated_file(self, dsid: str, file_path: str, filename: str = None) -> Dict:
        """Backward compatible: Use client.datasets.add_associated_file() instead."""
        return self.datasets.add_associated_file(dsid, file_path, filename=filename)
    
    def get_keywords(self, dsid: str = None, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_keywords() instead."""
        return self.datasets.get_keywords(dsid=dsid, limit=limit)

    def add_dataset_keyword(self, dsid: str, keyword: str) -> Dict:
        """Backward compatible: Use client.datasets.add_keyword() instead."""
        return self.datasets.add_keyword(dsid, keyword)

    def delete_dataset(self, dsid: str) -> Dict:
        """Backward compatible: Use client.datasets.delete() instead."""
        return self.datasets.delete(dsid)

    def get_google_drive_location(self, dsid: str) -> List[Dict]:
        """Backward compatible: Use client.datasets.get_google_drive_location() instead."""
        return self.datasets.get_google_drive_location(dsid)

    def add_google_drive_location(self, dsid: str, drive_info: Dict) -> None:
        """Backward compatible: Use client.datasets.add_google_drive_location() instead."""
        return self.datasets.add_google_drive_location(dsid, drive_info)

    def update_ingestion_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Backward compatible: Use client.datasets.update_ingestion_status() instead."""
        return self.datasets.update_ingestion_status(dsid, reqid, status, timezone=timezone)

    def update_scicat_upload_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Backward compatible: Use client.datasets.update_scicat_upload_status() instead."""
        return self.datasets.update_scicat_upload_status(dsid, reqid, status, timezone=timezone)

    def update_transfer_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Backward compatible: Use client.datasets.update_transfer_status() instead."""
        return self.datasets.update_transfer_status(dsid, reqid, status, timezone=timezone)
    
    def link_datasets(self, parent_dataset_id: str, child_dataset_id: str) -> Dict:
        """Backward compatible: Use client.datasets.link_parent_child() instead."""
        return self.datasets.link_parent_child(parent_dataset_id, child_dataset_id)
    
    def request_carrier_segmentation(self, dataset_id):
        """Backward compatible: Use client.datasets.request_carrier_segmentation() instead."""
        return self.datasets.request_carrier_segmentation(dataset_id)
    
    #%% INSTRUMENT METHODS (DEPRECATED)
    
    def list_instruments(self, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Backward compatible: Use client.instruments.list() instead."""
        return self.instruments.list(limit=limit)


    def get_instrument(self, instrument_name: str = None, instrument_id: str = None) -> Dict:
        """Backward compatible: Use client.instruments.get() instead."""
        return self.instruments.get(instrument_name=instrument_name, instrument_id=instrument_id)


    def get_or_add_instrument(self, instrument_name: str, location: str = None, instrument_owner: str = None) -> Dict:
        """Backward compatible: Use client.instruments.get_or_create() instead."""
        return self.instruments.get_or_create(instrument_name, location=location, instrument_owner=instrument_owner)
    
    #%% USER METHODS (DEPRECATED)

    def get_user(self, orcid: str = None, email: str = None) -> Dict:
        """Backward compatible: Use client.users.get() instead."""
        return self.users.get(orcid=orcid, email=email)

    def add_user(self, user_info: Dict) -> Dict:
        """Backward compatible: Use client.users.create() instead."""
        return self.users.create(user_info)

    def get_or_add_user(self, orcid, get_user_info_function, **kwargs):
        """Backward compatible: Use client.users.get_or_create() instead."""
        return self.users.get_or_create(orcid, get_user_info_function, **kwargs)