# Dataset Model

| Field | Description | Settable |
|---|---|---|
| `dataset_name` | Human-readable name for the dataset | create, update |
| `project_id` | Project this dataset belongs to | create, update |
| `measurement` | Industry-standard experiment type (e.g. `"Raman Spectroscopy"`) | create, update |
| `data_type` | Institution-specific data organization descriptor (e.g. `"ScopeFoundry H5 file"`) | create, update |
| `instrument_name` | Name of the instrument as registered in Crucible | create, update |
| `data_format` | File type or extension (e.g. `"h5"`, `"dat"`) | create, update |
| `session_name` | Optional tag grouping datasets collected in the same session | create, update |
| `timestamp` | When the data was collected (ISO 8601 format) | create, update |
| `public` | Whether the dataset is publicly accessible (default: `False`) | create, update |
| `owner_orcid` | Dataset owner — defaults to the authenticated user | create, update |
| `unique_id` | System-assigned MFID identifier | server-assigned |
| `size` | Total file size in bytes | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |

### Relationships

| Relationship | Key(s) | Description |
|---|---|---|
| **Files** | `files_to_upload` in `create()`; `add_file_to_dataset(dsid, file_path)` to add later | Zero or more files can be attached to a dataset. Each file is uploaded to cloud storage and triggers an ingestion process to parse metadata and generate thumbnails. |
| **Scientific metadata** | `scientific_metadata` in `create()`; `metadata` in `add_scientific_metadata()` / `update_scientific_metadata()` | A free-form JSON object for experiment-specific parameters. Stored separately from structured fields and searchable across datasets. |
| **Thumbnails** | `add_thumbnail(dsid, image)` | Small preview images representing the data or results. Generated automatically by ingestors where supported, or uploaded manually. |
| **Samples** | `sample_id` in `add_sample(dataset_id, sample_id)` | A dataset can be linked to one or more samples, and a sample to one or more datasets — capturing which material was measured. |
| **Parent/child datasets** | `parent_dataset_id`, `child_dataset_id` in `link_parent_child()` | Datasets can be linked in a directed hierarchy to represent processing pipelines (e.g. raw → calibrated → analyzed). |

# Working with Datasets
## Creating a dataset

Pass a `Dataset` model and optional files to `client.datasets.create()`:

```python
from crucible.models import Dataset

result = client.datasets.create(
    dataset=Dataset(
        dataset_name="XRD run 5",
        measurement="X-ray diffraction",
        instrument_name="Beamline 12.3.2",
        project_id="my-project",
    ),
    files_to_upload=["xrd_run5.xy"],
    scientific_metadata={"wavelength_angstrom": 0.7749, "temperature_K": 300},
    keywords=["XRD", "powder"],
)

dsid = result["dsid"]
```

You can upload multiple files in one call:

```python
result = client.datasets.create(
    dataset=Dataset(dataset_name="Multi-file dataset", project_id="my-project"),
    files_to_upload=["file1.dat", "file2.dat", "thumbnail.png"],
)
```
!!! note "What happens when you call create()"
    `create()` is a client-side convenience method that chains several API calls:

    1. **POST** `/datasets` — creates the dataset record and returns a `dsid`
    2. **POST** `/resources/{dsid}/metadata` — adds scientific metadata (if provided)
    3. **POST** `/datasets/{dsid}/keywords` — adds each keyword individually (if provided)
    4. Uploads each file via GCS and triggers an ingestion request per file (if `files_to_upload` is provided)


## Retrieving a dataset

```python
ds = client.datasets.get("ds-abc123")
ds_with_metadata = client.datasets.get("ds-abc123", include_metadata=True, include_links=True)
```

## Listing datasets

```python
# All datasets in a project
datasets = client.datasets.list(project_id="my-project", limit=50)

# Filter by measurement type
datasets = client.datasets.list(project_id="my-project", measurement="SEM imaging")

# Filter by keyword
datasets = client.datasets.list(project_id="my-project", keywords=["gold"])

# Datasets linked to a specific sample
datasets = client.datasets.list(sample_id="sm-xyz789")
```

## Updating a dataset

```python
client.datasets.update(
    "ds-abc123",
    dataset_name="XRD run 5 (corrected)",
    measurement="Powder X-ray diffraction",
)
```

## Adding files to a dataset

Add files to an existing dataset:

```python
client.datasets.add_file_to_dataset("ds-abc123", "additional_file.dat")
```

### How the data ingestion process works

When a file is added to a dataset, three things happen:

1. The file is uploaded to cloud storage
2. A file record is created in the database linked to the dataset
3. An ingestion request is sent to the backend

Data type-specific ingestion classes parse scientific metadata, structured metadata, and thumbnails from the file. If an ingestion class is specified via the `ingestor` parameter, that class is used. Otherwise available classes are scanned from most to least specific, if there are no ingestion classes that support the data type, then metadata and thumbnails will not be extracted from the file.

Ingestors will not overwrite the dataset attributes provided at dataset creation. Structured metadata for the primary dataset record (eg. timestamp, dataset_name, data_type) can be updated using the `client.datasets.update()` method. 

For updates to the scientific metadata, the ingestion process uses the `client.datasets.update_scientific_metadata(overwrite = False)` method. As a result, new key-value pairs parsed during the ingestion process will be appended to the existing `scientific_metadata` and newly parsed values for existing keys will be updated. If you would like to replace the entire scientific_metadata dictionary, it can be done manally with `update_scientific_metadata(overwrite=True)`.

Files are deduplicated by sha256 hash. If you add the same file twice it will not be reuploaded, but ingestion will be re-requested — this operation is **idempotent**.

!!! warning
    If two files with the same name but different contents are added to the same dataset, the upload proceeds but **replaces the original file in cloud storage**. A new file record is created with a new `mfid` and hash; the old record remains but its download link points to the new file. We are actively working on updated logic to address this.

If no ingestion class exists for your data type, reach out on [Discord](https://discord.gg/Wrepphsgbx) or contribute to the [crucible-ingestion](https://github.com/MolecularFoundryCrucible/crucible-ingestion) repository.

## Scientific metadata

Scientific metadata stores experiment-specific parameters as a free-form JSON object.

```python
# Add or replace scientific metadata
client.datasets.add_scientific_metadata(
    "ds-abc123",
    metadata={"temperature_K": 300, "pressure_bar": 1.0, "scan_rate_mV_s": 50},
)

# Retrieve it
meta = client.datasets.get_scientific_metadata("ds-abc123")

# Search across all datasets
results = client.datasets.search_scientific_metadata("temperature", limit=20)
```

`add_scientific_metadata()` **replaces** all existing metadata (POST). To update selectively, use `update_scientific_metadata()`:

```python
# Merge new keys into existing metadata (PATCH — appends/updates individual keys)
client.datasets.update_scientific_metadata("ds-abc123", {"new_key": "value"})

# Replace all metadata entirely (POST)
client.datasets.update_scientific_metadata("ds-abc123", {"new_key": "value"}, overwrite=True)
```

## Keywords

```python
client.datasets.add_keyword("ds-abc123", "annealed")
keywords = client.datasets.get_keywords(dataset_id="ds-abc123")
```

## Thumbnails

```python
client.datasets.add_thumbnail("ds-abc123", "preview.png")
thumbnails = client.datasets.get_thumbnails("ds-abc123")
```

## Downloading

```python
# Download all files for a dataset
client.datasets.download("ds-abc123", output_dir="./downloads")

# Download only matching files
client.datasets.download("ds-abc123", output_dir="./downloads", include="*.dat")

# Get pre-signed download URLs (valid ~1 hour)
links = client.datasets.get_download_links("ds-abc123")
```

## Parent-child relationships between datasets

Link datasets to represent a processing pipeline:

```python
# raw → processed
client.datasets.link_parent_child(parent_id=raw_dsid, child_id=processed_dsid)

# List relationships
parents = client.datasets.list_parents("ds-processed")
children = client.datasets.list_children("ds-raw")
```

## Deleting a dataset

```python
client.datasets.delete("ds-abc123")
```

!!! note
    Calling `delete()` submits a deletion request — it does not immediately remove the resource. An admin must approve the request before the dataset is deleted.


