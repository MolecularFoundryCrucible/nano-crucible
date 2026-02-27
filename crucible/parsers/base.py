#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 10 17:45:48 2026

@author: roncofaber
"""

import os
import socket
import json
import logging
from pathlib import Path
from crucible import BaseDataset

logger = logging.getLogger(__name__)

#%%

class BaseParser:

    _measurement = "base"
    _data_format = None
    _instrument_name = None

    def __init__(self, files_to_upload=None, project_id=None,
                 metadata=None, keywords=None, mfid=None,
                 measurement=None, dataset_name=None,
                 session_name=None, public=False, instrument_name=None,
                 data_format=None):
        """
        Initialize the parser with dataset properties.

        Args:
            files_to_upload (str, list, or None): File(s) to upload. Can be a single file path (str) or list of file paths
            project_id (str, optional): Crucible project ID
            metadata (dict or str, optional): Scientific metadata as dict or path to JSON file
            keywords (list, optional): Keywords for the dataset
            mfid (str, optional): Unique dataset identifier
            measurement (str, optional): Measurement type
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

        # Handle files_to_upload - convert string to list if needed
        if files_to_upload is None:
            files_to_upload = []
        elif isinstance(files_to_upload, str):
            files_to_upload = [files_to_upload]

        # Dataset properties
        self.project_id      = project_id
        self.files_to_upload = files_to_upload
        self.mfid            = mfid
        self.measurement     = measurement
        self.dataset_name    = dataset_name
        self.session_name    = session_name
        self.public          = public
        self.instrument_name = instrument_name
        self.data_format     = data_format
        self.source_folder   = os.getcwd()
        self.thumbnail       = None

        # Handle metadata - can be a dict or path to JSON file
        metadata_dict = self._load_metadata(metadata)

        # Initialize with user-provided metadata/keywords
        self.scientific_metadata = metadata_dict or {}
        self.keywords = keywords or []
        self._client = None

        # Call parser-specific extraction (Template Method Pattern)
        self.parse()

        return

    def parse(self):
        """
        Parse domain-specific files and extract metadata.

        This is a hook method that subclasses should override to implement
        their specific parsing logic. The base implementation does nothing
        (generic upload with no parsing).

        Subclasses should:
        - Read and parse domain-specific file formats
        - Call self.add_metadata() to merge extracted metadata with user-provided metadata
        - Call self.add_keywords() to add domain-specific keywords to user-provided keywords
        - Update self.files_to_upload if needed (e.g., add related files)
        - Set self.thumbnail if generating a visualization
        - Access all instance variables (self.mfid, self.project_id, etc.)

        Example:
            def parse(self):
                # Parse files
                input_file = self.files_to_upload[0]
                metadata = self._parse_file(input_file)

                # Add to instance
                self.add_metadata(metadata)
                self.add_keywords(["domain", "specific"])
                self.thumbnail = self._generate_thumbnail()
        """
        pass  # BaseParser does nothing - generic upload

    @staticmethod
    def _load_metadata(metadata):
        """
        Load metadata from dict or JSON file.

        Args:
            metadata (dict, str, or None): Metadata as dict, path to JSON file, or None

        Returns:
            dict or None: Loaded metadata dictionary

        Raises:
            FileNotFoundError: If metadata is a string but file doesn't exist
            json.JSONDecodeError: If file exists but contains invalid JSON
        """
        if metadata is None:
            return None

        # If it's already a dict, return it
        if isinstance(metadata, dict):
            return metadata

        # If it's a string, treat it as a file path
        if isinstance(metadata, str):
            metadata_path = Path(metadata)
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata_dict = json.load(f)
                    logger.info(f"Loaded metadata from file: {metadata_path}")
                    return metadata_dict
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in metadata file {metadata_path}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error reading metadata file {metadata_path}: {e}")
                    raise
            else:
                raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        # If we get here, metadata is an unsupported type
        raise TypeError(f"metadata must be a dict, str (path to JSON file), or None, got {type(metadata)}")

    def add_metadata(self, metadata):
        """
        Merge additional metadata into parser's metadata.

        Args:
            metadata (dict or str): Metadata to merge as dict or path to JSON file.
                                   Updates existing values.

        Raises:
            FileNotFoundError: If metadata is a string but file doesn't exist
            json.JSONDecodeError: If file exists but contains invalid JSON
            TypeError: If metadata is neither dict nor str
        """
        # Load metadata (handles dict, file path, or None)
        metadata_dict = self._load_metadata(metadata)

        if metadata_dict is not None:
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

    def add_thumbnail(self, image):
        """
        Add a thumbnail image to the dataset.

        Args:
            image: Can be:
                - str or Path: Path to an image file
                - PIL.Image: PIL Image object
                - matplotlib.figure.Figure: Matplotlib figure
                - numpy.ndarray: Numpy array (will be saved as PNG)

        Raises:
            FileNotFoundError: If image is a path but file doesn't exist
            TypeError: If image type is not supported

        Note:
            The thumbnail will be automatically uploaded when upload_dataset() is called.
            Image objects (PIL, matplotlib, numpy) are saved to a temporary directory.
        """
        # Case 1: File path (str or Path)
        if isinstance(image, (str, Path)):
            image_path = Path(image)

            # Validate file exists
            if not image_path.exists():
                raise FileNotFoundError(f"Thumbnail image not found: {image_path}")

            # Set thumbnail path
            self.thumbnail = str(image_path.absolute())
            logger.info(f"Thumbnail set to: {self.thumbnail}")
            return

        # Case 2: Image object - need to save to temporary directory
        import tempfile
        import random
        import string

        # Use system temp directory (platform-independent)
        temp_dir = tempfile.gettempdir()
        thumbnail_dir = os.path.join(temp_dir, 'crucible_thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)

        # Use mfid if available, otherwise generate random name
        if self.mfid:
            filename = f'{self.mfid}.png'
        else:
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            filename = f'thumbnail_{random_str}.png'

        thumbnail_path = os.path.join(thumbnail_dir, filename)

        # Try PIL Image
        try:
            from PIL import Image as PILImage
            if isinstance(image, PILImage.Image):
                image.save(thumbnail_path, format='PNG')
                self.thumbnail = thumbnail_path
                logger.info(f"PIL Image saved as thumbnail: {thumbnail_path}")
                return
        except ImportError:
            pass

        # Try matplotlib Figure
        try:
            from matplotlib.figure import Figure
            if isinstance(image, Figure):
                image.savefig(thumbnail_path, format='png', bbox_inches='tight', dpi=150)
                self.thumbnail = thumbnail_path
                logger.info(f"Matplotlib Figure saved as thumbnail: {thumbnail_path}")
                return
        except ImportError:
            pass

        # Try numpy array
        try:
            import numpy as np
            if isinstance(image, np.ndarray):
                from PIL import Image as PILImage
                # Assume array is in format (H, W) or (H, W, C)
                pil_image = PILImage.fromarray(image)
                pil_image.save(thumbnail_path, format='PNG')
                self.thumbnail = thumbnail_path
                logger.info(f"Numpy array saved as thumbnail: {thumbnail_path}")
                return
        except ImportError:
            pass

        # If we get here, unsupported type
        raise TypeError(f"Unsupported thumbnail type: {type(image)}. "
                       f"Supported types: str, Path, PIL.Image, matplotlib.Figure, numpy.ndarray")

    @property
    def client(self):
        """Get or create CrucibleClient instance (lazy loaded)."""
        if self._client is None:
            from crucible.config import get_client
            self._client = get_client()
        return self._client

    def to_dataset(self):
        """
        Convert parser data to a Crucible dataset object.

        Uses instance variables for all dataset properties.

        Returns:
            BaseDataset: Crucible dataset object
        """

        crucible_dataset = BaseDataset(
            unique_id      = self.mfid,
            measurement    = self.measurement,
            project_id     = self.project_id,
            owner_orcid    = None,  # API key handles user authentication
            dataset_name   = self.dataset_name,
            session_name   = self.session_name,
            public         = self.public,
            instrument_name = self.instrument_name,
            data_format    = self.data_format,
            source_folder  = self.source_folder,
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

        # Upload to Crucible using resource-based API
        result = self.client.datasets.create(
            dataset,
            files_to_upload=self.files_to_upload,
            scientific_metadata=self.scientific_metadata,
            keywords=self.keywords,
            # get_user_info_function=self.client.get_user,
            ingestor=ingestor,
            verbose=verbose,
            wait_for_ingestion_response=wait_for_ingestion_response
        )

        dataset_id = result['dsid']
        logger.info(f"Dataset uploaded successfully: {dataset_id}")
        logger.info(f"  Dataset name: {result['created_record'].get('dataset_name', 'N/A')}")
        logger.info(f"  Project: {result['created_record'].get('project_id', 'N/A')}")

        if self.thumbnail is not None:
            self.client.datasets.add_thumbnail(dataset_id, self.thumbnail)
            logger.info(f"  Thumbnail uploaded")

        return result