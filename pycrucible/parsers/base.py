#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 10 17:45:48 2026

@author: roncofaber
"""

import os
import logging
from pycrucible import BaseDataset

logger = logging.getLogger(__name__)

#%%

class BaseParser:

    _measurement = "base"
    _data_format = None
    _instrument_name = None

    def __init__(self, files_to_upload=None, project_id=None,
                 metadata=None, keywords=None, mfid=None,
                 measurement=None, owner_orcid=None, dataset_name=None,
                 session_name=None, public=False, instrument_name=None,
                 data_format=None, thumbnail=None):
        """
        Initialize the parser with dataset properties.

        Args:
            files_to_upload (list, optional): Files to upload
            project_id (str, optional): Crucible project ID
            metadata (dict, optional): Scientific metadata
            keywords (list, optional): Keywords for the dataset
            mfid (str, optional): Unique dataset identifier
            measurement (str, optional): Measurement type
            owner_orcid (str, optional): Owner's ORCID ID
            dataset_name (str, optional): Human-readable dataset name
            session_name (str, optional): Session name for grouping datasets
            public (bool, optional): Whether dataset is public. Defaults to False.
            instrument_name (str, optional): Instrument name
            data_format (str, optional): Data format type
        """
        # Use parser's defaults if not provided
        if measurement is None:
            measurement = self._measurement
        if data_format is None:
            data_format = self._data_format
        if instrument_name is None:
            instrument_name = self._instrument_name

        # Dataset properties
        self.project_id      = project_id
        self.files_to_upload = files_to_upload or []
        self.mfid            = mfid
        self.measurement     = measurement
        self.owner_orcid     = owner_orcid
        self.dataset_name    = dataset_name
        self.session_name    = session_name
        self.public          = public
        self.instrument_name = instrument_name
        self.data_format     = data_format
        self.source_folder   = os.getcwd()
        self.thumbnail       = thumbnail

        # initialize with user-provided metadata/keywords
        self.scientific_metadata = metadata or {}
        self.keywords = keywords or []
        self._client = None

        return

    def add_metadata(self, metadata_dict):
        """
        Merge additional metadata into parser's metadata.

        Args:
            metadata_dict (dict): Metadata to merge. Updates existing values.
        """
        if self.scientific_metadata is None:
            self.scientific_metadata = {}
        self.scientific_metadata.update(metadata_dict)

    def add_keywords(self, keywords_list):
        """
        Add unique keywords to parser's keyword list.

        Args:
            keywords_list (list): Keywords to add. Duplicates are ignored.
        """
        if self.keywords is None:
            self.keywords = []
        existing = set(self.keywords)
        for kw in keywords_list:
            if kw not in existing:
                self.keywords.append(kw)
                existing.add(kw)

    @property
    def client(self):
        """Get or create CrucibleClient instance (lazy loaded)."""
        if self._client is None:
            from pycrucible.config import get_client
            self._client = get_client()
        return self._client

    def to_dataset(self):
        """
        Convert parser data to a Crucible dataset object.

        Uses instance variables for all dataset properties.

        Returns:
            BaseDataset: Crucible dataset object
        """
        # Use the first file from files_to_upload as the main file
        file_to_upload = self.files_to_upload[0] if self.files_to_upload else None

        crucible_dataset = BaseDataset(
            unique_id      = self.mfid,
            measurement    = self.measurement,
            project_id     = self.project_id,
            owner_orcid    = self.owner_orcid,
            dataset_name   = self.dataset_name,
            session_name   = self.session_name,
            public         = self.public,
            instrument_name = self.instrument_name,
            data_format    = self.data_format,
            source_folder  = self.source_folder,
            file_to_upload = file_to_upload
        )

        return crucible_dataset
    
    def upload_dataset(self, ingestor='ApiUploadIngestor',
                       verbose=False, wait_for_ingestion_response=True):
        """
        Upload the parsed dataset to Crucible.

        Uses instance variables for all dataset properties (mfid, measurement,
        project_id, owner_orcid, dataset_name, metadata, keywords).

        Args:
            ingestor (str, optional): Ingestion class to use. Defaults to 'ApiUploadIngestor'
            verbose (bool, optional): Print detailed progress. Defaults to False.
            wait_for_ingestion_response (bool, optional): Wait for ingestion to complete. Defaults to True.

        Returns:
            dict: Dictionary containing 'created_record', 'scientific_metadata_record',
                  'ingestion_request', and 'uploaded_files'
        """
        # Create dataset object from instance variables
        dataset = self.to_dataset()

        # Upload to Crucible
        result = self.client.create_new_dataset_from_files(
            dataset,
            files_to_upload=self.files_to_upload,
            scientific_metadata=self.scientific_metadata,
            keywords=self.keywords,
            # get_user_info_function=self.client.get_user,
            ingestor=ingestor,
            verbose=verbose,
            wait_for_ingestion_response=wait_for_ingestion_response
        )
        
        if self.thumbnail is not None:
            self.client.add_thumbnail(self.mfid, self.thumbnail)
        
        return result