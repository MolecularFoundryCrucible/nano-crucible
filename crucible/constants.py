#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package-wide constants for the Crucible API client.
"""

DEFAULT_LIMIT = 100   # default page size for list requests
API_PAGE_MAX  = 1000  # server hard cap per request

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