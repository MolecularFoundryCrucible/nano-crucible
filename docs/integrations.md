# Crucible Instrument Integrations


##  Evaluating Instrument Complexity / Compatibility
- Is internet access available?
- How are files saved, organized, and accessed?
- What data types does the instrument produce?
- For each data type what scientific metadata should be captured and where is that information currently stored? 
- What ingestion classes currently exist that support your workflows? 

## Existing User Interfaces
### Web Explorer - generic web based input forms to create samples or datasets
 << coming soon >>

### Sample Creators - custom web based apps to add samples with specific metadata structures or anticipated relationship trees
 Explore: https://crucible.lbl.gov/sample-creators
 Contribute: https://github.com/MolecularFoundryCrucible/sample-creators
 Request: Contact us on Discord (#TODO - link)!

## Crucible Upload UI - Locally deployable UI for uploading folders of data or individual files and printing QR code labels.
 This repository was originally developed specifically for TEM session data. Feel free to download as is or fork and customize to your instrument needs! PRs welcomed. 

 Github: https://github.com/MolecularFoundryCrucible/crucible-tem-upload-ui

## A couple notes about metadata parsing and uploading
We have intentionally developed the scientific metadata field to be flexible and undefined with many routes to entry.  This is an attempt to meet the needs of a wide variety of users.  As a result it may seem unclear what is the best way to annotate your datasets.  Here are some common usage patterns that are not comprehensive but may be helpful: 

    1.  Metadata is available in instrument logs or output files **with an ingestion class available**
        - Pass the files to `client.datasets.create()` as files to upload. Each file will be added to the dataset and the ingestion process will update with parsed metadata and thumbnails where relevant. 
        - Use the client to `add_file_to_dataset` for each file you want to add, loosens the constraint that files need to be known and present at the time of dataset creation - ingestion process parses the metadata and updates the dataset
    2. Metadata is available in output files but no ingestion class supports the data type
        - Develop or Request an ingestion class for your data type (# todo: Github (link), Discord (link))
        - Parse the files locally and upload parsed information as json using the python client. Use the client to `add_file_to_dataset`. 
    3. Metadata is not captured in output files from the instrument
        - Create forms, Jupyter notebooks, or UI's to capure this information and upload via the API during dataset creation or using `client.datasets.update()`
        - Take pictures of lab notebooks, handwritten notes, or experimental set up and upload as associated files. Currently these will not be parsed into json dictionaries, but it is possible to envision that future! 

 