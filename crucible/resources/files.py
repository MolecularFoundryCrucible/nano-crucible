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

    # Upload Methods

    def add_file_to_dataset(self, dsid: str, file_path: str,
                            ingestion_class: Optional[str] = None,
                            wait_for_ingestion_response: bool = False) -> Dict:
        """Add an associated file to a dataset.

        Automatically routes to chunked GCS upload for files >= 100 MB.

        Args:
            dsid: Dataset unique identifier
            file_path: Local path to the file
            ingestion_class: Ingestion class (e.g. 'ApiUploadIngestor').
                If None, the server selects one based on file format.
            wait_for_ingestion_response: Block until ingestion completes.

        Returns:
            Dict: Associated file record and ingestion request.
        """
        return self.upload_large_file(dsid, file_path,
                                      ingestion_class=ingestion_class,
                                      wait_for_ingestion_response=wait_for_ingestion_response)

        # Legacy small-file path via direct POST (kept for reference)
        # file_size = os.path.getsize(file_path)
        # from ..utils import checkhash
        # file_hash = checkhash(file_path)
        # upload_path = self._upload_file(dsid, file_path)
        # if upload_path is None:
        #     raise RuntimeError(f"Failed to upload {file_path}.")
        # associated_file_data = {
        #     'filename': upload_path,
        #     'size': file_size,
        #     'sha256_hash': file_hash,
        # }
        # response = self._request('post', f'/datasets/{dsid}/associated_files',
        #                          json=associated_file_data,
        #                          params={'ingestion_class': ingestion_class})
        # if wait_for_ingestion_response:
        #     ingestion_request = response.get('ingestion_request')
        #     self._client._wait_for_request_completion(dsid, ingestion_request['id'], 'ingest')
        # return response

    def upload_large_file(self, dsid: str, file_path: str,
                          ingestion_class: Optional[str] = None,
                          wait_for_ingestion_response: bool = False) -> Dict:
        """Upload a file to a dataset using resumable GCS chunked upload.

        Suitable for files of any size. Automatically resumes interrupted uploads.

        Args:
            dsid: Dataset unique identifier
            file_path: Local path to the file
            ingestion_class: Ingestion class to use after upload.
            wait_for_ingestion_response: Block until ingestion completes.

        Returns:
            Dict: Associated file record and ingestion request.
        """
        import hashlib
        _256K = 256 * 1024
        _MAX_RETRIES = 3

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        logger.info(f"Uploading {filename} ({file_size / 1024**2:.1f} MB) to dataset {dsid}")

        # Compute sha256 without loading the whole file into RAM
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                h.update(block)
        sha256_hash = h.hexdigest()
        logger.debug(f"sha256={sha256_hash}")

        # Initiate resumable upload session
        init = self._request('post', f'/datasets/{dsid}/upload/initiate',
                             json={'filename': filename, 'size': file_size})
        upload_id  = init['upload_id']
        uri        = init['resumable_uri']
        raw_hint   = init.get('chunk_size_hint', 8 * 1024 * 1024)
        # GCS requires chunks to be multiples of 256 KiB (except the last)
        chunk_size = max((raw_hint // _256K) * _256K, _256K)

        logger.debug(f"Chunked upload initiated: upload_id={upload_id}, chunk_size={chunk_size}")

        # Upload chunks directly to GCS (no Crucible auth needed)
        with open(file_path, 'rb') as f:
            offset = 0
            while offset < file_size:
                f.seek(offset)
                chunk = f.read(chunk_size)
                chunk_end = offset + len(chunk) - 1

                for attempt in range(_MAX_RETRIES):
                    resp = requests.put(
                        uri,
                        data=chunk,
                        headers={
                            'Content-Range': f'bytes {offset}-{chunk_end}/{file_size}',
                            'Content-Length': str(len(chunk)),
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
                        if probe.status_code == 308 and 'Range' in probe.headers:
                            last_byte = int(probe.headers['Range'].split('-')[1])
                            offset = last_byte + 1
                        f.seek(offset)
                        chunk = f.read(chunk_size)
                        chunk_end = offset + len(chunk) - 1

        # Register the AssociatedFile record
        logger.info(f"Completing upload for {filename} (upload_id={upload_id})")
        file_record = self._request('post', f'/datasets/{dsid}/upload/complete',
                                    json={'upload_id': upload_id, 'sha256_hash': sha256_hash})

        # Trigger ingestion — use the stored filename from the response (full GCS path)
        stored_filename = file_record.get('filename', filename)
        ingest_params = {'filename': stored_filename, 'file_size': file_size}
        if ingestion_class:
            ingest_params['ingestion_class'] = ingestion_class
        logger.info(f"Requesting ingestion for {stored_filename}"
                    + (f" (class={ingestion_class})" if ingestion_class else ""))
        ingestion_request = self._request('post', f'/datasets/{dsid}/ingest',
                                          params=ingest_params)
        logger.debug(f"Ingestion request created: id={ingestion_request.get('id')}, "
                     f"status={ingestion_request.get('status')}")

        if wait_for_ingestion_response and ingestion_request:
            self._client._wait_for_request_completion(dsid, ingestion_request['id'], 'ingest')

        return {'associated_file': file_record, 'ingestion_request': ingestion_request}

    def _upload_file(self, dsid: str, file_path: str) -> Optional[str]:
        """Upload a small file via direct POST (legacy path, kept for backward compat).

        For new code prefer add_file_to_dataset() which auto-routes based on size.
        """
        logger.debug(f"Uploading file {file_path}...")
        with open(file_path, 'rb') as f:
            fname = os.path.basename(file_path)
            file_obj = [('files', (fname, f, 'application/octet-stream'))]
            result = self._request('post', f'/datasets/{dsid}/upload', files=file_obj)
        # Endpoint returns a list of uploaded paths; we upload one file at a time
        if isinstance(result, list):
            return result[0] if result else None
        return result

    # Download Methods

    def get_associated_files(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get associated files for a dataset.

        Args:
            dsid: Dataset unique identifier
            limit: Maximum number of results to return

        Returns:
            List[Dict]: File metadata with names, sizes, and hashes
        """
        return self._request('get', f'/datasets/{dsid}/associated_files')

    def get_download_links(self, dsid: str) -> Dict:
        """Get signed download URLs for all files in a dataset.

        URLs are valid for 1 hour and can be shared freely.

        Args:
            dsid: Dataset unique identifier

        Returns:
            Dict: Mapping of file path → signed URL. Empty dict if no files.
        """
        try:
            return self._request('get', f"/datasets/{dsid}/download_links")
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 404:
                    detail = e.response.json().get('detail', '')
                    if 'No files found' in detail:
                        logger.debug(f"No files in storage for dataset {dsid}")
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
            if not overwrite_existing and os.path.exists(download_path):
                downloads.append(download_path)
                continue
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            response = self._client._session.get(signed_url, stream=True)
            response.raise_for_status()
            # Write to a temp file then atomically rename to avoid corrupt files
            # if the download is interrupted.
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
            download_urls = self.get_download_links(dsid)
            matched = [k for k in download_urls if re.fullmatch(fr"({file_name})", k)]
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

    def get_ingestion_requests(self, dsid: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get ingestion requests for a dataset."""
        return self._request('get', f'/datasets/{dsid}/ingest')

    def get_request_status(self, dsid: str, reqid: str, request_type: str) -> Dict:
        """Get the status of an ingestion request.

        Args:
            dsid: Dataset unique identifier
            reqid: Request ID
            request_type: Type of request ('ingest')

        Returns:
            Dict: Request status information
        """
        if request_type == 'ingest':
            return self._request('get', f'/datasets/{dsid}/ingest/{reqid}')
        raise ValueError(f"Unsupported request_type: {request_type}")

    def update_ingestion_status(self, dsid: str, reqid: str, status: str,
                                ingestion_githash: str = None,
                                ingestion_class: str = None,
                                timezone: str = "America/Los_Angeles") -> Dict:
        """Update the status of an ingestion request.

        **Requires admin permissions.**

        Args:
            dsid: Dataset unique identifier
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

        return self._request('patch', f'/datasets/{dsid}/ingest/{reqid}', json=patch_json)
