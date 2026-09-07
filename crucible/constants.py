#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package-wide constants for the Crucible API client.
"""

DEFAULT_LIMIT = 100   # default page size for list requests
API_PAGE_MAX  = 1000  # server hard cap per request

PROJECT_MEMBER_ROLES = ('viewer', 'contributor', 'editor', 'admin')

# Kinds of parent/child link between two datasets, or between two samples.
# Oriented child-relative-to-parent: 'is_part_of' reads "child is_part_of
# parent". A link may also carry no type at all. Client-side completion list;
# the server is authoritative for what it currently accepts.
RELATIONSHIP_TYPES = ('is_derived_from', 'is_part_of')

# Multipart upload defaults (tuned via benchmarking — see testing/tune_results.jsonl)
UPLOAD_CHUNK_SIZE_MB = 64   # GCS XML multipart part size in MiB
UPLOAD_MAX_WORKERS   = 8    # concurrent upload threads

AVAILABLE_INGESTORS = [
    'ApiUploadIngestor',
    'AFMIngestor',
    'TitanXSessionIngestor',
    'Team05SessionIngestor',
    'SimpleTiledImageScopeFoundryH5Ingestor',
    'BioGlowIngestor',
    'QSpleemSVRampIngestor',
    'QSpleemImageIngestor',
    'QSpleemARRESEKIngestor',
    'QSpleemARRESMMIngestor',
    'CanonCaptureScopeFoundryH5Ingestor',
    'SingleSpecScopeFoundryH5Ingestor',
    'HyperspecScopeFoundryH5Ingestor',
    'HyperspecSweepScopeFoundryH5Ingestor',
    'ToupcamLiveScopeFoundryH5Ingestor',
    'CLSyncRasterScanIngestor',
    'CLHyperspecIngestor',
    'SpinbotSpecLineIngestor',
    'SpinbotCameraCaptureIngestor',
    'SpinbotPhotoRunIngestor',
    'InSituPlIngestor',
    'CziIngestor',
    'DigitalMicrographIngestor',
    'SerIngestor',
    'BcfIngestor',
    'EmdIngestor',
    'SpinbotSpecRunIngestor',
    'ImageIngestor'
]
