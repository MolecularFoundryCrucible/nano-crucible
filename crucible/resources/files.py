#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File resource operations — scoped to a single file MFID (/files/* endpoints).

For dataset-scoped file operations (upload, download, thumbnails, ingestion)
see DatasetOperations (client.datasets.*).
"""

import logging
from typing import Optional, List, Dict

from .base import BaseResource
from ..constants import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class FileOperations(BaseResource):
    """Operations on individual files by MFID.

    Access via: client.files.get(), client.files.list(), etc.
    """

    @staticmethod
    def _parse(raw: Optional[Dict]) -> Optional[Dict]:
        """Validate a raw API response dict through the AssociatedFile Pydantic model.

        Preserves any extra fields returned by the server (extra='allow'), same
        pattern as DatasetOperations._parse(). Passes through None (e.g. a 204
        response with no body) unchanged.
        """
        if raw is None:
            return None
        from ..models import AssociatedFile
        return AssociatedFile.model_validate(raw).model_dump()

    def get(self, file_id: str) -> Dict:
        """Get metadata for a single file by its MFID.

        Args:
            file_id: File MFID

        Returns:
            Dict: File record (mfid, filename, storage_path, storage_backend,
                access_note, size, sha256_hash, dataset_mfid)
        """
        return self._parse(self._request('get', f'/files/{file_id}'))

    def list(self, limit: int = DEFAULT_LIMIT,
             sha256_hash: Optional[str] = None) -> List[Dict]:
        """List files across all accessible datasets.

        Args:
            limit: Maximum number of results
            sha256_hash: Filter by SHA-256 hex digest

        Returns:
            List[Dict]: File records (mfid, filename, storage_path, storage_backend,
                access_note, size, sha256_hash, dataset_mfid)
        """
        params = {}
        if sha256_hash:
            params['sha256_hash'] = sha256_hash
        return [self._parse(f) for f in self._paginate('/files', params, limit=limit)]

    def download(self, file_id: str, output_dir: str = '.') -> str:
        """Download a single file by MFID to a local directory.

        Args:
            file_id: File MFID
            output_dir: Directory to save the file (default: current directory)

        Returns:
            str: Path of the downloaded file

        Raises:
            RuntimeError: If the file has not been ingested yet, or if it's not
                stored on GCS (Crucible cannot fetch it directly in that case).
        """
        import tempfile

        file_record = self.get(file_id)

        backend = file_record.get('storage_backend') or 'gcs'
        if backend != 'gcs':
            note = f"\nNote: {file_record['access_note']}" if file_record.get('access_note') else ""
            raise RuntimeError(
                f"File {file_id} is stored on '{backend}', not GCS - Crucible can't fetch it directly.\n"
                f"Location: {file_record.get('storage_path') or '(not set)'}{note}"
            )

        if not file_record.get('storage_path'):
            raise RuntimeError(f"File {file_id} has not been ingested yet - cannot download")

        url = self.get_download_link(file_id)

        sp       = file_record.get('storage_path', '')
        prefix   = 'mf-storage-prod/'
        if sp.startswith(prefix):
            after  = sp[len(prefix):]
            _, _, name = after.partition('/')
        else:
            import os as _os
            name = _os.path.basename(file_record.get('filename') or file_id)

        import os
        output_path = os.path.join(output_dir, name)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        response = self._client._session.get(url, stream=True)
        response.raise_for_status()

        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(output_path)))
        try:
            with os.fdopen(tmp_fd, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    fh.write(chunk)
            os.replace(tmp_path, output_path)
        except Exception:
            os.unlink(tmp_path)
            raise

        logger.info(f"Downloaded {name} to {output_path}")
        return output_path



    def _skip_ingestion(self, file_id) -> Dict:

        log_message = f"Skipping ingestion for file {file_id}"
                   
        logger.info(log_message)
        params = {'status': 'not_requested'}

        ingestion_request = self._request('post', f'/files/{file_id}/ingest',
                                          params=params)

        logger.debug(f"Ingestion request created: id={ingestion_request.get('id')}, "
                     f"status={ingestion_request.get('status')}")
        
        return ingestion_request


    def request_ingestion(self,
                          file_id: str,
                          ingestion_class: Optional[str] = None,
                          wait_for_response: bool = False) -> Dict:
        
        """Request ingestion of an uploaded file.

        Args:
            file_id: File MFID
            ingestion_class: Ingestion class for the worker (e.g. 'lammps', 'nexus').
                Defaults to the server-side default if omitted.
            wait_for_response: Block until ingestion completes.

        Returns:
            Dict: IngestionRequest record (id, status, ...)
        """
        params = {'status':'requested'}
        if ingestion_class:
            params['ingestion_class'] = ingestion_class
            
        logger.info(f"Requesting ingestion for file {file_id}"
                    + (f" (class={ingestion_class})" if ingestion_class else ""))

        ingestion_request = self._request('post', f'/files/{file_id}/ingest', params=params)

        logger.debug(f"Ingestion request created: id={ingestion_request.get('id')}, "
                     f"status={ingestion_request.get('status')}")

        if wait_for_response and ingestion_request:
            self._client._wait_for_request_completion(ingestion_request['id'])

        return ingestion_request


    def delete(self, file_id: str) -> None:
        """Delete a file record by its MFID.

        Args:
            file_id: File MFID (AssociatedFile mfid)
        """
        self._request('delete', f'/files/{file_id}')


    def update(self, file_id: str, **updates) -> Dict:
        """Update fields on a file record.

        Args:
            file_id: File MFID
            **updates: Fields to update, e.g. storage_path='...', access_note='...'

        Returns:
            Dict: Updated file record.
        """
        return self._parse(self._request('patch', f'/files/{file_id}', json=updates))


    def get_download_link(self, file_id: str) -> str:
        """Get a signed download URL for a single file.

        Args:
            file_id: File MFID

        Returns:
            str: Signed URL valid for 1 hour, no auth required.

        Raises:
            HTTPError 404: File has not been ingested yet.
        """
        result = self._request('get', f'/files/{file_id}/download_link')
        return result['url']
