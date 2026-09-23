#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GCS download helpers for Crucible datasets.

Standalone functions — take an explicit `client` argument so they can be
tested in isolation and reused outside of any resource class.

Note on parallelism: file downloads within a single dataset are sequential.
To download multiple datasets concurrently, use ThreadPoolExecutor at the
caller level wrapping datasets.download().
"""

import fnmatch
import logging
import os
import tempfile
from typing import Dict, List, Optional

from ...utils.io import storage_display_name

logger = logging.getLogger(__name__)


def bare_name(file_record: Dict, dsid: str) -> str:
    """Extract the display filename from a file record."""
    return storage_display_name(file_record, dsid)


def download_dataset_files(client, dsid: str, output_dir: str,
                           link_map: Dict[str, str],
                           all_files: List[Dict],
                           overwrite_existing: bool = True,
                           include: Optional[List[str]] = None,
                           exclude: Optional[List[str]] = None) -> List[str]:
    """Download ingested files for a dataset into output_dir.

    Files are downloaded sequentially. To parallelise across multiple
    datasets, wrap datasets.download() in a ThreadPoolExecutor at the
    caller level.

    Args:
        client:            CrucibleClient instance.
        dsid:              Dataset unique identifier.
        output_dir:        Local directory to write files into.
        link_map:          {mfid: signed_url} from get_download_links().
        all_files:         List of file records from list_files(dsid).
        overwrite_existing: Overwrite existing local files (default True).
        include:           Glob patterns — only download matching filenames.
        exclude:           Glob patterns — skip matching filenames.

    Returns:
        List[str]: Paths of all downloaded files.
    """
    candidates = []
    for f in all_files:
        name = bare_name(f, dsid)
        if not name:
            continue
        url = link_map.get(f.get('mfid', ''))
        if url:
            candidates.append((f, name, url))
        else:
            backend = f.get('storage_backend') or 'gcs'
            if backend != 'gcs':
                logger.info(f"Skipping '{name}': stored on '{backend}', not GCS - "
                           f"see storage_path/access_note ({f.get('storage_path') or 'not set'})")

    if include:
        candidates = [(f, n, u) for f, n, u in candidates
                      if any(fnmatch.fnmatch(n, p) for p in include)]
    if exclude:
        candidates = [(f, n, u) for f, n, u in candidates
                      if not any(fnmatch.fnmatch(n, p) for p in exclude)]

    if not candidates:
        return []

    downloads = []
    for _, name, signed_url in candidates:
        download_path = os.path.join(output_dir, name)

        if not overwrite_existing and os.path.exists(download_path):
            downloads.append(download_path)
            continue

        dest_dir = os.path.dirname(download_path) or output_dir
        os.makedirs(dest_dir, exist_ok=True)

        response = client._session.get(signed_url, stream=True)
        response.raise_for_status()

        tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
        try:
            with os.fdopen(tmp_fd, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    fh.write(chunk)
            os.replace(tmp_path, download_path)
        except Exception:
            os.unlink(tmp_path)
            raise

        logger.debug(f"Downloaded {name}")
        downloads.append(download_path)

    return downloads
