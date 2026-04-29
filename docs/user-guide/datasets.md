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

## Uploading additional files

Add files to an existing dataset:

```python
client.datasets.upload_file("ds-abc123", "additional_file.dat")
client.datasets.add_associated_file("ds-abc123", "notes.pdf")
```

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
