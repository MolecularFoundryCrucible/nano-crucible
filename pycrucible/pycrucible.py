import os
import re
import time
import requests
import json
import logging
from typing import Optional, List, Dict, Any
from .models import BaseDataset
from .utils import get_tz_isoformat, run_shell, checkhash
from .constants import AVAILABLE_INGESTORS

logger = logging.getLogger(__name__)

class CrucibleClient:
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize the Crucible API client.  
        This client provides access to the Molecular Foundry data lakehouse which contains
        experimental synthesis and characterization data as well as information about the users, 
        projects, and instruments involved in acquiring the data.  Any instrument settings or 
        parameters should be saved in the scientific_metadata record associated with each dataset. 
        
        Args:
            api_url: Base URL for the Crucible API
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
    

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an HTTP request to the API.
        
        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests
        
        Returns:
            Parsed JSON response
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        kwargs['headers'] = {**kwargs.get('headers', {}), **self.headers}
        response = requests.request(method, url, timeout = 10, **kwargs,)
        response.raise_for_status()
        try:
            if response.content:
                return response.json()
            else:
                return None
        except:
            return response
    
    def get_project(self, project_id: str) -> Dict:
        """Get details of a specific project.

        Args:
            project_id (str): Unique project identifier

        Returns:
            Dict: Complete project information
        """
        return self._request('get', f'/projects/{project_id}')

    def list_projects(self, orcid: str = None, limit: int = 100) -> List[Dict]:
        """List all accessible projects.

        Args:
            orcid (str): Option to filter projects by those associated with a certain user
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Project metadata including project_id, project_name, description, project_lead_email
        """
        if orcid is None:
            return self._request('get', '/projects')
        else:
            return self._request('get', f'/users/{orcid}/projects')

    
    def get_user(self, orcid: str = None, email: str = None) -> Dict:
        """Get user details by ORCID or email.

        **Requires admin permissions.**

        Args:
            orcid (str): ORCID identifier (format: 0000-0000-0000-000X)
            email (str): Users email address

            If both orcid and email are provided, only orcid will be used. 

        Returns:
            Dict: User profile with orcid, name, email, timestamps
        """
        if orcid:
            return self._request('get', f'/users/{orcid}')
        elif email:
            params = {"email": email}
            result = self._request('get', '/users', params=params)
            if not result:
                params = {"lbl_email": email}
                result = self._request('get', '/users', params=params)
            if len(result) > 0:
                return result[-1]
            else:
                return None
        else:
            raise ValueError('please provide orcid or email')
        
    
    def get_project_users(self, project_id: str, limit: int = 100) -> List[Dict]:
        """Get users associated with a project.

        **Requires admin permissions.**

        Args:
            project_id (str): Unique project identifier
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Project team members (excludes project lead)
        """
        result = self._request('get', f'/projects/{project_id}/users')
        return result
    
    def list_datasets(self, sample_id: Optional[str] = None, include_metadata: bool = False, limit: int = 100, **kwargs) -> List[Dict]:
        """List datasets with optional filtering.

        Args:
            sample_id (str, optional): If provided, returns datasets for this sample
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering. Fields that are currently supported to filter on include: 
                        keyword, unique_id, public, dataset_name, file_to_upload, owner_orcid,
                        project_id, instrument_name, source_folder, creation_time,
                        size, data_format, measurement, session_name, and sha256_hash_file_to_upload
                Other kwargs will be ignored during filtering. 

            Note:   Filters are applied such that datasets are filtered on the fields
                    corresponding to the provided argument names where their attributes
                    are equivalent to the value provided.  Values are case sensitive and
                    expect exact matches with the exception of keywords.
                    Keywords are case insensitive and will match substrings
                    (eg. keyword = 'TEM' will return datasets with any of the following keywords: TEM, tem, Stem, etc)

        Returns:
            List[Dict]: Dataset objects matching filter criteria
        """
        params = {**kwargs}
        params['limit'] = limit
        params['include_metadata'] = include_metadata
        if sample_id:
            result = self._request('get', f'/samples/{sample_id}/datasets', params=params)
        else:
            result = self._request('get', '/datasets', params=params)
        return result


    def update_dataset(self, dsid: str, **updates) -> Dict:
        """Update an existing dataset with new field values.

        Args:
            dsid (str): Dataset unique identifier
            **updates: Field names and values to update (e.g., dataset_name="New Name", public=True)

        Returns:
            Dict: Updated dataset object

        Example:
            client.update_dataset("my-dataset-id", dataset_name="Updated Name", public=True)
        """
        return self._request('patch', f'/datasets/{dsid}', json=updates)


    def upload_dataset_file(self, dsid: str, file_path: str, verbose=True) -> Dict:
        """Upload a file to a dataset.

        Args:
            dsid (str): Dataset unique identifier
            file_path (str): Local path to file to upload

        Returns:
            Dict: Upload response 
        """
        logger.debug(f"Uploading file {file_path}...")

        use_upload_endpoint = self.check_small_files([file_path])

        if use_upload_endpoint: 
            with open(file_path, 'rb') as f:
                fname = os.path.basename(file_path)
                files = [('files', (fname, f, 'application/octet-stream'))]
                added_af = self._request('post', f'/datasets/{dsid}/upload', files=files)
                return added_af
        else:
            try:
                # use rclone to copy to bucket (using list args for security)
                rclone_cmd = ['rclone', 'copy', file_path,
                             'mf-cloud-storage-upload:/crucible-uploads/api-uploads/']
                logger.debug(f"Uploading file {file_path}...")
                logger.debug(f"Running: {' '.join(rclone_cmd)}")
                xx = run_shell(rclone_cmd)
                logger.debug(f"stdout={xx.stdout}")
                logger.debug(f"stderr={xx.stderr}")
                logger.debug(f"Upload complete.")

                # call add associated file
                fname = os.path.basename(file_path)
                af = {"filename": os.path.join("api-uploads", fname), 
                     "size": os.path.getsize(file_path),
                     "sha256_hash": checkhash(file_path)}
                added_af = self._request('post', f"/datasets/{dsid}/associated_files", json=af)
                return added_af[-1]

            except:
                raise Exception("Files too large for transfer by http")


    def get_dataset_download_links(self, dsid: str):
        """Get the download links for file in a given dataset.
        URLs will be valid for 1 hour and can be shared with other people.
        While the URL is active, anyone with the URL will be able to access the file.

        Args:
            dsid (str): Dataset ID

        Returns:
            Dict: Each item in the dictionary is a key, value pair 
                  where the key is the filepath of a file in the dataset,
                  and the value is the corresponding signed url. 
        """

        result = self._request('get', f"/datasets/{dsid}/download_links")
        return result

    # TODO - maybe better to have specific functions like load_photo load_h5 load_json etc?
    # def load_dataset(self, dsid: str, file_name: str) -> None:
    #     '''
    #     Load a data file for a given dataset into memory. Similar to download dataset, but does not save to a file. 
        
    #     dsid str: Dataset Unique ID
    #     file_name: File to load into memory
    #     '''
    #     # generate the signed urls
    #     download_urls = self.get_dataset_download_links(dsid)
    #     if file_name is None:
    #         files = download_urls
    #     else:
    #         files = {k:v for k,v in download_urls.items() if file_name in k}

    #     downloads = []
    #     for _, signed_url in files.items():
    #         response = requests.get(signed_url)

    #     return response.content()


    def download_dataset(self, dsid: str, file_name: Optional[str] = None, output_dir: Optional[str] = 'crucible-downloads', overwrite_existing = True) -> None:
        """
        Download a dataset file.

        Args:
            dsid (str): Dataset Unique ID
            file_name (str, optional): File to download (If not provided, downloads all files)
            output_dir (str, optional): Directory to save files in (If not provided, files are saved to crucible-downloads/)
            overwrite_existing(bool): If the file already exists in the output directory, overwrite the File if set to True.
        """
    
        # make sure the output directory is a directory not a file
        try:
            os.makedirs(output_dir, exist_ok = True)
        except:
            raise Exception("Please specify a directory for the output_dir")
        
        # generate the signed urls
        download_urls = self.get_dataset_download_links(dsid)

        # subset the urls to the file specified or all files if not specified
        if file_name is None:
            files = download_urls
        else:
            file_regex = fr"({file_name})"
            files = {k:v for k,v in download_urls.items() if re.fullmatch(file_regex,k)}

        downloads = []
        for fname, signed_url in files.items():
            
            # set the local download location
            download_path = os.path.join(output_dir, fname)

            # check if the file exists and should be skipped
            if overwrite_existing is False and os.path.exists(download_path):
                continue

            # if there are subdirectories make them now
            os.makedirs(os.path.dirname(download_path), exist_ok=True)

            # get the content
            response = requests.get(signed_url, stream=True)

            # write to file
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            downloads.append(download_path)

        return(downloads)
        

        
    def request_ingestion(self, dsid: str, file_to_upload: str = None, ingestion_class: str = None, wait_for_response: bool = False,) -> Dict:
        """Request dataset ingestion.

        Args:
            dsid (str): Dataset ID
            file_to_upload (str, optional): Path to file for ingestion
            ingestor (str, optional): Ingestion class to use

        Returns:
            Dict: Ingestion request with id and status
        """
        params = {"ingestion_class": ingestion_class, "file_to_upload": file_to_upload}
        logger.debug(f"Ingestion params: {params}")
        req_info =  self._request('post', f'/datasets/{dsid}/ingest', params=params)
        if wait_for_response:
            req_info = self._wait_for_request_completion(dsid, req_info['id'], 'ingest')

        return req_info

    
    def request_scicat_upload(self, dsid: str, wait_for_response: bool = False, overwrite_data: bool = False) -> Dict:
        """Request SciCat update for a dataset.

        Args:
            dsid (str): Dataset ID
            wait_for_scicat_response (bool): Whether to wait for completion
            overwrite_data (bool): Whether to overwrite existing SciCat records

        Returns:
            Dict: SciCat update request information
        """
        params = {'overwrite_data': overwrite_data} if overwrite_data else None
        scicat_req_info = self._request('post', f'/datasets/{dsid}/scicat_update', params=params)

        if wait_for_response:
            req_info = self._wait_for_request_completion(dsid, scicat_req_info['id'], 'scicat_update')

        return req_info
    

    def get_request_status(self, dsid: str, reqid: str, request_type: str) -> Dict:
        """Get the status of any type of request.

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID
            request_type (str): Type of request ('ingest' or 'scicat_update')

        Returns:
            Dict: Request status information
        """
        if request_type == 'ingest':
            return self._request('get', f'/datasets/{dsid}/ingest/{reqid}')
        elif request_type == 'scicat_update':
            return self._request('get', f'/datasets/{dsid}/scicat_update/{reqid}')
        else:
            raise ValueError(f"Unsupported request_type: {request_type}")
    

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
        req_info = self.get_request_status(dsid, reqid, request_type)
        logger.info(f"Waiting for {request_type} request to complete...")

        while req_info['status'] in ['requested', 'started']:
            time.sleep(sleep_interval)
            req_info = self.get_request_status(dsid, reqid, request_type)
            logger.debug(f"Current status: {req_info['status']}")

        logger.info(f"Request completed with status: {req_info['status']}")
        return req_info
    

    def get_dataset_access_groups(self, dsid: str) -> List[str]:
        """Get access groups for a dataset.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset ID

        Returns:
            List[str]: List of access group names with dataset permissions
        """
        groups = self._request('get', f'/datasets/{dsid}/access_groups')
        return [group['group_name'] for group in groups]
        
    

    def get_scientific_metadata(self, dsid: str) -> Dict:
        """Get scientific metadata for a dataset.

        Args:
            dsid (str): Dataset ID

        Returns:
            Dict: Scientific metadata containing experimental parameters and settings
        """
        return self._request('get', f'/datasets/{dsid}/scientific_metadata')


    def update_scientific_metadata(self, dsid: str, metadata: Dict, overwrite = False) -> Dict:
        """Create or replace scientific metadata for a dataset.

        Args:
            dsid (str): Dataset ID
            metadata (Dict): Scientific metadata dictionary

        Returns:
            Dict: Updated metadata object
        """
        if overwrite == True:
            return self._request('post', f'/datasets/{dsid}/scientific_metadata', json=metadata)
        else: 
            return self._request('patch', f'/datasets/{dsid}/scientific_metadata', json=metadata)


    def get_thumbnails(self, dsid: str, limit: int = 100) -> List[Dict]:
        """Get thumbnails for a dataset.
        Args:
            dsid (str): Dataset ID
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Thumbnail objects with base64-encoded images
        """
        return self._request('get', f'/datasets/{dsid}/thumbnails')


    def add_thumbnail(self, dsid: str, file_path: str, thumbnail_name: str = None) -> Dict:
        """Add a thumbnail to a dataset.

        Args:
            dsid (str): Dataset ID
            file_path (str): Path to image file
            thumbnail_name (str, optional): Display name (uses filename if not provided)

        Returns:
            Dict: Created thumbnail object
        """
        import base64

        # Read file and encode to base64
        with open(file_path, 'rb') as f:
            file_content = f.read()
            thumbnail_b64str = base64.b64encode(file_content).decode('utf-8')

        # Use filename if no thumbnail_name provided
        if thumbnail_name is None:
            thumbnail_name = os.path.basename(file_path)

        thumbnail_data = {
            'thumbnail_name': thumbnail_name,
            'thumbnail_b64str': thumbnail_b64str
        }
        return self._request('post', f'/datasets/{dsid}/thumbnails', json=thumbnail_data)
    

    def get_associated_files(self, dsid: str, limit: int = 100) -> List[Dict]:
        """Get associated files for a dataset.

        Args:
            dsid (str): Dataset ID
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: File metadata with names, sizes, and hashes
        """
        return self._request('get', f'/datasets/{dsid}/associated_files')


    def add_associated_file(self, dsid: str, file_path: str, filename: str = None) -> Dict:
        """Add an associated file to a dataset.

        Args:
            dsid (str): Dataset ID
            file_path (str): Path to file (for calculating metadata)
            filename (str, optional): Filename to store (uses basename if not provided)

        Returns:
            Dict: Created associated file object
        """
        # Calculate file metadata
        file_size = os.path.getsize(file_path)
        file_hash = checkhash(file_path)

        # Use basename if no filename provided
        if filename is None:
            filename = os.path.basename(file_path)

        associated_file_data = {
            'filename': filename,
            'size': file_size,
            'sha256_hash': file_hash
        }
        return self._request('post', f'/datasets/{dsid}/associated_files', json=associated_file_data)
    

    def get_keywords(self, dsid: str = None, limit: int = 100) -> List[Dict]:
        """List keywords, option to filter on keywords associated with a given dataset.

        Args:
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Keyword objects with keyword text and num_datasets counts
        """
        if dsid is None:
            return self._request('get', '/keywords')
        else:
            return self._request('get', f'/datasets/{dsid}/keywords')


    def add_dataset_keyword(self, dsid: str, keyword: str) -> Dict:
        """Add a keyword to a dataset.

        Args:
            dsid (str): Dataset ID
            keyword (str): Keyword/tag to associate with dataset

        Returns:
            Dict: Keyword object with updated usage count
        """
        return self._request('post', f'/datasets/{dsid}/keywords', params={'keyword': keyword})


    def delete_dataset(self, dsid: str) -> Dict:
        """Delete a dataset (not implemented in API).

        Args:
            dsid (str): Dataset ID

        Returns:
            Dict: Deletion response
        """
        return self._request('delete', f'/datasets/{dsid}')


    def get_google_drive_location(self, dsid: str) -> List[Dict]:
        """Get current Google Drive location information for a dataset.

        Args:
            dsid (str): Dataset ID

        Returns:
            Dict: Google Drive location information
        """
        return self._request('get', f'/datasets/{dsid}/drive_location')


    def add_google_drive_location(self, dsid: str, drive_info: Dict) -> None:
        """Add drive location information for a dataset (not implemented).

        Args:
            dsid (str): Dataset ID
            drive_info (Dict): Drive location information to add
        """
        #TODO define this
        pass


    def update_ingestion_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Update the status of a dataset ingestion request.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID for the ingestion
            status (str): New status ('complete', 'in_progress', 'failed')
            timezone (str): Timezone for completion time

        Returns:
            requests.Response: HTTP response from the update request
        """
        if status == "complete":
            completion_time = get_tz_isoformat(timezone)
            patch_json = {"id": reqid,
                        "status": status,
                        "time_completed": completion_time}
        else:
            patch_json = {"id": reqid,
                        "status": status}

        url = f"{self.api_url}/datasets/{dsid}/ingest/{reqid}"
        response = requests.request("patch", url, json=patch_json, headers=self.headers)
        return response


    def update_scicat_upload_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Update the status of a SciCat upload request.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID for the SciCat upload
            status (str): New status ('complete', 'in_progress', 'failed')
            timezone (str): Timezone for completion time

        Returns:
            requests.Response: HTTP response from the update request
        """
        if status == "complete":
            completion_time = get_tz_isoformat(timezone)
            patch_json = {"id": reqid,
                        "status": status,
                        "time_completed": completion_time}
        else:
            patch_json = {"id": reqid,
                        "status": status}

        url = f"{self.api_url}/datasets/{dsid}/scicat_update/{reqid}"
        response = requests.request("patch", url, json=patch_json, headers=self.headers)
        return response


    def update_transfer_status(self, dsid: str, reqid: str, status: str, timezone: str = "America/Los_Angeles"):
        """Update the status of a dataset transfer request.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset ID
            reqid (str): Request ID for the transfer
            status (str): New status ('complete', 'in_progress', 'failed')
            timezone (str): Timezone for completion time

        Returns:
            requests.Response: HTTP response from the update request
        """
        if status == "complete":
            completion_time = get_tz_isoformat(timezone)
            patch_json = {"id": reqid,
                        "status": status,
                        "time_completed": completion_time}
        else:
            patch_json = {"id": reqid,
                        "status": status}

        url = f"{self.api_url}/datasets/{dsid}/google_drive_transfer/{reqid}"
        response = requests.request("patch", url, json=patch_json, headers=self.headers)
        return response


    def list_instruments(self, limit: int = 100) -> List[Dict]:
        """List all available instruments.

        Args:
            limit (int): Maximum number of results to return (default: 100)

        Returns:
            List[Dict]: Instrument objects with specifications and metadata
        """
        result = self._request('get', '/instruments')
        return result


    def get_instrument(self, instrument_name: str = None, instrument_id: str = None) -> Dict:
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


    def get_or_add_instrument(self, instrument_name: str, location: str = None, instrument_owner: str = None) -> Dict:
        """Get an existing instrument or create a new one if it doesn't exist.

        Args:
            instrument_name (str): Name of the instrument
            creation_location (str, optional): Location where instrument was created
            instrument_owner (str, optional): Owner of the instrument

        Returns:
            Dict: Instrument information (existing or newly created)
        """
        found_inst = self.get_instrument(instrument_name)

        if found_inst:
            return found_inst
        elif any([location is None, instrument_owner is None]):
            raise ValueError('Instrument does not exist, please provide location and owner')
        else:
            new_instrum = {"instrument_name": instrument_name,
                        "location": location,
                        "owner": instrument_owner}
            logger.debug(f"Creating new instrument: {new_instrum}")
            instrument = self._request('post', '/instruments', json=new_instrum)
        return instrument


    def get_sample(self, sample_id: str) -> Dict:
        """Get sample information by ID.

        Args:
            sample_id (str): Sample unique identifier

        Returns:
            Dict: Sample information with associated datasets
        """
        response = self._request('get', f"/samples/{sample_id}")
        return response
    
    def get_dataset(self, dsid: str, include_metadata: bool = False) -> Dict:
        """Get dataset details, optionally including scientific metadata.

        Args:
            dsid (str): Dataset unique identifier
            include_metadata (bool): Whether to include scientific metadata

        Returns:
            Dict: Dataset object with optional metadata
        """
        dataset = self._request('get', f'/datasets/{dsid}')
        if dataset and include_metadata:
            try:
                metadata = self._request('get', f'/datasets/{dsid}/scientific_metadata')
                dataset['scientific_metadata'] = metadata or {}
            except requests.exceptions.RequestException:
                dataset['scientific_metadata'] = {}
        return dataset

    def get_resource_type(self, resource_id: str) -> dict:
        """
        Determine the type of a resource.

        Args:
            resource_id (str): The unique identifier (mfid) of the resource

        Returns:
            str: resource_type
        """
        # TODO IMPLEMENT THIS
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
            return self.get_sample(resource_id)
        elif resource_type == "dataset":
            return self.get_dataset(resource_id, include_metadata=include_metadata)
        else:
            raise ValueError(f"Unknown or unsupported resource type: {resource_type}")

    def list_parents_of_sample(self, sample_id, limit = 100, **kwargs)-> List[Dict]:
        params = {**kwargs}
        """List the parents of a given sample with optional filtering.

        Args:
            sample_id (str, optional): The unique ID of the sample for which you want to find the parents 
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Parent samples
        """
        result = self._request('get', f"/samples/{sample_id}/parents", params=params)
        return result
    

    def list_children_of_sample(self, sample_id, limit = 100, **kwargs)-> List[Dict]:
        params = {**kwargs}
        """List the children of a given sample with optional filtering.

        Args:
            sample_id (str, optional): The unique ID of the sample for which you want to find the children
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering samples

        Returns:
            List[Dict]: Children samples
        """
        result = self._request('get', f"/samples/{sample_id}/children", params=params)
        return result
    

    def list_samples(self, dataset_id: str = None, parent_id: str = None, limit: int = 100, **kwargs) -> List[Dict]:
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
            logger.warning('Using parent_id with list_samples is deprecated. Please use list_children_sample instead.')
            result = self._request('get', f"/samples/{parent_id}/children", params=params)
        else:
            result = self._request('get', f"/samples", params=params)
        return result
        
    def update_sample(self, unique_id: str = None, sample_name: str = None, description: str = None,
                   creation_date: str = None, owner_orcid: str = None, owner_id: int = None, project_id: str = None, sample_type: str = None,
                   parents: List[Dict] = [], children: List[Dict] = []):
        
        sample_info = {   "unique_id": unique_id,
                          "sample_name": sample_name,
                          "owner_orcid": owner_orcid,
                          "owner_user_id": owner_id,
                          "sample_type": sample_type,
                          "description": description,
                          "project_id": project_id,
                          "date_created": creation_date
                        }

        sample_info = {k:v for k,v in sample_info.items() if v is not None}
    
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


    def add_sample(self, unique_id: str = None, sample_name: str = None, description: str = None,
                   creation_date: str = None, owner_orcid: str = None, owner_id: int = None, project_id: str = None, sample_type: str = None,
                   parents: List[Dict] = [], children: List[Dict] = []) -> Dict:
        """Add a new sample with optional parent-child relationships.

        Args:
            unique_id (str, optional): Unique sample identifier
            sample_name (str, optional): Human-readable sample name
            sample_type(str, optional): Category of sample (for filtering)
            description (str, optional): Sample description
            creation_date (str, optional): Sample creation date
            owner_orcid (str, optional): Owner's ORCID
            owner_id (int, optional): Owner's user ID
            project_id (str, optional): Project ID (Name)
            parents (List[Dict], optional): Parent samples
            children (List[Dict], optional): Child samples

        Returns:
            Dict: Created sample object
        """
        sample_info = {   "unique_id": unique_id,
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
    
    def remove_sample_from_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        '''
        Remove a connection between a sample and a dataset
        Requires admin permissions.
        Currently only available in staging API
        '''
        del_link = self._request('delete', f"/datasets/{dataset_id}/samples/{sample_id}")
        return del_link
    

    def add_sample_to_dataset(self, dataset_id: str, sample_id: str) -> Dict:
        """Link a sample to a dataset.

        Args:
            dataset_id (str): Dataset ID
            sample_id (str): Sample ID

        Returns:
            Dict: Information about the created link
        """
        new_link = self._request('post', f"/datasets/{dataset_id}/samples/{sample_id}")
        return new_link

    add_dataset_to_sample = add_sample_to_dataset
    remove_dataset_from_sample = remove_sample_from_dataset
    
    def add_user(self, user_info: Dict) -> Dict:
        """Add a new user to the system.

        **Requires admin permissions.**

        Args:
            user_info (Dict): User information including 'projects' key

        Returns:
            Dict: Created user object
        """
        user_projects = user_info.pop("projects")

        new_user = self._request('post', "/users",
                                json={"user_info": user_info,
                                      "project_ids": user_projects})
        return new_user


    def add_user_to_project(self, orcid, project_id):
        updated_project_users = self._request('post', f'/projects/{project_id}/users/{orcid}')
        
        return updated_project_users
        
        
    def get_or_add_user(self, orcid, get_user_info_function, **kwargs):
        """Get an existing user or create a new one if they don't exist.

        **Requires admin permissions.**

        Args:
            orcid (str): ORCID of the user
            get_user_info_function (callable): Function to retrieve user info if not found
            **kwargs: Additional arguments to pass to get_user_info_function

        Returns:
            dict: User information (existing or newly created)

        Raises:
            ValueError: If user info cannot be found or created
        """
        user = self.get_user(orcid)
        if user:
            return user
        
        user_info = get_user_info_function(orcid, **kwargs)
        if user_info:
            user = self.add_user(user_info)
            return user
        else:
            raise ValueError(f"User info for {orcid} not found in database or using the get_user_info_func")
    

    def _build_project_from_args(project_id, organization, project_lead_email):
        return({"project_id": project_id,
                "organization": organization,
                "project_lead_email": project_lead_email})
    

    def check_small_files(self, filelist):
        for f in filelist:
            if os.path.getsize(f) < 1e8:
                continue
            else:
                return False
        return True


    def get_or_add_project(self, project_id, get_project_info_function = _build_project_from_args, **kwargs):
        """Get an existing project or create a new one if it doesn't exist.
        
        Args:
            project_id (str): ID of the Crucible project
            get_project_info_func (callable): Function to retrieve project info if not found
            **kwargs: Additional arguments to pass to get_project_info_func. 
            If relying on the default to build the project from arguments, 
            please provide the project_id, project_organization, and project_lead_email. 
            
        Returns:
            dict: Project information (existing or newly created)
            
        Raises:
            ValueError: If project info cannot be found or created
        """
        proj = self.get_project(project_id)
        if proj is not None:
            return proj

        project_info = get_project_info_function(project_id = project_id, **kwargs)
            
        if project_info:
            proj = self._request('post', "/projects", json=project_info)
            return proj
        else:
            raise ValueError(f"Project info for {project_id} not found in database or using the provided get_project_info_func")
        

    def create_new_dataset(self,
                            dataset: BaseDataset, 
                            scientific_metadata: Optional[dict] = {}, 
                            keywords: List[str] = [],
                            get_user_info_function = None,
                            verbose = False) -> Dict:
        
        """Shared helper method to create a dataset with metadata."""
        
        dataset_details = dict(**dataset.model_dump())
        
        # add creation time
        if dataset_details.get('creation_time') is None:
            dataset_details['creation_time'] = get_tz_isoformat()

        # get owner_id if orcid provided
        owner_orcid = dataset_details.get('owner_orcid')
        logger.debug(f"owner_orcid={owner_orcid}")
        if owner_orcid:
            owner = self.get_or_add_user(owner_orcid, get_user_info_function)
            logger.debug(f"owner={owner}")
            dataset_details['owner_user_id'] = owner['id']
        
        # get or add project
        project_id = dataset_details.get('project_id')
        if project_id:
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project with ID '{project_id}' does not exist in the database.")
            else:
                project_id = project['project_id']

        # get instrument_id if instrument_name provided
        instrument_name = dataset_details.get('instrument_name')
        if instrument_name:
            instrument = self.get_instrument(instrument_name)
            if instrument:
                dataset_details['instrument_id'] = instrument['id']
            else:
                raise ValueError(f'Provided instrument does not exist: {instrument_name}')

        logger.debug('Creating new dataset record...')

        clean_dataset = {k: v for k, v in dataset_details.items() if v is not None}
        logger.debug(f'POST request to /datasets with {clean_dataset}')
        new_ds_record = self._request('post', '/datasets', json = clean_dataset)
        logger.debug('Request complete')
        dsid = new_ds_record['unique_id']

        # add scientific metadata
        scimd = None
        if scientific_metadata is not None:
            logger.debug(f'Adding scientific metadata record for {dsid}')
            scimd = self._request('post', f'/datasets/{dsid}/scientific_metadata', json=scientific_metadata)
            logger.debug('Metadata addition complete')
            logger.debug(f'Adding keywords to dataset {dsid}: {keywords}')

        # add keywords
        for kw in keywords:
            self.add_dataset_keyword(dsid, kw)

        logger.debug(f"dsid={dsid}")
        return {"created_record": new_ds_record, "scientific_metadata_record": scimd, "dsid": dsid}

    
    def create_new_dataset_from_files(self, 
                                     dataset: BaseDataset, 
                                     files_to_upload: List[str], 
                                     scientific_metadata: Optional[dict] = None,
                                     keywords: List[str] = [], 
                                     get_user_info_function = None, 
                                     ingestor = 'ApiUploadIngestor',
                                     verbose = False,
                                     wait_for_ingestion_response = True
                                     ):
        
        """Build a new dataset with file upload and ingestion.
        Args:
            files_to_upload (List[str]): List of file paths to upload
            dataset (BaseDataset): basic details about the data being uploaded
            scientific_metadata (dict, optional): Additional scientific metadata (accepts nested fields)
            keywords (list, optional): List of keywords to associate with the dataset
            get_user_info_function (callable, optional): Function to get user info if needed. This function should accept an orcid (str) and return a dictionary with keys: 'first_name', 'last_name', 'orcid', 'email' (optional), 'lbl_email' (optional), 'projects' (optional list of project IDs).
            ingestor (str, optional): Ingestion class to use. defaults to api upload ingestor which will not perform any processing
                                      but ensure that the json file and mf-storage-prod objects are created.
            The current list of available ingestors is below:

            Available Ingestors:
                AFMIngestor,
                TitanXSessionIngestor,
                Team05SessionIngestor,
                SimpleTiledImageScopeFoundryH5Ingestor,
                BioGlowIngestor,
                QSpleemSVRampIngestor,
                QSpleemImageIngestor,
                QSpleemARRESEKIngestor,
                QSpleemARRESMMIngestor,
                CanonCaptureScopeFoundryH5Ingestor,
                SingleSpecScopeFoundryH5Ingestor,
                HyperspecScopeFoundryH5Ingestor,
                HyperspecSweepScopeFoundryH5Ingestor,
                ToupcamLiveScopeFoundryH5Ingestor,
                CLSyncRasterScanIngestor,
                CLHyperspecIngestor,
                SpinbotSpecLineIngestor,
                SpinbotCameraCaptureIngestor,
                SpinbotPhotoRunIngestor,
                InSituPlIngestor,
                CziIngestor,
                DigitalMicrographIngestor,
                SerIngestor,
                BcfIngestor,
                EmdIngestor,
                SpinbotSpecRunIngestor,
                ImageIngestor
            
        Returns:
            dict: Dictionary containing created_record, scientific_metadata_record, and ingestion_request
            
        Raises:
            ValueError: If project_id is provided but the project does not exist in the database
        """
        # figure out the file path
        dataset_details = dict(**dataset.model_dump())

        logger.debug(f'files_to_upload={files_to_upload}')
        main_file = dataset_details.get('file_to_upload')
        logger.debug(f'main_file from dataset_details: {main_file}')
        if not main_file:
            main_file = files_to_upload[0]
            logger.debug(f'main_file from files_to_upload: {main_file}')
        base_file_name = os.path.basename(main_file)
        logger.debug(f'base_file_name={base_file_name}')
        main_file_cloud = os.path.join(f'api-uploads/{base_file_name}')
        dataset_details['file_to_upload'] = main_file_cloud
        logger.debug(f'main_file_cloud={main_file_cloud}')
        # create the dataset record / user / scimd / instrument / project
        cleaned_dataset = BaseDataset(**dataset_details)
        result = self.create_new_dataset(cleaned_dataset, 
                                         scientific_metadata=scientific_metadata,
                                         keywords=keywords,
                                         get_user_info_function=get_user_info_function
                                        )
        
        new_ds_record = result["created_record"]
        scimd = result["scientific_metadata_record"]
        dsid = result["dsid"]
            
        # Upload the files and add to dataset -- returns list of associated file objs (filename, size, sha)
        uploaded_files = [self.upload_dataset_file(dsid, each_file, verbose) for each_file in files_to_upload]

        logger.debug(f"Submitting {dsid} to be ingested from file {main_file_cloud} using the class {ingestor}")

        ingest_req_info = self.request_ingestion(dsid, main_file_cloud, ingestor)

        logger.debug(f"Ingestion request {ingest_req_info['id']} is added to the queue")

        if wait_for_ingestion_response:
            ingest_req_info = self._wait_for_request_completion(dsid, ingest_req_info['id'], 'ingest')

        return {"created_record": new_ds_record,
                "scientific_metadata_record": scimd,
                "ingestion_request": ingest_req_info, 
                "uploaded_files": uploaded_files}

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
            return self.link_datasets(parent_id, child_id)

        # Both are samples
        elif parent_type == "sample" and child_type == "sample":
            logger.info(f"Linking samples: {parent_id} (parent) -> {child_id} (child)")
            return self.link_samples(parent_id, child_id)

        # Mixed: dataset and sample
        elif parent_type == "dataset" and child_type == "sample":
            logger.info(f"Linking sample {child_id} to dataset {parent_id}")
            return self.add_sample_to_dataset(parent_id, child_id)

        elif parent_type == "sample" and child_type == "dataset":
            logger.info(f"Linking sample {parent_id} to dataset {child_id}")
            return self.add_sample_to_dataset(child_id, parent_id)

        else:
            raise ValueError(
                f"Cannot link resources: parent is {parent_type}, child is {child_type}. "
                f"Valid combinations: dataset-dataset, sample-sample, or dataset-sample."
            )
    
    
    def link_datasets(self, parent_dataset_id: str, child_dataset_id: str) -> Dict:
        """Link a derived dataset to a parent dataset.

        Args:
            parent_dataset_id (str): The unique ID for the parent dataset. 
            child_dataset_id (str): The unique ID for the derived dataset. 

        Returns:
            Dict: Information about the created link
        """
        new_link = self._request('post', f"/datasets/{parent_dataset_id}/children/{child_dataset_id}")
        return new_link
    
    def link_samples(self, parent_id: str, child_id: str):
        """Link two samples with a parent-child relationship.

        Args:
            parent_id (str): Unique sample identifier of parent sample (unique_id)
            child_id (str): Unique sample identifier of child sample (unique_id)

        Returns:
            Dict: Created link object
        """
        return self._request('post', f"/samples/{parent_id}/children/{child_id}")
    
    def list_children_of_dataset(self, parent_dataset_id: str, limit = 100, **kwargs) -> List[Dict]:
        params = {**kwargs}
        """List the children of a given dataset with optional filtering.

        Args:
            parent_dataset_id (str, optional): The unique ID of the datasets for which you want to find the children
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering datasets

        Returns:
            List[Dict]: Children datasets
        """
        params = {**kwargs}
        result = self._request('get', f"/datasets/{parent_dataset_id}/children", params=params)
        return result


    def list_parents_of_dataset(self, child_dataset_id: str, limit = 100, **kwargs) -> List[Dict]:
        """List the parents of a given dataset with optional filtering.

        Args:
            child_dataset_id (str, optional): The unique ID of the dataset for which you want to find the children
            limit (int): Maximum number of results to return (default: 100)
            **kwargs: Query parameters for filtering datasets
        Returns:
            List[Dict]: Parent datasets
        """
        params = {**kwargs}
        result = self._request('get', f"/datasets/{child_dataset_id}/parents", params=params)
        return result
    

    def request_carrier_segmentation(self, dataset_id):
        '''
        :param dataset_id: Description
        '''
        result = self._request('post', f"/datasets/{dataset_id}/carrier_segmentation")
        return result