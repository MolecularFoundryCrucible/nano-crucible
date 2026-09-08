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
## Choose a project

Datasets and samples belong to projects. Use a project ID you can access:

```python
PROJECT_ID = "my-project"
```

Creating projects and managing members requires additional permissions. See the [project management guide](user-guide/projects.md) for those workflows.

---


## Create a dataset

Provide the context needed to identify and reuse the dataset:

```python
from crucible.models import Dataset

result = client.datasets.create(
    dataset=Dataset(
        dataset_name="XRD measurement",
        measurement="X-ray diffraction",
        data_type="X-ray diffraction xy file",
        instrument_name="Rigaku_XRD",
        project_id=PROJECT_ID,
    ),
    files=["xrd_data.xy"],
    scientific_metadata={"wavelength_angstrom": 0.7749, "temperature_K": 300},
    keywords=["XRD", "powder diffraction"],
)

dataset_mfid = result["dataset_mfid"]
dataset = result["created_record"]
print(dataset_mfid)
```

Retrieve it later:

```python
ds = client.datasets.get(dataset_mfid)
print(ds["dataset_name"])
```

---

## Create a sample

```python
from crucible.models import Sample

sample = client.samples.create(Sample(
    sample_name="Silicon wafer A",
    sample_type="substrate",
    project_id=PROJECT_ID,
    description="FZ silicon, 100-orientation, 4-inch wafer",
))

print(sample["unique_id"])  # system-assigned sample MFID
```

---

## Link a dataset to a sample

```python
client.samples.link_dataset(sample["unique_id"], dataset_mfid)
```

See [linking resources](user-guide/linking.md) for dataset processing chains and sample hierarchies.

---

## List datasets in a project

```python
datasets = client.datasets.list(project_id=PROJECT_ID, limit=20)
for ds in datasets:
    print(ds["unique_id"], ds["dataset_name"])
```

---

## Download a dataset

```python
client.datasets.download(dataset_mfid, output_dir="./downloads")
```

---

## Using the CLI

The same operations are available from the terminal:

```bash
# Create a dataset with a file
crucible dataset create -i xrd_data.xy -n "XRD measurement" -m "X-ray diffraction" --project-id my-project

# Create a sample
crucible sample create -n "Silicon wafer A" --type substrate --project-id my-project

# Link them
crucible sample add-dataset SAMPLE_ID -d DATASET_ID

# List datasets
crucible dataset list --project-id my-project

# Download
crucible download DATASET_ID
```

---

## Next steps

- [Core Concepts](concepts.md) — understand how Projects, Datasets, Samples, and Instruments relate
- [Working with Datasets](user-guide/datasets.md) — scientific metadata, ingestion, thumbnails, and more
- [Working with Samples](user-guide/samples.md) — sample hierarchies and provenance
- [CLI Reference](cli/reference.md) — full command reference
