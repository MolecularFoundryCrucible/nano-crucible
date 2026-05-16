# Core Concepts

Crucible organizes scientific data around four types of objects. Understanding how they relate makes it easier to structure your data.

---

## Users
Users can be people or service accounts with access to Crucible. Users can be members of access groups and projects. To create a user profile, an ORCID account is required.  Crucible API keys are required for working with the Crucible API locally.  API keys can be generated at https://crucible.lbl.gov/api/v2/user_apikey.  

If your integration requires a service account with elevated privileges, please join the discord and submit a request for a service account. 


## Projects

A **project** is the top-level organizational unit. Projects commonly map to research projects or user facility proposals.

Projects serve two primary purposes:

1. **Organization** — datasets and samples belong to a project, making them easier to find and filter.
2. **Access control** — all members of a project can read the datasets and samples within it. Adding a user to a project grants them access to all associated data.

Every dataset and sample must belong to a project. The `project_id` is a short, human-readable identifier chosen at creation time (e.g., `MFP12345`).

[Project model →](models/project.md) | [Project management guide →](user-guide/projects.md)

---

## Datasets

A **dataset** is the core data object in Crucible. It can combine:

- **Files** — the actual measurement data (optional; a dataset record can exist simply as a set of structured and unstructured metadata without any attached files). 
- **Structured metadata** — measurement (industry standard terminology that reflects the scientific intention of the experiment performed, eg. Raman Spectroscopy), data_type (institutionally specific terminology that reflects the expected organization of the collected data to inform how it can be used downstream, eg. ScopeFoundry H5 file), instrument (corresponds to the name of the instrument used to collect/generated the data as it exists in the Crucible data platform), session_name (optional name used to tag datasets that are contextualized by being collected as part of the same session), timestamp (the time/date when the data was collected in isoformat), data_format (generally the file type or extension, eg. h5). Other information about the dataset such as creation_time, modification_time, and download path will be generated and recorded on the server side. 
- **Scientific metadata** — free-form key-value pairs for experiment-specific parameters, notes, and comments that are considered necessary for reproducibility and provenance. The structure is intentionally flexible to accommodate a variety of use cases and reduce input burden for experimentalists as well as allow adaptibility over time. However, it is recommended to standardize the structure of the scientific data for specific data types within a project or organization to promote higher quality data curation and enable downstream analytics. 
- **Keywords** — searchable tags associated with each dataset
- **Thumbnails** - Small, low resolution images to represent the results or underlying data in the dataset. 


Datasets can be linked to each other in parent-child relationships to represent processing pipelines (e.g., raw data → calibrated → analyzed) or collections of related data.

[Working with datasets →](user-guide/datasets.md)

## Files
# todo - is this the right spot for this info and should we reformat it / should we split ingestion requests to their own category
Files records in the database reflect the file objects associated with the dataset. Files may not exist independent of a dataset record. Zero or more files may be added to a dataset. When a file is added to a dataset, several events occur. 1. The file is uploaded to a cloud storage location 2. A SQL record for the file is created with a relationship to the dataset record. 3. An ingestion request is sent to the backend server. 

Data type specific ingestion classes exist to parse scientific metadata and/or structured metadata from the files and generate thumbnails from the data. If an ingestion class is specified at the time a file is added to the dataset, that ingestion class will be used to parse the file. If no ingestion class is specified, the available ingestion classes will be scanned (from most to least specific) to determine if there is an ingestion class is available that supports the provided file type. If no ingestor is found then no metadata or thumbnails will be parsed from the file. 

Different ingestors will apply custom logic to update dataset records, but existing information will not be overwritten by an ingestor.  If a user provides dataset attributes during the dataset creation, these values will persist regardless of the ingestion processes requested by adding files to the dataset. Ingestion processes will append newly parsed key,value pairs to the scientific metadata dictionary, but will update values for existing keys if a new parsed value is found. Users may update the dataset record using the python client or CLI if they wish to overwrite existing attributes. Additionally, the client can be used to update or replace the scientific_metadata dictionary. 

Files are guaranteed to be unique within a dataset based on their sha256_hash identity. If a user adds a file to a dataset twice and the hash has not changed, the file will not be reuploaded and a duplicate record will not be created. The ingestion will be re-requested to ensure that the metadata is successfully parsed. #TODO - is this idempotency

Currently, if two files with the same file path/name but different sha256 hashes are added to the same dataset, the upload will proceed but **replace the original file in cloud storage**. A new associated file record will be created with a unique mfid and the newly calculated sha256 hash. The previous associated record will still exist, but the storage path and download link will point to the new file.  **We are actively working on an updated logic to address this.** 

If an ingestion class does not exist for your data types, please reach out on our discord channel or consider contributing to our open source crucible-ingestion repository!

---

## Samples

A **sample** represents a physical or computational material that data was collected from. Samples are useful for tracking provenance: which datasets were measured from which material, and how that material was prepared.

Like datasets, samples support parent-child hierarchies. A bulk crystal, a cleaved wafer cut from it, and a thin film deposited on the wafer can all be modeled as a parent-child sample chain.

A dataset can be linked to one or more samples, and a sample can be linked to one or more datasets.

[Working with samples →](user-guide/samples.md)

---

## Instruments

An **instrument** represents the physical equipment from which a dataset originated. Linking a dataset to an instrument (via `instrument_name`) provides a consistent way to filter and search data by the equipment that produced it.

Instruments are shared across projects and exist independently of any single project. However, each distinct physical instrument should have its own entry.

If an instrument already exists in Crucible, reference it by name in your datasets. If not, create it first with `client.instruments.create()` — the method returns the existing record if one with that name already exists.

[Instrument model →](models/instrument.md)

---

## IDs

Every object in Crucible has a system-assigned `unique_id` generated by the [`mfid`](https://pypi.org/project/mfid/) package. The `unique_id` is the stable identifier you use to retrieve, update, link, and download dataset, sample, instrument, and associated file objects.
