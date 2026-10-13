#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GCS upload helpers for Crucible datasets.

Standalone functions — take an explicit `client` argument rather than `self`
so they can be tested in isolation and reused outside of any resource class.

Three strategies:
  - upload_file_signed_multipart : parallel parts to API-signed URLs (signed_multipart.py)
  - upload_file_gcs_multipart    : legacy parallel XML multipart via a vended token
  - upload_file_gcs_resumable    : sequential chunked resumable URI (plain requests)

upload_file_gcs() picks one from the `multipart` flag and the upload protocol.
"""

import os
import logging
import requests
from typing import Dict, Optional, Tuple

from ...constants import UPLOAD_PROTOCOLS
from ...utils.io import hash_file
from .signed_multipart import (Progress, SignedMultipartUnavailable,
                               upload_file_signed_multipart)

logger = logging.getLogger(__name__)


def upload_file_gcs(client, dsid: str, file_path: str,
                    multipart: bool = True,
                    chunk_size_mb: Optional[int] = None,
                    max_workers: Optional[int] = None,
                    protocol: Optional[str] = None,
                    progress: Optional[Progress] = None,
                    replace: bool = False) -> Tuple[Dict, bool]:
    """Dispatch to a multipart or resumable upload.

    Args:
        client:        CrucibleClient instance (provides _request and _config).
        dsid:          Dataset unique identifier.
        file_path:     Local path to the file.
        multipart:     Use parallel multipart (default True); False = sequential resumable.
        chunk_size_mb: Chunk size in MiB for the legacy token route; signed
                       uploads use the server's part size.
        max_workers:   Upload threads — overrides config if provided.
        protocol:      "auto", "signed", or "legacy" for multipart uploads;
                       defaults to client.upload_protocol, then the
                       upload_protocol setting. "auto" falls
                       back to the legacy token route when the server has
                       signed uploads switched off.
        progress:      Called as progress(filename, bytes_done, total) by
                       signed uploads; defaults to client.upload_progress.
        replace:       Replace the content of an existing file with this
                       filename. Needs signed uploads, so it never uses the
                       legacy route.

    Returns:
        Tuple[Dict, bool]: (AssociatedFileRead record, was_existing).
            was_existing is True when the file was a dedup hit and the upload was skipped.
    """
    if not multipart:
        return upload_file_gcs_resumable(client, dsid, file_path)
    protocol = (protocol or getattr(client, 'upload_protocol', None)
                or client._config.upload_protocol)
    progress = progress or getattr(client, 'upload_progress', None)
    if protocol not in UPLOAD_PROTOCOLS:
        raise ValueError(f"protocol must be one of: {', '.join(UPLOAD_PROTOCOLS)}.")
    if replace:
        if protocol == 'legacy':
            raise ValueError("Replacing a file needs signed uploads; the legacy upload "
                             "protocol cannot replace.")
        try:
            return upload_file_signed_multipart(client, dsid, file_path, max_workers=max_workers,
                                                progress=progress, replace=True)
        except SignedMultipartUnavailable as error:
            raise RuntimeError("Signed multipart uploads are switched off on this server, "
                               "and replacing a file needs them.") from error
    use_signed = protocol == 'signed' or (
        protocol == 'auto' and not getattr(client, '_signed_uploads_unavailable', False))
    if use_signed:
        try:
            return upload_file_signed_multipart(client, dsid, file_path,
                                                max_workers=max_workers, progress=progress)
        except SignedMultipartUnavailable as error:
            if protocol == 'signed':
                raise
            if os.path.getsize(file_path):
                client._signed_uploads_unavailable = True
            logger.info(f"{error} Using the legacy upload route.")
    return upload_file_gcs_multipart(client, dsid, file_path,
                                     chunk_size_mb=chunk_size_mb,
                                     max_workers=max_workers)


def upload_file_gcs_multipart(client, dsid: str, file_path: str,
                               chunk_size_mb: Optional[int] = None,
                               max_workers: Optional[int] = None) -> Tuple[Dict, bool]:
    """Parallel multipart upload via the GCS SDK (upload_chunks_concurrently).

    The Crucible API vends a short-lived OAuth2 token via
    POST /datasets/{dsid}/upload/initiate/multipart so no GCS credentials
    are required on the client side.

    Args:
        client:        CrucibleClient instance.
        dsid:          Dataset unique identifier.
        file_path:     Local path to the file.
        chunk_size_mb: Part size in MiB (default from config: 64 MiB).
        max_workers:   Concurrent upload threads (default from config: 8).

    Returns:
        Tuple[Dict, bool]: (AssociatedFileRead, was_existing).
    """
    from google.cloud import storage
    from google.cloud.storage import transfer_manager
    from google.oauth2.credentials import Credentials

    cfg      = client._config
    _CHUNK   = (chunk_size_mb or cfg.upload_chunk_size_mb) * 1024 * 1024
    _WORKERS = max_workers or cfg.upload_max_workers

    file_size = os.path.getsize(file_path)
    filename  = os.path.basename(file_path)

    logger.info(f"Uploading {filename} ({file_size / 1024**2:.1f} MB) "
                f"to dataset {dsid} [parallel, {_WORKERS} workers]")

    sha256_hash, local_crc32c_b64 = hash_file(file_path, block_size=_CHUNK)

    init = client._request('post', f'/datasets/{dsid}/upload/initiate/multipart',
                           json={'filename': filename, 'size': file_size,
                                 'sha256_hash': sha256_hash})

    if init.get('existing_file') is not None:
        logger.info(f"{filename} already exists in dataset {dsid}, skipping upload")
        return init['existing_file'], True

    upload_id = init['upload_id']

    gcs = storage.Client(
        credentials=Credentials(token=init['access_token']),
        project=init['project'],
    )
    blob = gcs.bucket(init['bucket']).blob(f"{init['object_prefix']}{filename}")

    logger.debug(f"Starting parallel upload: upload_id={upload_id}, "
                 f"chunk={_CHUNK >> 20} MiB, workers={_WORKERS}")

    # No per-chunk checksum — known SDK bug (sends CRC32C in a way GCS rejects).
    # We verify the final assembled object below instead, which is a stronger guarantee.
    transfer_manager.upload_chunks_concurrently(
        file_path,
        blob,
        chunk_size=_CHUNK,
        max_workers=_WORKERS,
        worker_type=transfer_manager.THREAD,
    )

    # Verify assembled object CRC32C against our local hash.
    blob.reload()
    if blob.crc32c and blob.crc32c != local_crc32c_b64:
        raise RuntimeError(
            f"CRC32C mismatch for {filename} after assembly: "
            f"local={local_crc32c_b64} gcs={blob.crc32c}"
        )
    logger.debug(f"CRC32C verified: {local_crc32c_b64}")

    logger.info(f"Completing upload for {filename} (upload_id={upload_id})")
    file_record = client._request('post', f'/datasets/{dsid}/upload/complete',
                                  json={'upload_id': upload_id, 'sha256_hash': sha256_hash})
    return file_record, False


def upload_file_gcs_resumable(client, dsid: str, file_path: str) -> Tuple[Dict, bool]:
    """Sequential chunked resumable upload via a GCS resumable session URI.

    Does not require the google-cloud-storage SDK. The Crucible API initiates
    the resumable session and returns a signed URI; chunks are PUT directly
    to GCS using plain requests.

    Args:
        client:    CrucibleClient instance.
        dsid:      Dataset unique identifier.
        file_path: Local path to the file.

    Returns:
        Tuple[Dict, bool]: (AssociatedFileRead, was_existing).
    """
    _256K        = 256 * 1024
    _MIN_CHUNK   = 32 * 1024 * 1024   # 32 MiB floor
    _MAX_RETRIES = 3

    file_size = os.path.getsize(file_path)
    filename  = os.path.basename(file_path)

    logger.info(f"Uploading {filename} ({file_size / 1024**2:.1f} MB) to dataset {dsid}")

    sha256_hash, local_crc32c_b64 = hash_file(file_path, block_size=_MIN_CHUNK)

    init = client._request('post', f'/datasets/{dsid}/upload/initiate',
                           json={'filename': filename, 'size': file_size,
                                 'sha256_hash': sha256_hash})

    if init.get('existing_file') is not None:
        logger.info(f"File {filename} already exists in dataset {dsid}, skipping upload")
        return init['existing_file'], True

    upload_id  = init['upload_id']
    uri        = init['resumable_uri']
    raw_hint   = init.get('chunk_size_hint', _MIN_CHUNK)
    chunk_size = max((max(raw_hint, _MIN_CHUNK) // _256K) * _256K, _256K)

    logger.debug(f"Chunked upload initiated: upload_id={upload_id}, "
                 f"chunk_size={chunk_size >> 20} MiB")

    with open(file_path, 'rb') as f:
        offset = 0
        while offset < file_size:
            f.seek(offset)
            chunk     = f.read(chunk_size)
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
                    try:
                        remote_crc32c = resp.json().get('crc32c')
                    except ValueError:
                        remote_crc32c = None
                    if remote_crc32c and remote_crc32c != local_crc32c_b64:
                        raise RuntimeError(
                            f"GCS crc32c mismatch for {filename}: "
                            f"local={local_crc32c_b64} remote={remote_crc32c}"
                        )
                    offset = file_size
                    break
                elif resp.status_code == 308:
                    offset = chunk_end + 1
                    logger.debug(f"Chunk accepted, offset={offset}/{file_size}")
                    break
                else:
                    logger.warning(
                        f"{filename} GCS chunk rejected offset={offset} "
                        f"status={resp.status_code} attempt={attempt+1}/{_MAX_RETRIES} "
                        f"body={resp.text[:300]}"
                    )
                    if attempt == _MAX_RETRIES - 1:
                        raise RuntimeError(
                            f"GCS chunk upload failed after {_MAX_RETRIES} attempts "
                            f"(status {resp.status_code}): {resp.text}"
                        )
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
                    chunk     = f.read(chunk_size)
                    chunk_end = offset + len(chunk) - 1

    logger.info(f"Completing upload for {filename} (upload_id={upload_id})")
    file_record = client._request('post', f'/datasets/{dsid}/upload/complete',
                                  json={'upload_id': upload_id, 'sha256_hash': sha256_hash})
    return file_record, False
