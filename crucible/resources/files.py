#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File operations for Crucible datasets: upload, download, thumbnails, ingestion.

Accessible as client.files.* or via client.datasets.* (DatasetOperations inherits
this class so all methods are available on both namespaces).
"""

import os
import re
import fnmatch
import logging
import requests
from typing import Optional, List, Dict

from .base import BaseResource
from ..constants import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class FileOperations(BaseResource):
    """File operations scoped to a dataset: upload, download, thumbnails, ingestion.

    Access via client.files.* or client.datasets.* (DatasetOperations inherits this).
    All methods take a dataset unique ID (dsid) as their first argument.
    """

    #%% Upload Methods

    def add_file_to_dataset(self, dsid: str, file_path: str,
                            ingestion_class: Optional[str] = None,
                            wait_for_ingestion_response: bool = False) -> Dict:
        """Upload a file to a dataset and request ingestion.

        Args:
            dsid: Dataset unique identifier
            file_path: Local path to the file
            ingestion_class: Ingestion class for the worker (e.g. 'lammps', 'nexus').
                Defaults to the server-side default if omitted.
            wait_for_ingestion_response: Block until ingestion completes.

        Returns:
            Dict: {'associated_file': AssociatedFileRead, 'ingestion_request': IngestionRequest}
                AssociatedFileRead includes: mfid, filename, storage_path, size, sha256_hash, dataset_mfid
        """
        # get file information
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # run file upload
        file_record = self._upload_file_gcs(dsid, file_path)
        
        # Trigger ingestion — use the stored filename from the response (full GCS path)
        stored_filename = file_record.get('filename', filename)
        file_id = file_record.get('mfid')
        ingest_params = {'filename': stored_filename, 'file_size': file_size}
        if ingestion_class:
            ingest_params['ingestion_class'] = ingestion_class
            
        logger.info(f"Requesting ingestion for {stored_filename}"
                    + (f" (class={ingestion_class})" if ingestion_class else ""))
        
        ingestion_request = self._request('post', f'/datasets/{dsid}/files/{file_id}/ingest', params=ingest_params)
        
        logger.debug(f"Ingestion request created: id={ingestion_request.get('id')}, "
                     f"status={ingestion_request.get('status')}")

        if wait_for_ingestion_response and ingestion_request:
            self._client._wait_for_request_completion(ingestion_request['id'])
            
        return {'associated_file': file_record, 'ingestion_request': ingestion_request}


    def _upload_file_gcs(self, dsid: str, file_path: str) -> Dict:
        """Upload a file to a dataset using resumable GCS chunked upload.
        
        Automatically resumes interrupted uploads.

        Args:
            dsid: Dataset unique identifier
            file_path: Local path to the file

        Returns:
            Dict: AssociatedFile record for the uploaded file.
        """
        import hashlib
        import base64
        import struct
        import google_crc32c
        _256K      = 256 * 1024
        _MIN_CHUNK = 32 * 1024 * 1024  # 32 MiB floor - overrides server hint for throughput
        _MAX_RETRIES = 3

        file_size = os.path.getsize(file_path)
        filename  = os.path.basename(file_path)

        logger.info(f"Uploading {filename} ({file_size / 1024**2:.1f} MB) to dataset {dsid}")

        # Single pre-pass: SHA256 sent to /initiate for server-side dedup;
        # reused at /complete - CRC32C per chunk covers transport integrity.
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(_MIN_CHUNK), b''):
                h.update(block)
        sha256_hash = h.hexdigest()
        logger.debug(f"sha256={sha256_hash}")

        # Initiate resumable upload session; server returns existing_file if hash matches
        init = self._request('post', f'/datasets/{dsid}/upload/initiate',
                             json={'filename': filename, 'size': file_size, 'sha256_hash': sha256_hash})
        logger.info(f"[{filename}] upload_id={upload_id} uri={uri[-40:]}")
        if init.get('existing_file', None) is not None:
            logger.info(f"File {filename} already exists in dataset {dsid}, skipping upload")
            return init['existing_file']

        upload_id  = init['upload_id']
        uri        = init['resumable_uri']
        raw_hint   = init.get('chunk_size_hint', _MIN_CHUNK)
        # Use the larger of server hint and our minimum; align to GCS 256 KiB boundary
        chunk_size = max((max(raw_hint, _MIN_CHUNK) // _256K) * _256K, _256K)

        logger.debug(f"Chunked upload initiated: upload_id={upload_id}, chunk_size={chunk_size >> 20} MiB")

        # Upload chunks directly to GCS (no Crucible auth needed)
        with open(file_path, 'rb') as f:
            offset = 0
            while offset < file_size:
                f.seek(offset)
                chunk = f.read(chunk_size)
                chunk_end = offset + len(chunk) - 1

                for attempt in range(_MAX_RETRIES):
                    crc_b64 = base64.b64encode(struct.pack(">I", google_crc32c.value(chunk))).decode()
                    resp = requests.put(
                        uri,
                        data=chunk,
                        headers={
                            'Content-Range': f'bytes {offset}-{chunk_end}/{file_size}',
                            'Content-Length': str(len(chunk)),
                            'x-goog-hash': f'crc32c={crc_b64}',
                        },
                        timeout=120,
                    )
                    if resp.status_code in (200, 201):
                        logger.debug("Chunked upload complete")
                        offset = file_size
                        break
                    elif resp.status_code == 308:
                        offset = chunk_end + 1
                        logger.debug(f"Chunk accepted, offset={offset}/{file_size}")
                        break
                    else:
                        logger.debug(f"Unexpected GCS status {resp.status_code} "
                                     f"(attempt {attempt + 1}/{_MAX_RETRIES})")
                        if attempt == _MAX_RETRIES - 1:
                            raise RuntimeError(
                                f"GCS chunk upload failed after {_MAX_RETRIES} attempts "
                                f"(status {resp.status_code}): {resp.text}"
                            )
                        # Query GCS for confirmed offset and retry from there
                        probe = requests.put(uri,
                                             headers={'Content-Range': f'bytes */{file_size}'},
                                             timeout=30)
                        if probe.status_code in (200, 201):
                            offset = file_size
                            break
                        elif probe.status_code == 308 and 'Range' in probe.headers:
                            last_byte = int(probe.headers['Range'].split('-')[1])
                            offset = last_byte + 1
                        f.seek(offset)
                        chunk = f.read(chunk_size)
                        chunk_end = offset + len(chunk) - 1

        # Register the AssociatedFile record
        logger.info(f"Completing upload for {filename} (upload_id={upload_id})")
        file_record = self._request('post', f'/datasets/{dsid}/upload/complete',
                                    json={'upload_id': upload_id, 'sha256_hash': sha256_hash})

        return file_record


    def list_files(self, limit: int = DEFAULT_LIMIT,
                   sha256_hash: Optional[str] = None) -> List[Dict]:
        """List all files across all accessible datasets.

        Args:
            limit: Maximum number of results
            sha256_hash: Filter by SHA-256 hex digest

        Returns:
            List[Dict]: File records (mfid, filename, storage_path, size, sha256_hash, dataset_mfid)
        """
        params = {}
        if sha256_hash:
            params['sha256_hash'] = sha256_hash
        return self._paginate('/files', params, limit=limit)

    def get_associated_files(self, dsid: str) -> List[Dict]:
        """Get associated files for a dataset.

        Args:
            dsid: Dataset unique identifier

        Returns:
            List[Dict]: File records (mfid, filename, storage_path, size, sha256_hash, dataset_mfid).
                storage_path is null until the file has been ingested.
        """
        return self._request('get', f'/datasets/{dsid}/files')

    def get_file(self, file_id: str) -> Dict:
        """Get metadata for a single associated file.

        Args:
            file_id: File MFID

        Returns:
            Dict: File record (mfid, filename, storage_path, size, sha256_hash, dataset_mfid)
        """
        return self._request('get', f'/files/{file_id}')

    def get_download_link(self, file_id: str) -> str:
        """Get a signed download URL for a single file.

        Prefer this over get_download_links() when the user requests a specific
        file — avoids signing all files in the dataset.

        Args:
            file_id: File MFID

        Returns:
            str: Signed URL valid for 1 hour, no auth required.

        Raises:
            HTTPError 404: File has not been ingested yet.
        """
        result = self._request('get', f'/files/{file_id}/download_link')
        return result['url']

    #%% Download Methods

    def get_download_links(self, dsid: str) -> Dict:
        """Get signed download URLs for all ingested files in a dataset.

        URLs are valid for 1 hour, require no auth, and are safe to share.

        Args:
            dsid: Dataset unique identifier

        Returns:
            Dict: Mapping of file MFID → signed URL. Only includes ingested files.
                Empty dict if no ingested files found.
        """
        try:
            return self._request('get', f"/datasets/{dsid}/download_links")
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 404:
                    logger.debug(f"No ingested files in storage for dataset {dsid}")
                    return {}
                if e.response.status_code in (502, 503, 504):
                    logger.warning(f"Could not retrieve download links for {dsid}: "
                                   f"{e.response.status_code} {e.response.reason}. "
                                   "The server may be temporarily unavailable.")
                    return {}
            raise

    def _fetch_files(self, dsid: str, output_dir: str,
                     overwrite_existing: bool = True,
                     include: Optional[List[str]] = None,
                     exclude: Optional[List[str]] = None) -> List[str]:
        """Download files for a dataset into output_dir. Returns list of downloaded paths."""
        import tempfile

        all_files = self.get_associated_files(dsid)

        # Only ingested files have a storage_path and are downloadable
        prefix_sp = f'mf-storage-prod/{dsid}/'
        ingested = [f for f in all_files if f.get('storage_path')]

        def _bare_name(f: Dict) -> str:
            sp = f.get('storage_path', '')
            return sp[len(prefix_sp):] if sp.startswith(prefix_sp) else os.path.basename(sp)

        if include:
            ingested = [f for f in ingested if any(fnmatch.fnmatch(_bare_name(f), p) for p in include)]
        if exclude:
            ingested = [f for f in ingested if not any(fnmatch.fnmatch(_bare_name(f), p) for p in exclude)]

        if not ingested:
            return []

        # Bulk-fetch signed URLs; keys are MFIDs
        link_map = self.get_download_links(dsid)

        downloads = []
        for file_meta in ingested:
            name       = _bare_name(file_meta)
            signed_url = link_map.get(file_meta.get('mfid'))
            if not signed_url:
                logger.warning(f"No download URL for {name}, skipping")
                continue

            download_path = os.path.join(output_dir, name)
            if not overwrite_existing and os.path.exists(download_path):
                downloads.append(download_path)
                continue

            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            response = self._client._session.get(signed_url, stream=True)
            response.raise_for_status()
            # Write to a temp file then atomically rename to avoid corrupt partial files
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
            dsid: Dataset unique identifier
            file_name: Deprecated. Use include=['pattern'] with glob syntax.
            output_dir: Directory to save files (default: 'crucible-downloads/')
            overwrite_existing: Overwrite existing files (default: True)
            include: Glob patterns - only download matching files
            exclude: Glob patterns - skip matching files

        Returns:
            List[str]: Downloaded file paths (including record.json)
        """
        if file_name is not None:
            import warnings
            warnings.warn(
                "The 'file_name' parameter is deprecated. Use include=['pattern'] with glob "
                "syntax instead (e.g. include=['*.h5']). Note: file_name used regex fullmatch; "
                "glob syntax differs.",
                DeprecationWarning, stacklevel=2,
            )
            all_files = self.get_associated_files(dsid)
            matched = [os.path.basename(f.get('storage_path') or f.get('filename', ''))
                       for f in all_files
                       if re.fullmatch(fr"({file_name})",
                                       os.path.basename(f.get('storage_path') or f.get('filename', '')))]
            include = matched

        return self._client.download(dsid, output_dir=output_dir, no_files=False,
                                     no_record=no_record,
                                     overwrite_existing=overwrite_existing,
                                     include=include, exclude=exclude)

    # Thumbnail Methods
    def get_thumbnails(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get thumbnails for a dataset.

        Args:
            dsid: Dataset unique identifier
            limit: Maximum number of results to return

        Returns:
            List[Dict]: Thumbnail objects with base64-encoded images
        """
        return self._request('get', f'/datasets/{dsid}/thumbnails')

    def add_thumbnail(self, dsid: str, image, thumbnail_name: Optional[str] = None) -> Dict:
        """Add a thumbnail to a dataset.

        Args:
            dsid: Dataset unique identifier
            image: Image to use as thumbnail. Accepts:
                - str or Path: path to an image file or a base64-encoded string
                - PIL.Image.Image: PIL image object
                - matplotlib.figure.Figure: matplotlib figure
                - numpy.ndarray: array of shape (H, W) or (H, W, C)
            thumbnail_name: Display name. Defaults to the filename for file paths,
                or the dataset ID for in-memory objects.

        Returns:
            Dict: Created thumbnail object
        """
        import base64
        from ..utils import data2thumbnail, is_base64

        if is_base64(image):
            thumbnail_data = {
                'thumbnail_name': thumbnail_name or f"{dsid}_thumbnail",
                'thumbnail_b64str': image,
            }
            return self._request('post', f'/datasets/{dsid}/thumbnails', json=thumbnail_data)

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

    # Ingestion Methods

    def get_ingestion_requests(self, dsid: Optional[str] = None,
                               file_id: Optional[str] = None,
                               limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get ingestion requests, optionally filtered by dataset or file.

        Args:
            dsid: Filter by dataset ID
            file_id: Filter by file MFID
            limit: Maximum number of results
        """
        params = {}
        if dsid:
            params['dataset_id'] = dsid
        if file_id:
            params['file_id'] = file_id
        return self._request('get', '/ingestion_requests', params=params or None)

    def get_request_status(self, reqid: str) -> Dict:
        """Get the status of an ingestion request.
        Args:
            reqid: Request ID
        """
        return self._request('get', f'/ingestion_requests/{reqid}')


    def update_ingestion_status(self, reqid: str, status: str,
                                ingestion_githash: str = None,
                                ingestion_class: str = None,
                                timezone: str = "America/Los_Angeles") -> Dict:
        """Update the status of an ingestion request.

        **Requires admin permissions.**

        Args:
            reqid: Request ID
            status: New status ('complete', 'in_progress', 'failed')
            timezone: Timezone for completion timestamp

        Returns:
            Dict: Updated ingestion request
        """
        from ..utils import get_tz_isoformat

        patch_json = {'ingestion_githash': ingestion_githash,
                      'ingestion_class': ingestion_class}

        if status == "complete":
            patch_json.update({"id": reqid, "status": status,
                                "time_completed": get_tz_isoformat(timezone)})
        else:
            patch_json.update({"id": reqid, "status": status})

        return self._request('patch', f'/ingestion_requests/{reqid}', json=patch_json)
