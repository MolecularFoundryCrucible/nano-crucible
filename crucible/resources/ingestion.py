#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingestion request operations for the Crucible API.

Access via: client.ingestions.list(), client.ingestions.get(), etc.
"""

import logging
import time
from typing import Dict, List, Optional

from .base import BaseResource
from ..constants import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


def _one_of(name, value, alias, alias_value):
    if alias_value is None:
        return value
    if value is not None and value != alias_value:
        raise ValueError(f"{name} and {alias} name the same filter; pass only one")
    return alias_value


class IngestionOperations(BaseResource):
    """Operations on ingestion requests (/ingestion_requests endpoints).

    Access via: client.ingestions.list(), client.ingestions.get(), etc.
    """

    def list(self, dataset_mfid: Optional[str] = None,
             file_mfid: Optional[str] = None,
             limit: int = DEFAULT_LIMIT,
             offset: int = 0,
             cursor: Optional[str] = None,
             *,
             dsid: Optional[str] = None,
             file_id: Optional[str] = None) -> List[Dict]:
        """List ingestion requests, optionally filtered by dataset or file.

        Args:
            dataset_mfid: Filter by dataset MFID
            file_mfid: Filter by file MFID
            limit: Maximum number of results
            offset: Starting position in the full result set (default: 0).
            cursor: Continuation token from a previous result's next_cursor;
                the listing resumes there.
            dsid: Same as dataset_mfid.
            file_id: Same as file_mfid.

        Returns:
            List[Dict]: IngestionRequest records
        """
        dataset_mfid = _one_of('dataset_mfid', dataset_mfid, 'dsid', dsid)
        file_mfid = _one_of('file_mfid', file_mfid, 'file_id', file_id)
        params = {}
        if dataset_mfid:
            params['dataset_mfid'] = dataset_mfid
        if file_mfid:
            params['file_mfid'] = file_mfid
        return self._paginate('/ingestion_requests', params, limit=limit, offset=offset, cursor=cursor)

    def get(self, request_id: str) -> Dict:
        """Get the status of a single ingestion request.

        Args:
            request_id: Ingestion request ID

        Returns:
            Dict: IngestionRequest record (id, status, ...)
        """
        return self._request('get', f'/ingestion_requests/{request_id}')

    def wait(self, request_id: str, sleep_interval: int = 1) -> Dict:
        """Poll an ingestion request until it reaches a terminal state.

        Args:
            request_id: Ingestion request ID
            sleep_interval: Seconds between status checks (default 1)

        Returns:
            Dict: Final IngestionRequest record
        """
        req = self.get(request_id)
        logger.info("Waiting for ingestion request to complete...")
        while req['status'] in ('requested', 'started'):
            time.sleep(sleep_interval)
            req = self.get(request_id)
            logger.info(f"Current status: {req['status']}")
        logger.info(f"Request completed with status: {req['status']}")
        return req

    def update(self, request_id: str, status: str,
               ingestion_githash: Optional[str] = None,
               ingestion_class: Optional[str] = None,
               timezone: str = "America/Los_Angeles") -> Dict:
        """Update the status of an ingestion request. Requires edit access to the
        parent dataset.

        Args:
            request_id: Ingestion request ID
            status: New status ('complete', 'in_progress', 'failed')
            ingestion_githash: Git hash of the ingestion worker version. Omitted
                from the request when None, leaving any stored value intact.
            ingestion_class: Ingestion class used. Omitted when None.
            timezone: Timezone for the completion timestamp

        Returns:
            Dict: Updated IngestionRequest record
        """
        from ..utils import get_tz_isoformat

        patch_json = {
            'id': request_id,
            'status': status,
        }
        if ingestion_githash is not None:
            patch_json['ingestion_githash'] = ingestion_githash
        if ingestion_class is not None:
            patch_json['ingestion_class'] = ingestion_class
        if status == "complete":
            patch_json["time_completed"] = get_tz_isoformat(timezone)

        return self._request('patch', f'/ingestion_requests/{request_id}', json=patch_json)

    def list_ingestors(self) -> List[str]:
        """List available ingestion classes.

        Returns:
            List[str]: Ingestion class names.
        """
        return self._request('get', '/ingestors')
