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
    _data_format = "EMD" 
    _instrument_name = None # Spectre?

    def parse(self):
        # Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Use first file as EMD input
        input_file = os.path.abspath(self.files_to_upload[0])
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")
        
        # Read input file using ncempy 
        self._ncempy_datafile = emdVelox.fileEMDVeloxWithSpectra(input_file)
        self._measurement_scientific_metadata = [self._ncempy_datafile.getMetadata(d) for d in self._ncempy_datafile.list_data]

        # Parse dataset_name and measurement for the file 
        self.dataset_name = (self.dataset_name + " " if self.dataset_name else "") + os.path.basename(self.files_to_upload[0]) # append the filename to user-provided dataset_name
        self.measurement = self._ncempy_datafile.getMeasurementType()
        # prev: self.measurement = self._measurement_scientific_metadata[-1]['General']['groupType'] # last measurement's groupType options (in order): EDS_SI, Image (STEM or TEM), EDS_Spectrum

    def upload_dataset(self, ingestor='ApiUploadIngestor', verbose=False, wait_for_ingestion_response=True):
        upload_file = False # for testing purposes 
         
        get_groupType_from_md = lambda md: md['General']['groupType'] if 'groupType' in md['General'] else "" # options: STEM, TEM, EDS_Processed, EDS
        get_title_from_md = lambda md: md['General']['title'] if 'title' in  md['General'] else "" # options: EDS_SI, EDS_Spectrum, HAADF, element name

        def upload_measurement(md, parent_dsid): 
            """
            Uploads measurement dataset using measurment metadata MD. Links the created dataset record to PARENT_DSID.
            Returns measurement_dsid. 
            """
            # Create dataset
            measurement_ds = BaseDataset(
                # unique_id      = self.mfid, # need a new id for each measurement ds?
                measurement    = get_groupType_from_md(md), 
                project_id     = self.project_id,
                owner_orcid    = None,  # API key handles user authentication
                dataset_name   = self.dataset_name + f" ({get_title_from_md(md)})", # TODO: use metadata.title
                session_name   = self.session_name,
                public         = self.public,
                instrument_name = self.instrument_name, # TODO: include detector here? 
                data_format    = self.data_format,
                source_folder  = self.source_folder,
                # file_to_upload = self.files_to_upload[0] <- INCLUDE if upload_file
            )
        
            # Upload dataset to crucible: use create_new_dataset instead, if no file needed            
            if upload_file: 
                measurement_upload_result = self.client.create_new_dataset_from_files(
                    measurement_ds,
                    files_to_upload=self.files_to_upload,
                    scientific_metadata=md,
                    keywords=self.keywords,
                    ingestor=ingestor,
                    verbose=verbose,
                    wait_for_ingestion_response=wait_for_ingestion_response
                )
            else: 
                measurement_upload_result = self.client.create_new_dataset(
                    measurement_ds,
                    scientific_metadata=md,
                    keywords=self.keywords,
                    verbose=verbose
                )
            measurement_dsid = measurement_upload_result['created_record']['unique_id']

            # Link measurement dataset (child) with file dataset (parent)
            self.client.link_datasets(parent_dsid, measurement_dsid)
            return measurement_dsid

        # 1. upload the dataset for the entire file
        if upload_file: 
            file_upload_result = super().upload_dataset(ingestor, verbose, wait_for_ingestion_response)
        else: 
            file_upload_result = self.client.create_new_dataset(
                self.to_dataset(),
                scientific_metadata=self.scientific_metadata,
                keywords=self.keywords,
                verbose=verbose,
            )
        file_dsid = file_upload_result['created_record']['unique_id'] # if using create_new_dataset instead of create_new_dataset_from_files, can directly use 

        # 2. upload measurement datasets 
        spectrum_image_dsid = None

        # iterate backwards through groups to catch if spectrum image exists (then handle nested uploads)
        for i, md in enumerate(self._measurement_scientific_metadata[::-1]):
            # expect that spectrum image will be at the end of measurement_scientific_metadata if it exists  
            if i == 0 and get_groupType_from_md(md) == self._ncempy_datafile.SPECTRUM_IMAGE_GROUP_NAME:
                spectrum_image_dsid = upload_measurement(md, file_dsid) # spectrum image dsid
            else: 
                # ensure that processed images are nested properly (assume: processed image exists => spectrum_image exists)
                parent_dsid = spectrum_image_dsid if get_groupType_from_md(md) == self._ncempy_datafile.PROCESSED_IMAGE_GROUP_NAME else file_dsid
                upload_measurement(md, parent_dsid)
                
        return file_upload_result
    