#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File resource operations — scoped to a single file MFID (/files/* endpoints).

For dataset-scoped file operations (upload, download, thumbnails, ingestion)
see DatasetOperations (client.datasets.*).
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from .base import BaseResource, ListResult
from ..constants import DEFAULT_LIMIT
from ..utils.io import safe_output_path, storage_display_name

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
             sha256_hash: Optional[str] = None,
             offset: int = 0,
             cursor: Optional[str] = None) -> List[Dict]:
        """List files across all accessible datasets.

        Args:
            limit: Maximum number of results
            sha256_hash: Filter by SHA-256 hex digest
            offset: Starting position in the full result set (default: 0).
            cursor: Continuation token from a previous result's next_cursor;
                the listing resumes there.

        Returns:
            List[Dict]: File records (mfid, filename, storage_path, storage_backend,
                access_note, size, sha256_hash, dataset_mfid)
        """
        params = {}
        if sha256_hash:
            params['sha256_hash'] = sha256_hash
        raw = self._paginate('/files', params, limit=limit, offset=offset, cursor=cursor)
        return ListResult.like(raw, [self._parse(f) for f in raw])

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

        name = storage_display_name(file_record) or file_id

        import os
        output_path = safe_output_path(output_dir, name)
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
            Dict: IngestionRequest record (id, status, ...); with
            wait_for_response, the record in its final state.
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
            ingestion_request = self._client._wait_for_request_completion(ingestion_request['id'])

        return ingestion_request


    def delete(self, file_id: str) -> None:
        """Delete a file record by its MFID.

        Args:
            file_id: File MFID (AssociatedFile mfid)
        """
        self._request('delete', f'/files/{file_id}')


    def update(self, file_id: str, **updates: Any) -> Dict:
        """Update fields on a file record.

        Args:
            file_id: File MFID
            **updates: Fields to update, e.g. storage_path='...', access_note='...'

        Returns:
            Dict: Updated file record.
        """
        return self._parse(self._request('patch', f'/files/{file_id}', json=updates))


    def replace(self, file_id: str, file_path: str, etag: Optional[str] = None,
                ingestion_class: Optional[str] = None,
                wait_for_ingestion_response: bool = False,
                skip_ingestion: bool = False,
                max_workers: Optional[int] = None,
                progress: Optional[Callable[[str, int, int], None]] = None) -> Dict:
        """Replace a GCS file's content, keeping its MFID, filename, and metadata.

        The new content uploads through the signed multipart flow and the
        record is repointed once it is verified; the file stays downloadable
        meanwhile. Needs EDIT on the file's dataset.

        Args:
            file_id: MFID of the file to replace.
            file_path: Local path to the new content.
            etag: The file's ``etag`` as you last read it. The replace is then
                refused if the file changed since; None replaces whatever is
                current.
            ingestion_class: Ingestion class for the worker; defaults to
                server auto-detection.
            wait_for_ingestion_response: Block until ingestion completes.
            skip_ingestion: Replace without requesting ingestion. Also implied
                when client.request_ingestion is False.
            max_workers: Parts uploaded in parallel (default 8).
            progress: Called as progress(filename, bytes_done, total); defaults
                to client.upload_progress.

        Returns:
            Dict: {'associated_file': the updated record, 'ingestion_request':
            IngestionRequest or None}. No ingestion is requested when the file
            already held this content.
        """
        from .gcs.signed_multipart import replace_file_signed_multipart

        record, unchanged = replace_file_signed_multipart(
            self._client, file_id, file_path, etag=etag, max_workers=max_workers,
            progress=progress or getattr(self._client, 'upload_progress', None))
        record = self._parse(record)
        if unchanged:
            logger.info(f"{record.get('filename')} already holds this content, nothing replaced")
            return {'associated_file': record, 'ingestion_request': None}
        if skip_ingestion or not getattr(self._client, 'request_ingestion', True):
            return {'associated_file': record, 'ingestion_request': self._skip_ingestion(file_id)}
        return {'associated_file': record,
                'ingestion_request': self.request_ingestion(file_id, ingestion_class,
                                                            wait_for_ingestion_response)}

    def get_download_link(self, file_id: str, disposition: Optional[str] = None) -> str:
        """Get a signed download URL for a single file.

        Args:
            file_id: File MFID
            disposition: "attachment" (the server default) to download, or
                "inline" to let a browser display the file. HTML, SVG, and XML
                always download.

        Returns:
            str: Signed URL valid for 1 hour, no auth required.

        Raises:
            HTTPError 404: File has not been ingested yet.
        """
        params = {'disposition': disposition} if disposition else None
        result = self._request('get', f'/files/{file_id}/download_link', params=params)
        return result['url']
