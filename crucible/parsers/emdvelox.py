#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EMD Parser

Created on Wed Feb 25 2026
"""

import os
import logging
from .base import BaseParser

from ncempy.io import emdVelox
from crucible import BaseDataset

logger = logging.getLogger(__name__)

class EMDVeloxParser(BaseParser):
    _measurement = "EMD"
    _data_format = "EMD" 
    _instrument_name = None # change?

    def parse(self):
        # Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Use first file as EMD input
        input_file = os.path.abspath(self.files_to_upload[0])
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")

        # Read input file using ncempy 
        ncempy_datafile = emdVelox.fileEMDVelox(input_file)

        # custom attribute: measurement_scientific_metadata
        # self.measurement_scientific_metadata = [ncempy_datafile.getMetadata(d) for d in ncempy_datafile.list_data]
        self.measurement_scientific_metadata = [ncempy_datafile.parseMetaData(d) for d in ncempy_datafile.list_data]

    def upload_dataset(self, ingestor='ApiUploadIngestor', verbose=False, wait_for_ingestion_response=True):
        # upload the dataset for the entire file 
        file_upload_result = super().upload_dataset(ingestor, verbose, wait_for_ingestion_response)
        file_dsid = file_upload_result['created_record']['unique_id'] # if using create_new_dataset instead of create_new_dataset_from_files, can directly use 

        # create & upload a dataset for each measurement
        for md in self.measurement_scientific_metadata: 
            detector = md['Detector'] # only works if BinaryResult is unpacked.
            # create dataset
            measurement_ds = BaseDataset(
                # unique_id      = self.mfid, # need a new id for each measurement ds?
                measurement    = detector,
                project_id     = self.project_id,
                owner_orcid    = None,  # API key handles user authentication
                dataset_name   = self.dataset_name + f"({detector})",
                session_name   = self.session_name,
                public         = self.public,
                instrument_name = self.instrument_name + f"({detector})",
                data_format    = self.data_format,
                source_folder  = self.source_folder,
                file_to_upload = self.files_to_upload[0])
        
            # upload dataset to crucible: use create_new_dataset instead, if no file needed
            measurement_upload_result = self.client.create_new_dataset_from_files(
                measurement_ds,
                files_to_upload=self.files_to_upload,
                scientific_metadata=md,
                keywords=self.keywords,
                # get_user_info_function=self.client.get_user,
                ingestor=ingestor,
                verbose=verbose,
                wait_for_ingestion_response=wait_for_ingestion_response)
            measurement_dsid = measurement_upload_result['created_record']['unique_id']

            # link measurement dataset (child) with file dataset (parent)
            self.client.link_datasets(file_dsid, measurement_dsid)

        return file_upload_result