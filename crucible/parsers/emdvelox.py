#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EMD Parser

Created on Wed Feb 25 2026
"""

import os
import logging
from .base import BaseParser

import matplotlib.pyplot as plt
from ncempy.io import emdVelox
from crucible import BaseDataset

logger = logging.getLogger(__name__)

get_groupType_from_md = lambda md: md['General']['groupType'] if 'groupType' in md['General'] else "" # options: STEM, TEM, EDS_Processed, EDS
get_title_from_md = lambda md: md['General']['title'] if 'title' in  md['General'] else "" # options: EDS_SI, EDS_Spectrum, HAADF, element name

def getMeasurementType(ncempy_emd_file, index=-1):
    """
    Args:
    - index: which item of list_data to consider (default: consider last item)

    Returns: 
    - measurement type of this file for crucible data ingestion 
    """
    measurement_type = ncempy_emd_file.list_data[index].parent.name[6:]
    if measurement_type == 'Spectrum': 
        measurement_type = ncempy_emd_file.SPECTRUM_GROUP_NAME
    elif measurement_type == 'SpectrumImage': 
        measurement_type = ncempy_emd_file.SPECTRUM_IMAGE_GROUP_NAME
    return measurement_type 

def get_illumination_mode(metadata_dictionary): 
    """
    Identify the illumination mode for the measurement/child dataset 
    corresponding to to METADATA_DICTIONARY.

    Currently, Spectre specific logic. 

    Args: 
    - metadata_dictionary: dict 

    Returns: 
    - illumination: str (defaults to '[IlluminationMode]' no case matched)
    """
    # handle errors/edge cases
    illumination = '[IlluminationMode]' # placeholder 
    if 'OperatingMode' not in metadata_dictionary: 
        return illumination
    
    data_illumination = int(metadata_dictionary['OperatingMode'])
    if data_illumination == 1:
        illumination = 'TEM'
    elif data_illumination == 2:
        illumination = 'STEM'
    return illumination

def get_projection_mode(metadata_dictionary): 
    """
    Identify the projection mode for the measurement/child dataset 
    corresponding to to METADATA_DICTIONARY.

    Currently, Spectre specific logic. 

    Args: 
    - metadata_dictionary: dict 

    Returns: 
    - projection: str (defaults to '[ProjectorMode]' no case matched) 
    """
    # handle errors/edge cases
    projection = '[ProjectorMode]' # placeholder 
    if 'ProjectorMode' not in metadata_dictionary: 
        return projection

    data_proj = int(metadata_dictionary['ProjectorMode'])
    if data_proj == 1:
        projection = 'Diffraction'
    elif data_proj == 2:
        projection = 'Imaging'
    return projection

def get_signal_type(metadata_dictionary):
    """
    Identify the projection mode for the measurement/child dataset 
    corresponding to to METADATA_DICTIONARY.

    Currently, Spectre specific logic. 

    Args: 
    - metadata_dictionary: dict 

    Returns: 
    - signal: str or None (defaults to None if no case matched) 
    """
    # handle errors/edge cases
    signal = None 
    if 'DetectorIndex' not in metadata_dictionary: 
        return None # want measurement = 'Velox Processed Image'
    
    detector_indx = int(metadata_dictionary['DetectorIndex'])
    if detector_indx in [1, 3, 4, 5]:
        signal = 'Pixelated'
    elif detector_indx in [0, 2, 6]:
        signal = 'Non-Pixelated'
    elif detector_indx in [7, 8, 9, 10, 11, 12]:
        signal = 'EDS'
    return signal

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

        self.thumbnail = self._create_thumbnail_for_parent()

        # Parse metadata for measurments 
        self._measurement_scientific_metadata = self._parse_measurement_metadata() # requires ._create_thumbnail_for_parent() to run first 
        # previously: self._measurement_scientific_metadata = [self._ncempy_datafile.getMetadata(d) for d in self._ncempy_datafile.list_data] 

        # Parse dataset_name and measurement for the file 
        input_file_basename = os.path.basename(self.files_to_upload[0])
        self.dataset_name = (self.dataset_name + " " if self.dataset_name else "") + input_file_basename # append the filename to user-provided dataset_name
        self.measurement = self._measurement_scientific_metadata[-1]['measurement'] # TODO: update parse_parent_measurement
        # self.measurement = getMeasurementType(self._ncempy_datafile)
        # prev: self.measurement = self._measurement_scientific_metadata[-1]['General']['groupType'] # last measurement's groupType options (in order): EDS_SI, Image (STEM or TEM), EDS_Spectrum

    def _parse_measurement_metadata(self): 
        """
        Parses scientific metadata for measurement, including creating thumbnails for measurements.
        Adds thumbnails for each measurement group in "thumbnail" member of the metadata dict. 
        Requires self._create_thumbnail_for_parent() to run first, so that self.thumbnail is updated 

        Note: next step: explicitly ensure that spectrum image has the same thumbnail as the HAADF image, not a processed image
        """
        file_basename = os.path.splitext(os.path.basename(self.files_to_upload[0]))[0] # with no file extension

        measurement_metadata = []
        for i, measurement in enumerate(self._ncempy_datafile.list_data): 
            md = self._ncempy_datafile.getMetadata(measurement)

            # add thumbnail for this measurement 
            measurement_type = measurement.parent.name[6:]
            thumbnail_name = file_basename + str(i) + ".png" 
            if measurement_type == 'Image': 
                self._create_thumbnail(measurement, thumbnail_name)
            elif measurement_type == 'SpectrumImage': 
                # use same thumbnail as main file dataset
                thumbnail_name = self.thumbnail
            md.update({"thumbnail": thumbnail_name})

            # parse measurement_type for this measurement
            illumination = get_illumination_mode(md)
            projection = get_projection_mode(md)
            signal = get_signal_type(md) if measurement_type != 'SpectrumImage' else 'EDS' # handle spectrum images separately? 
            if signal == None: 
                measurement = 'Velox Processed Image'
            else: 
                measurement = illumination + ' ' + projection + ' ' + signal
            md.update({"measurement": measurement})

            measurement_metadata.append(md)

        return measurement_metadata

    def _create_thumbnail_for_parent(self):
        """
        Creates a thumbnail using the first slice of the last image in file. 
        Return thumbnail filepath (str) or None if no images in the dataset.
        """
        if '/Data/Image' not in self._ncempy_datafile._file_hdl: 
            return None

        file_basename = os.path.splitext(os.path.basename(self.files_to_upload[0]))[0] # with no file extension
        thumbnail_name = file_basename + ".png" 

        # choose the image from which to create a thumbnail
        image_dataset = None
        # iterate through image datasets to find a non-processed image 
        all_image_groups = list(self._ncempy_datafile._file_hdl['/Data/Image'].values())
        for group in all_image_groups[::-1]:  # start from the back, assuming that processed images are at the front
            md = self._ncempy_datafile.getMetadata(group)
            if get_groupType_from_md(md) != self._ncempy_datafile.PROCESSED_IMAGE_GROUP_NAME: 
                image_dataset = group 
                break 
        # if all images are processed images, use an arbitrary processed image
        if image_dataset == None: 
            image_dataset = all_image_groups[0]
        
        self._create_thumbnail(image_dataset, thumbnail_name)
        return thumbnail_name

    def _create_thumbnail(self, image_dataset, thumbnail_name):
        """
        Creates a thumbnail titled THUMBNAIL_NAME from IMAGE_DATASET 
        IMAGE_DATASET: a h5py.File
        thumbnail_name: string, ending in .png 
        """
        image_2d_array = image_dataset['Data'][:,:,0]
        plt.imshow(image_2d_array, cmap='gray')
        plt.savefig(thumbnail_name, bbox_inches='tight')

    def upload_dataset(self, ingestor='ApiUploadIngestor', verbose=False, wait_for_ingestion_response=True):
        upload_file = False # for testing purposes 
        measurement_dsids = []

        def upload_measurement(md, parent_dsid): 
            """
            Uploads measurement dataset using measurment metadata MD. Links the created dataset record to PARENT_DSID.
            Returns measurement_dsid. 
            """
            # Create dataset
            measurement_ds = BaseDataset(
                # unique_id      = self.mfid, # need a new id for each measurement ds?
                measurement    = md['measurement'], # prev: get_groupType_from_md(md), 
                project_id     = self.project_id,
                owner_orcid    = None,  # API key handles user authentication
                dataset_name   = self.dataset_name + f" ({get_title_from_md(md)})",
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
        
        def upload_file_dataset(): 
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
            return file_upload_result
        
        if len(self._measurement_scientific_metadata) == 1: 
            # include single measurement md in the main file dataset's md
            self.scientific_metadata.update(self._measurement_scientific_metadata[0]) 

        file_upload_result = upload_file_dataset()
        file_dsid = file_upload_result['created_record']['unique_id'] # if using create_new_dataset instead of create_new_dataset_from_files, can directly use 
        measurement_dsids.append(file_dsid) # REMOVE LATER when upload_file is true, i.e. using super().upload_dataset() should handle it 
        self.client.add_thumbnail(file_dsid, self.thumbnail) # TODO: EDIT THIS 

        # don't upload a separate measurement dataset if there's only 1 measurement
        if len(self._measurement_scientific_metadata) == 1: 
            return file_upload_result
        
        # 2. upload measurement datasets 
        spectrum_image_dsid = None

        # iterate backwards through groups to catch if spectrum image exists (then handle nested uploads)
        for i, md in enumerate(self._measurement_scientific_metadata[::-1]):
            # ensure that processed images are nested properly (assume: processed image exists => spectrum_image exists)
            parent_dsid = spectrum_image_dsid if (get_groupType_from_md(md) == self._ncempy_datafile.PROCESSED_IMAGE_GROUP_NAME and spectrum_image_dsid != None) else file_dsid 
            dsid = upload_measurement(md, parent_dsid)

            # add thumbnail for this measurement (if applicable)
            measurement_dsids.append(dsid) # if using the line below, can remove measurement_dsids
            if "thumbnail" in md: 
                self.client.add_thumbnail(dsid, md["thumbnail"]) 

            # assume that spectrum will always be at the end of list_data if it exists; therefore, we only update spectrum_image_dsid in the first iteration 
            if i == 0 and get_groupType_from_md(md) == self._ncempy_datafile.SPECTRUM_IMAGE_GROUP_NAME:
                spectrum_image_dsid = dsid

        # 3. add thumbnails to all new datasets (including file_dsid if not handed earlier)
        # for dsid in measurement_dsids: 
        #     self.client.add_thumbnail(dsid, self.thumbnail)
                
        return file_upload_result
    