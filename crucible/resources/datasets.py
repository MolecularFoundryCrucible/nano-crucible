#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset resource operations for Crucible API.

Provides organized access to dataset-related API endpoints.
"""

import os
import re
import fnmatch
import logging
import subprocess
import requests
from typing import Optional, List, Dict

# internal modules
from .base import BaseResource
from ..constants import DEFAULT_LIMIT
from ..utils import check_small_files
from ..utils.deprecation import _deprecated

# set up logging
logger = logging.getLogger(__name__)

#%%

class DatasetOperations(BaseResource):
    """Dataset-related API operations.

    Access via: client.datasets.get(), client.datasets.list(), etc.
    """

    @staticmethod
    def _parse(raw: Dict) -> Dict:
        """Validate a raw API response dict through the Dataset Pydantic model.

        Normalises field aliases (e.g. creation_date → timestamp) and preserves
        any extra fields returned by the server (keywords, scientific_metadata, …).
        """
        from ..models import Dataset
        return Dataset.model_validate(raw).model_dump()

    def get(self, dsid: str, include_metadata: bool = False) -> Dict:
        """Get dataset details, optionally including scientific metadata.

        Args:
            dsid (str): Dataset unique identifier
            include_metadata (bool): Whether to include scientific metadata

        Returns:
            Dict: Dataset object with optional metadata
        """
        raw = self._request('get', f'/datasets/{dsid}')
        if raw is None:
            return None
        dataset = self._parse(raw)
        if include_metadata:
            try:
                metadata = self._request('get', f'/datasets/{dsid}/scientific_metadata')
                dataset['scientific_metadata'] = metadata or {}
            except requests.exceptions.RequestException:
                dataset['scientific_metadata'] = {}
        return dataset

    def list(self, sample_id: Optional[str] = None, include_metadata: bool = False,
             limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List datasets with optional filtering.

        Args:
            sample_id (str, optional): If provided, returns datasets for this sample
            limit (int): Maximum number of results to return (default: 100)
            include_metadata (bool): Include scientific metadata in results
            **kwargs: Query parameters for filtering. Supported fields include:
                        keyword, unique_id, public, dataset_name, file_to_upload, owner_orcid,
                        project_id, instrument_name, source_folder, timestamp,
                        size, data_format, measurement, session_name, sha256_hash_file_to_upload

            Note:   Filters expect exact matches (case sensitive) except for keywords.
                    Keywords are case insensitive and match substrings.

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
        return [self._parse(d) for d in result] if result else []

    def create(self, dataset, scientific_metadata: Optional[Dict] = None,
               keywords: Optional[List[str]] = None,
               get_user_info_function=None, verbose: bool = False,
               files_to_upload: Optional[List[str]] = None,
               ingestor: str = 'ApiUploadIngestor',
               wait_for_ingestion_response: bool = True) -> Dict:
        """Create a new dataset with metadata and optionally upload files.

        Args:
            dataset: Dataset object with dataset details
            scientific_metadata (dict, optional): Scientific metadata
            keywords (list, optional): Keywords to associate with dataset
            get_user_info_function (callable, optional): Function to get user info
            verbose (bool): Enable verbose output
            files_to_upload (List[str], optional): List of file paths to upload
            ingestor (str): Ingestion class to use (default: 'ApiUploadIngestor')
            wait_for_ingestion_response (bool): Wait for ingestion to complete

        Returns:
            Dict: created_record, scientific_metadata_record, dsid, and optionally
                  uploaded_files and ingestion_request if files_to_upload provided
        """
        if scientific_metadata is None:
            scientific_metadata = {}
        if keywords is None:
            keywords = []

        dataset_details = dict(**dataset.model_dump())

        # Handle file upload path if files provided
        if files_to_upload:
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

            # auto-set timestamp from file modification time if not provided
            if dataset_details.get('timestamp') is None:
                import datetime
                mtime = os.path.getmtime(main_file)
                dataset_details['timestamp'] = datetime.datetime.fromtimestamp(
                    mtime, tz=datetime.timezone.utc).isoformat()

        # get owner_id if orcid provided
        owner_orcid = dataset_details.get('owner_orcid')
        logger.debug(f"owner_orcid={owner_orcid}")
        if owner_orcid:
            owner = self._client.users.get_or_create(owner_orcid, get_user_info_function)
            logger.debug(f"owner={owner}")
            dataset_details['owner_user_id'] = owner['id']

        # get or add project
        project_id = dataset_details.get('project_id')
        if project_id:
            project = self._client.projects.get(project_id)
            if not project:
                raise ValueError(f"Project with ID '{project_id}' does not exist in the database.")
            else:
                project_id = project['project_id']

        # get instrument_id if instrument_name provided
        instrument_name = dataset_details.get('instrument_name')
        if instrument_name:
            instrument = self._client.instruments.get(instrument_name=instrument_name)
            if instrument:
                dataset_details['instrument_id'] = instrument['id']
            else:
                raise ValueError(f'Provided instrument does not exist: {instrument_name}')

        logger.debug('Creating new dataset record...')

        clean_dataset = {k: v for k, v in dataset_details.items() if v is not None}
        logger.debug(f'POST request to /datasets with {clean_dataset}')
        new_ds_record = self._request('post', '/datasets', json=clean_dataset)
        logger.debug('Request complete')
        dsid = new_ds_record['unique_id']

        # add scientific metadata
        scimd = None
        if scientific_metadata is not None:
            logger.debug(f'Adding scientific metadata record for {dsid}')
            scimd = self._request('post', f'/datasets/{dsid}/scientific_metadata', json=scientific_metadata)
            logger.debug('Metadata addition complete')
            
        # add keywords
        if keywords:
            logger.debug(f'Adding keywords to dataset {dsid}: {keywords}')
            for kw in keywords:
                self.add_keyword(dsid, kw)

        logger.debug(f"dsid={dsid}")

        result = {"created_record": new_ds_record, "scientific_metadata_record": scimd, "dsid": dsid}

        # Handle file upload and ingestion if files provided
        if files_to_upload:
            uploaded_files = [self.upload_file(dsid, each_file, verbose) for each_file in files_to_upload]

            logger.debug(f"Submitting {dsid} to be ingested from file {main_file_cloud} using the class {ingestor}")

            ingest_req_info = self.request_ingestion(dsid, main_file_cloud, ingestor)

            logger.debug(f"Ingestion request {ingest_req_info['id']} is added to the queue")

            if wait_for_ingestion_response:
                ingest_req_info = self._client._wait_for_request_completion(dsid, ingest_req_info['id'], 'ingest')

            result["uploaded_files"] = uploaded_files
            result["ingestion_request"] = ingest_req_info

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

    def upload_file(self, dsid: str, file_path: str, verbose: bool = True) -> Dict:
        """Upload a file to a dataset.

        Args:
            dsid (str): Dataset unique identifier
            file_path (str): Local path to file to upload
            verbose (bool): Enable verbose output

        Returns:
            Dict: Upload response
        """
        from ..utils import checkhash, run_shell

        logger.debug(f"Uploading file {file_path}...")
        use_upload_endpoint = check_small_files([file_path])

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

            except (OSError, subprocess.SubprocessError, FileNotFoundError) as e:
                logger.error(f"File upload failed: {e}")
                raise RuntimeError("Files too large for transfer by http or rclone upload failed") from e

    def get_download_links(self, dsid: str) -> Dict:
        """Get the download links for files in a given dataset.

        URLs will be valid for 1 hour and can be shared with other people.
        While the URL is active, anyone with the URL will be able to access the file.

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Each item in the dictionary is a key, value pair
                  where the key is the filepath of a file in the dataset,
                  and the value is the corresponding signed url.
        """
        try:
            return self._request('get', f"/datasets/{dsid}/download_links")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (502, 503, 504):
                logger.warning(f"Could not retrieve download links for {dsid}: {e.response.status_code} {e.response.reason}. The server may be temporarily unavailable.")
                return {}
            raise

    def _fetch_files(self, dsid: str, output_dir: str,
                     overwrite_existing: bool = True,
                     include: Optional[List[str]] = None,
                     exclude: Optional[List[str]] = None) -> List[str]:
        """Download files for a dataset into output_dir. Returns list of downloaded paths."""
        import tempfile

        download_urls = self.get_download_links(dsid)

        files = download_urls
        if include:
            files = {k: v for k, v in files.items()
                     if any(fnmatch.fnmatch(k, p) for p in include)}
        if exclude:
            files = {k: v for k, v in files.items()
                     if not any(fnmatch.fnmatch(k, p) for p in exclude)}

        downloads = []
        for fname, signed_url in files.items():
            download_path = os.path.join(output_dir, fname)
            if overwrite_existing is False and os.path.exists(download_path):
                downloads.append(download_path)
                continue
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            response = self._client._session.get(signed_url, stream=True)
            response.raise_for_status()
            # Write to a temp file in the same directory, then atomically rename
            # to avoid leaving corrupt files if the download is interrupted.
            tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(download_path))
            try:
                with os.fdopen(tmp_fd, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                os.replace(tmp_path, download_path)
            except Exception:
                os.unlink(tmp_path)
                raise
            downloads.append(download_path)

        return downloads

    def download(self, dsid: str, file_name: Optional[str] = None,
                 output_dir: Optional[str] = 'crucible-downloads',
                 overwrite_existing: bool = True,
                 no_record: bool = False,
                 include: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None) -> List[str]:
        """Download dataset files.

        Args:
            dsid (str): Dataset unique identifier
            file_name (str, optional): Deprecated. Use include=['pattern'] with glob syntax.
            output_dir (str, optional): Directory to save files (default: 'crucible-downloads/')
            overwrite_existing (bool): Overwrite existing files (default: True)
            include (list, optional): Glob patterns — only download matching files
            exclude (list, optional): Glob patterns — skip matching files

        Returns:
            List[str]: List of downloaded file paths (including record.json)
        """
        if file_name is not None:
            import warnings
            warnings.warn(
                "The 'file_name' parameter is deprecated. Use include=['pattern'] with glob "
                "syntax instead (e.g. include=['*.h5']). Note: file_name used regex fullmatch; "
                "glob syntax differs.",
                DeprecationWarning, stacklevel=2,
            )
            # Apply regex filter now to produce an explicit filename list,
            # then pass as include so client.download() doesn't need to know about regex.
            download_urls = self.get_download_links(dsid)
            file_regex = fr"({file_name})"
            matched = [k for k in download_urls if re.fullmatch(file_regex, k)]
            include = matched  # exact names are valid glob literals

        return self._client.download(dsid, output_dir=output_dir, no_files=False,
                                     no_record=no_record,
                                     overwrite_existing=overwrite_existing,
                                     include=include, exclude=exclude)

    def request_ingestion(self, dsid: str, file_to_upload: Optional[str] = None,
                         ingestion_class: Optional[str] = None,
                         wait_for_response: bool = False) -> Dict:
        """Request dataset ingestion.

        Args:
            dsid (str): Dataset unique identifier
            file_to_upload (str, optional): Path to file for ingestion
            ingestion_class (str, optional): Ingestion class to use
            wait_for_response (bool): Wait for ingestion to complete

        Returns:
            Dict: Ingestion request with id and status
        """
        params = {"ingestion_class": ingestion_class, "file_to_upload": file_to_upload}
        logger.debug(f"Ingestion params: {params}")
        req_info = self._request('post', f'/datasets/{dsid}/ingest', params=params)
        if wait_for_response:
            req_info = self._client._wait_for_request_completion(dsid, req_info['id'], 'ingest')

        return req_info

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
                          get_user_info_function=get_user_info_function,
                          verbose=verbose,
                          files_to_upload=files_to_upload,
                          ingestor=ingestor,
                          wait_for_ingestion_response=wait_for_ingestion_response)

    # Scientific Metadata Methods
    def get_scientific_metadata(self, dsid: str) -> Dict:
        """Get scientific metadata for a dataset.

        Args:
            dsid (str): Dataset unique identifier

        Returns:
            Dict: Scientific metadata containing experimental parameters and settings
        """
        return self._request('get', f'/datasets/{dsid}/scientific_metadata')

    def update_scientific_metadata(self, dsid: str, metadata: Dict, overwrite: bool = False) -> Dict:
        """Create or replace scientific metadata for a dataset.

        Args:
            dsid (str): Dataset unique identifier
            metadata (Dict): Scientific metadata dictionary
            overwrite (bool): If True, replace all metadata; if False, merge with existing

        Returns:
            Dict: Updated metadata object
        """
        if overwrite:
            return self._request('post', f'/datasets/{dsid}/scientific_metadata', json=metadata)
        else:
            return self._request('patch', f'/datasets/{dsid}/scientific_metadata', json=metadata)

    def search_scientific_metadata(self, q: str, limit: Optional[int] = None) -> List[Dict]:
        """Perform a ranked full-text search on scientific metadata.

        Uses PostgreSQL full-text search on the server to find and rank
        datasets whose scientific metadata matches the query string.

        Args:
            q (str): Plain-text search query (e.g. "temperature", "XRD silicon").
            limit (int, optional): Maximum number of records to return.
                If omitted, default of 50 is used. Max is 200.

        Returns:
            List[Dict]: Matching scientific metadata records, ranked by relevance.

        Example:
            >>> results = client.datasets.search_scientific_metadata("thermal conductivity")
            >>> results = client.datasets.search_scientific_metadata("thermal conductivity", limit=25)
        """
        params = {"q": q}
        if limit is not None:
            params["limit"] = limit
        return self._request('get', '/scientific_metadata/search', params=params)

    # Thumbnail Methods
    def get_thumbnails(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get thumbnails for a dataset.

        Args:
            dsid (str): Dataset unique identifier
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: Thumbnail objects with base64-encoded images
        """
        return self._request('get', f'/datasets/{dsid}/thumbnails')

    def add_thumbnail(self, dsid: str, image, thumbnail_name: Optional[str] = None) -> Dict:
        """Add a thumbnail to a dataset.

        Args:
            dsid (str): Dataset unique identifier
            image: Image to use as thumbnail. Accepts:
                - str or Path: path to an image file
                - PIL.Image.Image: PIL image object
                - matplotlib.figure.Figure: matplotlib figure
                - numpy.ndarray: array of shape (H, W) or (H, W, C)
            thumbnail_name (str, optional): Display name. Defaults to the filename
                for file paths, or the dataset ID for in-memory objects.

        Returns:
            Dict: Created thumbnail object
        """
        import base64
        from ..utils import data2thumbnail

        png_path = data2thumbnail(image)

        if thumbnail_name is None:
            thumbnail_name = os.path.basename(png_path)

        with open(png_path, 'rb') as f:
            thumbnail_b64str = base64.b64encode(f.read()).decode('utf-8')

        thumbnail_data = {
            'thumbnail_name': thumbnail_name,
            'thumbnail_b64str': thumbnail_b64str,
        }
        return self._request('post', f'/datasets/{dsid}/thumbnails', json=thumbnail_data)

    # Associated Files Methods
    def get_associated_files(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get associated files for a dataset.

        Args:
            dsid (str): Dataset unique identifier
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: File metadata with names, sizes, and hashes
        """
        return self._request('get', f'/datasets/{dsid}/associated_files')

    def add_associated_file(self, dsid: str, file_path: str, filename: Optional[str] = None) -> Dict:
        """Add an associated file to a dataset.

        Args:
            dsid (str): Dataset unique identifier
            file_path (str): Path to file (for calculating metadata)
            filename (str, optional): Filename to store (uses basename if not provided)

        Returns:
            Dict: Created associated file object
        """
        from ..utils import checkhash

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

    # Request Status Methods
    def get_request_status(self, dsid: str, reqid: str, request_type: str) -> Dict:
        """Get the status of any type of request.

        Args:
            dsid (str): Dataset unique identifier
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

    def update_ingestion_status(self, dsid: str, reqid: str, status: str,
                               timezone: str = "America/Los_Angeles"):
        """Update the status of a dataset ingestion request.

        **Requires admin permissions.**

        Args:
            dsid (str): Dataset unique identifier
            reqid (str): Request ID for the ingestion
            status (str): New status ('complete', 'in_progress', 'failed')
            timezone (str): Timezone for completion time

        Returns:
            requests.Response: HTTP response from the update request
        """
        from ..utils import get_tz_isoformat

        if status == "complete":
            completion_time = get_tz_isoformat(timezone)
            patch_json = {"id": reqid,
                        "status": status,
                        "time_completed": completion_time}
        else:
            patch_json = {"id": reqid,
                        "status": status}

        return self._request('patch', f'/datasets/{dsid}/ingest/{reqid}', json=patch_json)

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

    def list_children(self, parent_dataset_id: str, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List the children of a given dataset with optional filtering.

        Args:
            parent_dataset_id (str): The unique ID of the dataset for which you want to find the children
            limit (int): Maximum number of results to return
            **kwargs: Query parameters for filtering datasets

        Returns:
            List[Dict]: Children datasets
        """
        params = {**kwargs}
        params['limit'] = limit
        result = self._request('get', f"/datasets/{parent_dataset_id}/children", params=params)
        return result

    def list_parents(self, child_dataset_id: str, limit: int = DEFAULT_LIMIT, **kwargs) -> List[Dict]:
        """List the parents of a given dataset with optional filtering.

        Args:
            child_dataset_id (str): The unique ID of the dataset for which you want to find the parents
            limit (int): Maximum number of results to return
            **kwargs: Query parameters for filtering datasets

        Returns:
            List[Dict]: Parent datasets
        """
        params = {**kwargs}
        params['limit'] = limit
        result = self._request('get', f"/datasets/{child_dataset_id}/parents", params=params)
        return result

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
