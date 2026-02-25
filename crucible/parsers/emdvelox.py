from .base import BaseParser
import os
from ncempy.io import emdVelox # ncempy module
from crucible import BaseDataset

class EMDVeloxParser(BaseParser):
    def parse(self):
        # Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Use first file as EMD input
        input_file = os.path.abspath(self.files_to_upload[0])

        # Read input file using ncempy 
        ncempy_datafile = emdVelox.fileEMDVelox(input_file)

        # custom attribute: measurement_scientific_metadata
        self.measurement_scientific_metadata = [ncempy_datafile.getMetadata(d) for d in ncempy_datafile.list_data]

    def upload_dataset(self, ingestor='ApiUploadIngestor', verbose=False, wait_for_ingestion_response=True):
        # upload the dataset for the entire file 
        results = [super().upload_dataset(self, ingestor, verbose, wait_for_ingestion_response)]

        # create & upload the dataset for each measurement
        detectors = [d['Detector'] for d in self.measurement_scientific_metadata] # get list of detectors
        measurement_datasets = [BaseDataset(
            unique_id      = self.mfid,
            measurement    = self.measurement,
            project_id     = self.project_id,
            owner_orcid    = None,  # API key handles user authentication
            dataset_name   = self.dataset_name,
            session_name   = self.session_name,
            public         = self.public,
            instrument_name = detector,
            data_format    = self.data_format,
            source_folder  = self.source_folder,
            file_to_upload = self.files_to_upload[0]
        ) for detector in detectors]

        # upload measurements to crucible
        results.append([self.client.create_new_dataset_from_files(
            measurement_datasets[i],
            files_to_upload=self.files_to_upload,
            scientific_metadata=self.measurement_scientific_metadata[i],
            keywords=self.keywords,
            # get_user_info_function=self.client.get_user,
            ingestor=ingestor,
            verbose=verbose,
            wait_for_ingestion_response=wait_for_ingestion_response
        ) for i in range(len(measurement_datasets))])

        return results