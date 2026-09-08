# Dataset Model

| Field | Description | Settable |
|---|---|---|
| `dataset_name` | Human-readable name for the dataset | create, update |
| `project_id` | Project this dataset belongs to | create; later changes use `reassign_project()` |
| `project_mfid` | Canonical project selector for creation | create |
| `measurement` | Industry-standard experiment type (e.g. `"Raman Spectroscopy"`) | create, update |
| `data_type` | Institution-specific data organization descriptor (e.g. `"ScopeFoundry H5 file"`) | create, update |
| `instrument_name` | Name of the instrument as registered in Crucible | create |
| `instrument_id` | Instrument identifier | create |
| `instrument_mfid` | Canonical registered instrument selector for creation | create |
| `instrument` | Current instrument identity and display fields, including its canonical MFID | server-assigned |
| `project` | Current project identity and display fields, including its canonical MFID | server-assigned |
| `data_format` | File type or extension (e.g. `"h5"`, `"dat"`) | create, update |
| `session_name` | Optional tag grouping datasets collected in the same session | create, update |
| `timestamp` | When the data was collected (ISO 8601 format) | create, update |
| `public` | Whether the dataset is publicly accessible (default: `False`) | create, update |
| `owner_orcid` | Canonical owner identifier returned by the API; deprecated as a creation input | read; deprecated for create |
| `owner` | Flexible owner identifier on create; public-safe user record on singleton reads | create with an ORCID, MFID, username, or email; expanded by default on `get()` |
| `unique_id` | System-assigned MFID identifier | server-assigned |
| `size` | Total file size in bytes | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |
| `capabilities` | Optional caller-specific actions calculated for an exact response | server-assigned |

Instrument assignment is fixed at creation for now. Generic dataset updates may resubmit the current `instrument_id` or `instrument_name` for compatibility, but changing or clearing either value returns HTTP 409 until a dedicated reassignment operation is available.

List datasets assigned to a canonical instrument across every project visible to the caller with:

```python
datasets = client.datasets.list(instrument_mfid="0tkn2knjast3h0008nyq9zps2c")
```

The equivalent CLI command is `crucible dataset list --instrument-mfid 0tkn2knjast3h0008nyq9zps2c`. Supplying this explicit filter does not apply the saved current project, while combining it with `--project-id` intentionally narrows the results to that project. Legacy datasets without a canonical instrument MFID are not included.

### Relationships

| Relationship | Key(s) | Description |
|---|---|---|
| **Files** | `files` in `create()`; `add_file(dataset_mfid, file_path)` to add later | Zero or more files can be attached to a dataset. Each file is uploaded to cloud storage and triggers an ingestion process to parse metadata and generate thumbnails. |
| **Scientific metadata** | `scientific_metadata` in `create()`; `metadata` in `update_scientific_metadata()` / `replace_scientific_metadata()` | A free-form JSON object for experiment-specific parameters. Stored separately from structured fields and searchable across datasets. |
| **Thumbnails** | `add_thumbnail(dataset_mfid, image)` | Small preview images representing the data or results. Generated automatically by ingestors where supported, or uploaded manually. |
| **Samples** | `sample_mfid` in `link_sample(dataset_mfid, sample_mfid)` | A dataset can be linked to one or more samples, and a sample to one or more datasets, capturing which material was measured. |
| **Parent/child datasets** | `parent_mfid`, `child_mfid` in `link()` | Datasets can be linked in a directed hierarchy to represent processing pipelines, such as raw to calibrated to analyzed. |

# Working with Datasets
## Creating a dataset

Dataset records and associated files are separate API resources. Create the dataset record first, then add files using its returned MFID:

```python
from crucible.models import Dataset

result = client.datasets.create(
    dataset=Dataset(
        dataset_name="XRD run 5",
        measurement="X-ray diffraction",
        instrument_name="Beamline 12.3.2",
        project_id="my-project",
    ),
    scientific_metadata={"wavelength_angstrom": 0.7749, "temperature_K": 300},
    keywords=["XRD", "powder"],
)

dataset_mfid = result["dataset_mfid"]
client.datasets.add_file(dataset_mfid, "xrd_run5.xy")
```

Applications may use canonical MFIDs instead of human-readable IDs. The API also accepts both forms when they resolve to the same resource:

```python
dataset = Dataset(
    dataset_name="XRD run 5",
    project_id="my-project",
    project_mfid="0tkn2knjast3h0008nyq9zps2c",
    instrument_id="beamline-123",
    instrument_mfid="0tk8pf1me0h3h0003fp91vr037",
)
```

Conflicting ID and MFID selectors produce an API validation error. Nano forwards the supplied selectors without resolving one into the other.

Files are optional. The CLI can create a record that receives its files later:

```bash
crucible dataset create --project-id my-project --name "Planned experiment"
crucible dataset add-file DATASET_MFID -i results.dat
```

The CLI defaults to human-readable `--project-id` and `--instrument-id` selectors. Integrations can use `--project-mfid` and `--instrument-mfid`; matching ID and MFID flags may be combined.

For convenience, `create()` can perform these operations in sequence when `files` is supplied. Files are not part of the API dataset-creation request, and a failure while adding one does not roll back the created dataset record:

```python
result = client.datasets.create(
    dataset=Dataset(dataset_name="Multi-file dataset", project_id="my-project"),
    files=["file1.dat", "file2.dat", "thumbnail.png"],
)
```
!!! note "What happens when you call create()"
    `create()` is a client-side convenience method that chains several API calls:

    1. **POST** `/datasets` creates the dataset record and returns its `unique_id` MFID.
    2. **POST** `/resources/{dataset_mfid}/metadata` adds scientific metadata when provided.
    3. **POST** `/datasets/{dataset_mfid}/keywords` adds each keyword individually when provided.
    4. Adds each file through the associated-file and upload routes and triggers an ingestion request per file when `files` is provided


## Retrieving a dataset

```python
ds = client.datasets.get("0tkn2knjast3h0008nyq9zps2c")
ds_with_details = client.datasets.get(
    "0tkn2knjast3h0008nyq9zps2c",
    include_metadata=True,
    include_links=True,
)
```

Datasets are retrieved only by their canonical 26-character MFID. Dataset names are display values, not identifiers.

Singleton retrieval expands `owner` by default as a public-safe user record containing `unique_id`, `username`, `first_name`, and `last_name`. Pass `include_owner=False` to suppress expansion. List operations remain opt-in with `include_owner=True`. The canonical owner identifier remains available as `owner_orcid`.

Canonical detail responses include caller-specific `capabilities` when the server has calculated them. Dataset capabilities always report `can_change_status=False` because datasets have no lifecycle-status operation. Collections and search results normally return `capabilities=None`, which means the guidance was not calculated rather than that every action is denied. The API remains authoritative for each mutation.

Dataset responses include lightweight `instrument` and `project` references when those canonical relationships resolve. Use `dataset["instrument"]["unique_id"]` and `dataset["project"]["unique_id"]` for stable navigation. The flat `instrument_id`, `instrument_name`, and `project_id` fields remain available and provide display fallbacks for legacy records whose canonical relationship is unresolved. A reference exposes identity and display information only and does not imply access to the complete instrument or project.

## Listing datasets

```python
# All datasets in a project
datasets = client.datasets.list(project_id="my-project", limit=50)

# Datasets shared with a project but assigned elsewhere or unassigned
shared = client.datasets.list(project_id="my-project", project_scope="shared")

# Assigned and shared datasets using the project's canonical MFID
visible = client.datasets.list(
    project_mfid="0tkn2knjast3h0008nyq9zps2c",
    project_scope="all",
)

# Filter by measurement type
datasets = client.datasets.list(project_id="my-project", measurement="SEM imaging")

# Filter by keyword
datasets = client.datasets.list(project_id="my-project", keyword="gold")

# Datasets linked to a specific sample
datasets = client.datasets.list(sample_mfid="0td7evvtg5wb90005k1j97ak94")

# Datasets readable by both users and directly accessible to a project
datasets = client.datasets.list(
    accessible_to_user=["alice", "bob"],
    accessible_to_project="my-project",
)
```

Pass the project slug as `project_id` or the canonical project MFID as `project_mfid`. Both may be supplied when they identify the same project; conflicting identifiers produce an API validation error. `project_scope` accepts `assigned`, `shared`, or `all` and defaults to `assigned`. Scoped collection results expose `project_relation` as `assigned` or `shared`; `project` may be `None` when a shared resource has no primary project.

The `sample_mfid` relationship filter uses the normal paginated dataset collection and can be combined with compatible dataset filters such as project, instrument, and access selectors. Results follow cursor pagination and include only datasets the caller may read.

Access selectors accept user MFIDs, ORCIDs, usernames, or emails and project MFIDs or project IDs. Multiple selectors use intersection semantics and only narrow resources the authenticated caller may read. Inspecting another user requires platform-administrator access, while inspecting a project requires membership in that project or platform-administrator access.

## Updating a dataset

```python
client.datasets.update(
    "0tkn2knjast3h0008nyq9zps2c",
    dataset_name="XRD run 5 (corrected)",
    measurement="Powder X-ray diffraction",
)
```

Project and ownership changes use preview-first workflows. Pass `confirm=True` only after reviewing the preview:

```python
project_preview = client.datasets.reassign_project(dataset_mfid, "new-project")
client.datasets.reassign_project(dataset_mfid, "new-project", confirm=True)

owner_preview = client.datasets.transfer_ownership(dataset_mfid, "new-owner@example.org")
client.datasets.transfer_ownership(dataset_mfid, "new-owner@example.org", confirm=True)
```

## Managing access

```python
grants = client.datasets.list_access(dataset_mfid)
client.datasets.set_access(dataset_mfid, "users", "0000-0002-1825-0097", "editor")
client.datasets.revoke_access(dataset_mfid, "users", "0000-0002-1825-0097")
client.datasets.publish(dataset_mfid)
client.datasets.unpublish(dataset_mfid)
```

Normal access grants accept `viewer`, `contributor`, `editor`, or `admin`. Use `transfer_ownership()` for ownership.

## Adding files to a dataset

Add files to an existing dataset:

```python
client.datasets.add_file(dataset_mfid, "additional_file.dat")
```

To discover files recursively, build the list locally and add each file to the existing dataset. Crucible stores the filename, not its relative directory hierarchy, so verify that basenames are unique before uploading:

```python
from collections import Counter
from pathlib import Path

source_root = Path("experiment-output")
source_files = sorted(path for path in source_root.rglob("*") if path.is_file())
duplicate_names = [name for name, count in Counter(path.name for path in source_files).items() if count > 1]
if duplicate_names:
    raise ValueError(f"Duplicate filenames in source tree: {duplicate_names}")

for path in source_files:
    client.datasets.add_file(dataset_mfid, str(path))
```

### Replacing a file

File replacement is an explicit delete-and-create workflow. Find the old associated-file MFID, delete that file, and then add the replacement to the dataset:

```python
associated_files = client.datasets.list_files(dataset_mfid)
old_file = next(file for file in associated_files if file["filename"] == "results.dat")

client.files.delete(old_file["mfid"])
client.datasets.add_file(dataset_mfid, "results.dat")
```

Deleting a file is irreversible. Verify the dataset MFID, file MFID, and filename before calling `delete()`.

The CLI follows the same sequence and asks for confirmation before deleting the old file:

```bash
crucible dataset list-files DATASET_MFID
crucible file delete FILE_MFID
crucible dataset add-file DATASET_MFID -i results.dat
```

### Re-uploading to an existing dataset

Keep the dataset MFID and add the local files to that record again. Do not call `datasets.create()` again, because that creates another dataset record:

```python
for path in source_files:
    client.datasets.add_file(dataset_mfid, str(path))
```

An unchanged file that the API recognizes by its SHA-256 hash is not uploaded again. If a filename now represents different content, use the explicit delete-and-create workflow above.

### How the data ingestion process works

When a file is added to a dataset, three things happen:

1. The file is uploaded to cloud storage
2. A file record is created in the database linked to the dataset
3. An ingestion request is sent to the backend

Data type-specific ingestion classes parse scientific metadata, structured metadata, and thumbnails from the file. If an ingestion class is specified via the `ingestor` parameter, that class is used. Otherwise available classes are scanned from most to least specific, if there are no ingestion classes that support the data type, then metadata and thumbnails will not be extracted from the file.

Ingestors will not overwrite the dataset attributes provided at dataset creation. Structured metadata for the primary dataset record (eg. timestamp, dataset_name, data_type) can be updated using the `client.datasets.update()` method. 

For updates to the scientific metadata, the ingestion process uses the `client.datasets.update_scientific_metadata(overwrite = False)` method. As a result, new key-value pairs parsed during the ingestion process will be appended to the existing `scientific_metadata` and newly parsed values for existing keys will be updated. If you would like to replace the entire scientific_metadata dictionary, it can be done manally with `update_scientific_metadata(overwrite=True)`.

Files are deduplicated by SHA-256 hash. If you add the same file twice, the client returns the existing associated-file record without uploading or requesting ingestion again.

If no ingestion class exists for your data type, reach out on [Discord](https://discord.gg/Wrepphsgbx) or contribute to the [crucible-ingestion](https://github.com/MolecularFoundryCrucible/crucible-ingestion) repository.

## Remote (non-GCS) files

Sometimes a file isn't worth (or isn't possible to) upload to GCS - it lives on Globus, at an HPC center, or on a shared filesystem. Crucible can still catalog it: it records where the file lives, but never verifies it exists, uploads it, or fetches it on your behalf.

```python
from crucible.models import AssociatedFile

client.datasets.add_remote_file(dataset_mfid, AssociatedFile(
    filename="raw_data.tar",
    storage_backend="globus",
    storage_path="https://app.globus.org/file-manager?origin_id=...&origin_path=...",
    access_note="request access via NERSC allocation X",
))
```

`storage_path` is optional - catalog the file now and set its location later with `client.files.update(mfid, storage_path=...)`.

You can also mix remote and uploaded files in one `create()` call:

```python
result = client.datasets.create(
    dataset=Dataset(dataset_name="Mixed dataset", project_id="my-project"),
    files=[
        "local_results.csv",                                     # uploaded to GCS
        AssociatedFile(filename="raw.tar", storage_backend="globus",
                       storage_path="https://app.globus.org/..."),  # cataloged only
    ],
)
```

A plain local path with `upload_files=False` is cataloged too, using its resolved absolute path and `storage_backend="local"`:

```python
result = client.datasets.create(
    dataset=Dataset(dataset_name="Cataloged only", project_id="my-project"),
    files=["/mnt/lustre/big_simulation_output.h5"],
    upload_files=False,
)
```

Downloading and ingestion are GCS-only: `client.files.download()`/`client.datasets.download()` skip non-GCS files (logging why), and the server rejects ingestion requests for them. Check `storage_backend` before assuming a file is fetchable - `crucible file get MFID` and `crucible dataset list-files` both show the backend name for non-GCS files instead of an "ingested" status.

## Scientific metadata

Scientific metadata stores experiment-specific parameters as a free-form JSON object.

```python
# Merge new keys into existing metadata (PATCH - appends/updates individual keys)
client.datasets.update_scientific_metadata(
    dataset_mfid,
    metadata={"temperature_K": 300, "pressure_bar": 1.0, "scan_rate_mV_s": 50},
)

# Retrieve it
meta = client.datasets.get_scientific_metadata(dataset_mfid)

# Search across all datasets
results = client.datasets.search_scientific_metadata("temperature", limit=20)
```

`update_scientific_metadata()` merges new keys into the existing metadata (PATCH). To replace all existing metadata entirely, use `replace_scientific_metadata()`:

```python
# Replace all metadata entirely (POST)
client.datasets.replace_scientific_metadata(dataset_mfid, {"new_key": "value"})
```

## Keywords

```python
client.datasets.add_keyword(dataset_mfid, "annealed")
keywords = client.datasets.get_keywords(dataset_mfid=dataset_mfid)
```

## Thumbnails

```python
thumbnail = client.datasets.add_thumbnail(dataset_mfid, "preview.png")
thumbnails = client.datasets.get_thumbnails(dataset_mfid)

print(thumbnail["id"])
print(thumbnail["mime_type"])

client.datasets.update_thumbnail(
    dataset_mfid,
    thumbnail["id"],
    thumbnail_name="overview.png",
)

client.datasets.update_thumbnail(
    dataset_mfid,
    thumbnail["id"],
    image="replacement.png",
)
```

Thumbnail create, list, and update responses contain `id`, `dataset_id`, `thumbnail_name`, `thumbnail_b64str`, and the authoritative `mime_type`. The API currently normalizes stored thumbnails to JPEG, regardless of the extension in the user-facing thumbnail name.

From the CLI, add a local image with:

```bash
crucible dataset add-thumbnail DATASET_MFID preview.png
```

Use `--name NAME` to override the thumbnail name stored by the API.

## Downloading

```python
# Download all files for a dataset
client.datasets.download(dataset_mfid, output_dir="./downloads")

# Download only matching files
client.datasets.download(dataset_mfid, output_dir="./downloads", include=["*.dat"])

# Get temporary signed download URLs, keyed by file MFID
links = client.datasets.get_download_links(dataset_mfid)
```

## Parent-child relationships between datasets

Link datasets to represent a processing pipeline:

```python
# raw to processed
client.datasets.link(
    parent_mfid=raw_dataset_mfid,
    child_mfid=processed_dataset_mfid,
)

# List relationships
parents = client.datasets.list_parents(processed_dataset_mfid)
children = client.datasets.list_children(raw_dataset_mfid)
```

## Requesting dataset deletion

```python
client.deletions.request(dataset_mfid, reason="Superseded dataset")
```

!!! note
    A deletion request does not immediately remove the resource. An admin must approve it before permanent deletion.
