#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package-wide constants for the Crucible API client.
"""

DEFAULT_LIMIT = 100   # default page size for list requests
API_PAGE_MAX  = 1000  # server hard cap per request

PROJECT_MEMBER_ROLES = ('viewer', 'contributor', 'editor', 'admin')
PROJECT_SCOPES = ('assigned', 'shared', 'all')

# Ordering and scoping options accepted by the dataset and sample collections.
RESOURCE_SORTS = ('created', 'updated', 'name')
SORT_DIRECTIONS = ('asc', 'desc')
VISIBILITIES = ('all', 'public', 'private')
AFFILIATIONS = ('owner',)

# Facet grouping fields and bucket ordering.
DATASET_FACET_FIELDS = ('session', 'measurement', 'data_format', 'owner',
                        'instrument', 'project')
SAMPLE_FACET_FIELDS = ('sample_type', 'owner', 'project')
FACET_SORTS = ('value', 'label', 'count')

# Deletion workflow scoping and ordering.
DELETION_REQUEST_SCOPES = ('accessible', 'submitted', 'reviewable')
DELETION_REQUEST_SORTS = ('request_time', 'resource_name', 'project_id',
                          'requester_name', 'status')
DELETION_AUDIT_SCOPES = ('all', 'submitted')

# Platform-wide roles a service account may hold.
PLATFORM_ROLES = ('none', 'contributor', 'support', 'admin')

# Values for the Crucible-Privilege-Mode request header.
PRIVILEGE_MODES = ('normal', 'elevated')

# None sends no header, so the server applies its legacy behavior: elevated for
# a platform administrator, normal for everyone else. Sending 'elevated'
# explicitly would instead be rejected with a 403 for ineligible callers.
DEFAULT_PRIVILEGE_MODE = None

# Kinds of parent/child link between two datasets, or between two samples.
# Oriented child-relative-to-parent: 'is_part_of' reads "child is_part_of
# parent". A link may also carry no type at all. Client-side completion list;
# the server is authoritative for what it currently accepts.
RELATIONSHIP_TYPES = ('is_derived_from', 'is_part_of')

# GCS bucket that dataset file storage_path values are prefixed with.
GCS_BUCKET_PREFIX = 'mf-storage-prod/'

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
