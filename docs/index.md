# nano-crucible

[![PyPI version](https://img.shields.io/pypi/v/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD-green.svg)](https://github.com/MolecularFoundryCrucible/nano-crucible/blob/main/LICENSE)
[![Discord](https://img.shields.io/discord/1476722549424394242?logo=discord&label=Discord&color=5865F2)](https://discord.gg/Wrepphsgbx)

**nano-crucible** is the official Python client library and CLI for [Crucible](https://crucible.lbl.gov) — the data management platform for the [Molecular Foundry](https://foundry.lbl.gov/) and DOE Nanoscale Science Research Centers (NSRCs).

Use it to store, retrieve, and manage scientific datasets as well as metadata about the samples, instruments, and projects with which they are associated. 

---

## What you can do

- **Catalog and annotate datasets** — create dataset records with structured metadata, flexible scientific metadata about how the data was collected, and attach associated raw data files. 
- **Create relationships between datasets** - upload analysis results and link to raw parent datasets with scientific metadata about how the analysis was performed. 
- **Track sample provenance** — create hierarchical sample trees and link samples to their synthesis recipes and characterization data. 
- **Organize data into projects** — share data with collaborators and control dataset access by associating each dataset with a project ID. 
- **Search and download** — query the platform through keyword searches, group by filters, and relationship traversals. Download raw data files from their cloud storage locations to your working environment. 

---

## Quick example

```python
from crucible import CrucibleClient
from crucible.models import Dataset, Sample, Project

client = CrucibleClient()

# Create a project
project = client.projects.create(Project(
    project_id="my-project",
    organization="LBNL",
    project_lead_orcid="0000-0001-2345-6789",
))

# Add a user to your project
client.projects.add_user(project_id=project["project_id"], email="user@lbl.gov")
# or by ORCID: client.projects.add_user(project_id=project["project_id"], orcid="0000-0001-2345-6789")

# Create a sample
sample = client.samples.create(
    sample_name="Au nanoparticles",
    sample_type="nanoparticle suspension",
    project_id=project["project_id"],
)
# More information about the fields that can be added when creating a sample are documented [here](user-guide/samples.md)

# Upload a dataset and link it to the sample
dataset = client.datasets.create(
    dataset=Dataset(
        dataset_name="SAXS run 42",
        measurement="Small-angle X-ray scattering",
        instrument_name="SAXS beamline",
        project_id=project["project_id"],
    ),
    files_to_upload=["saxs_run42.dat"],
    scientific_metadata={"energy_keV": 10.0, "sample_detector_distance_m": 1.5},
    keywords=["SAXS", "nanoparticles", "gold"],
)

# Link the dataset to the sample
client.samples.add_dataset(sample["unique_id"], dataset["unique_id"])

# More information about creating datasets is documented [here](user-guide/datasets.md)

print(f"Sample:  {sample['unique_id']}")
print(f"Dataset: {dataset['unique_id']}")
```

---

## Key concepts

| Object | What it represents |
|---|---|
| [**Project**](user-guide/projects.md) | Projects are primarily used as an access control layer for organizing datasets and samples and regulating which users are authorized to access them. Roughly maps to a user proposal at a user facility. |
| [**Dataset**](user-guide/datasets.md) | The primary data object: Datasets represent the experimental parameters required to repeat an experiment or process as well as raw data files that provide additional information or contain the results of the experiment. Datasets can include associated files, thumbnail images, flexible nested json as scientific metadata, and relationships with other datasets or samples. 
| [**Sample**](user-guide/samples.md) | The physical or computational material that was studied. Samples form parent-child hierarchies to capture provenance (boule → wafer → thin film) and link to datasets that capture each experimental or analytical method performed on the sample.  Samples may also include flexible nested json to capture observed properties of the sample itself such as solubility or physical location.  
| [**Instrument**](user-guide/instruments.md) | The physical equipment from which a dataset originated. Instruments are shared across projects, but intended to represent individual machines rather than equipment classes, for example two TEM's of the same make and model would be represented by separate entries. |

---

## Getting started

1. [Install the package](installation.md)
2. [Configure your API key](installation.md#configuration)
3. [Follow the quick start guide](quickstart.md)
4. [Set up a UI for your instrument](integrations.md)
---

## Support

- **Discord**: [Join our server](https://discord.gg/Wrepphsgbx)
- **GitHub Issues**: [Report a bug or request a feature](https://github.com/MolecularFoundryCrucible/nano-crucible/issues)
- **Email**: mkwall@lbl.gov, roncoroni@lbl.gov, esbarnard@lbl.gov
