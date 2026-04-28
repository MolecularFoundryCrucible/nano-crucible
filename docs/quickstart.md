# Quick Start

This guide walks through the most common operations: connecting to Crucible, creating a dataset, creating a sample, and linking them together.

## Connect to Crucible

```python
from crucible import CrucibleClient

client = CrucibleClient()  # reads credentials from config or environment
```

Verify you're connected:

```python
print(client.whoami())
# {'orcid': '0000-0000-0000-0000', 'first_name': 'Jane', ...}
```

---

## Create a dataset

All fields are optional — you can create a bare dataset record and fill in metadata later:

```python
from crucible.models import Dataset

# Minimal: creates a record with just a unique_id
dataset = client.datasets.create(Dataset())
print(dataset["unique_id"])
```

Or provide as much context as you have upfront:

```python
dataset = client.datasets.create(
    dataset=Dataset(
        dataset_name="XRD measurement",
        measurement="X-ray diffraction",
        instrument_name="Beamline 12.3.2",
        project_id="my-project",
    ),
    files_to_upload=["xrd_data.xy"],
    scientific_metadata={"wavelength_angstrom": 0.7749, "temperature_K": 300},
    keywords=["XRD", "powder diffraction"],
)

print(dataset["unique_id"])  # system-assigned dataset ID
```

Retrieve it later:

```python
ds = client.datasets.get(dataset["unique_id"])
print(ds["dataset_name"])
```

---

## Create a sample

```python
sample = client.samples.create(
    sample_name="Silicon wafer A",
    sample_type="substrate",
    project_id="my-project",
    description="FZ silicon, 100-orientation, 4-inch wafer",
)

print(sample["unique_id"])  # system-assigned sample ID
```

---

## Link a dataset to a sample

```python
client.samples.add_dataset(sample["unique_id"], dataset["unique_id"])
```

You can also link datasets to each other (e.g., raw → processed):

```python
client.datasets.link_parent_child(parent_id=raw_unique_id, child_id=processed_unique_id)
```

---

## List datasets in a project

```python
datasets = client.datasets.list(project_id="my-project", limit=20)
for ds in datasets:
    print(ds["unique_id"], ds["dataset_name"])
```

---

## Download a dataset

```python
client.download("DATASET_ID", output_dir="./downloads")
```

---

## Using the CLI

The same operations are available from the terminal:

```bash
# Create a dataset with a file
crucible dataset create -i xrd_data.xy -n "XRD measurement" -m "X-ray diffraction" -pid my-project

# Create a sample
crucible sample create -n "Silicon wafer A" --type substrate -pid my-project

# Link them
crucible sample add-dataset SAMPLE_ID -d DATASET_ID

# List datasets
crucible dataset list -pid my-project

# Download
crucible download DATASET_ID
```

---

## Next steps

- [Core Concepts](concepts.md) — understand how Projects, Datasets, Samples, and Instruments relate
- [Working with Datasets](user-guide/datasets.md) — scientific metadata, ingestion, thumbnails, and more
- [Working with Samples](user-guide/samples.md) — sample hierarchies and provenance
- [CLI Reference](cli/reference.md) — full command reference
