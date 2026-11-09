#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload helpers for Crucible datasets.

Every upload goes through the API's signed multipart flow
(signed_multipart.py): parts are PUT to URLs the API signs, so no storage
credentials or SDK are needed and any storage backend the API supports works.
"""

import logging
from typing import Dict, Optional, Tuple

from ...utils.deprecation import _removed
from .signed_multipart import Progress, upload_file_signed_multipart

logger = logging.getLogger(__name__)


def upload_file_gcs(client, dsid: str, file_path: str,
                    max_workers: Optional[int] = None,
                    progress: Optional[Progress] = None,
                    replace: bool = False) -> Tuple[Dict, bool]:
    """Upload a file to a dataset through the signed multipart flow.

    Args:
        client:      CrucibleClient instance (provides _request and _config).
        dsid:        Dataset MFID.
        file_path:   Local path to the file.
        max_workers: Parts uploaded in parallel; defaults to the
                     upload_max_workers setting.
        progress:    Called as progress(filename, bytes_done, total);
                     defaults to client.upload_progress.
        replace:     Replace the content of an existing file with this
                     filename instead of failing.

    Returns:
        Tuple[Dict, bool]: (AssociatedFileRead record, was_existing).
            was_existing is True when the dataset already held this content
            and nothing was uploaded.
    """
    return upload_file_signed_multipart(
        client, dsid, file_path,
        max_workers=max_workers or client._config.upload_max_workers,
        progress=progress or getattr(client, 'upload_progress', None),
        replace=replace)


@_removed("The legacy upload routes are gone; use upload_file_gcs().")
def upload_file_gcs_multipart(*args, **kwargs):
    pass


@_removed("The legacy upload routes are gone; use upload_file_gcs().")
def upload_file_gcs_resumable(*args, **kwargs):
    pass
