# nano-crucible

[![PyPI version](https://img.shields.io/pypi/v/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD-green.svg)](https://github.com/MolecularFoundryCrucible/nano-crucible/blob/main/LICENSE)
[![Discord](https://img.shields.io/discord/1476722549424394242?logo=discord&label=Discord&color=5865F2)](https://discord.gg/Wrepphsgbx)

**nano-crucible** is the official Python client library and CLI for [Crucible](https://crucible.lbl.gov) — the data management platform for the [Molecular Foundry](https://foundry.lbl.gov/) and DOE Nanoscale Science Research Centers (NSRCs).

Use it to store, retrieve, and manage scientific datasets alongside rich metadata about the samples, instruments, and projects they belong to.

---

## What you can do

- **Upload and manage datasets** — attach files, instrument metadata, measurement type, and custom scientific metadata
- **Track sample provenance** — create hierarchical sample trees and link samples to the datasets measured from them
- **Organize work into projects** — control access and group related datasets and samples
- **Search and download** — query by keyword or scientific metadata and download files locally
- **Automate with the CLI** — script common operations or run interactive sessions from the terminal

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

# Create a sample
sample = client.samples.create(
    sample_name="Au nanoparticles",
    sample_type="nanoparticle suspension",
    project_id=project["project_id"],
)

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

print(f"Sample:  {sample['unique_id']}")
print(f"Dataset: {dataset['unique_id']}")
```

---

## Key concepts

| Object | What it represents |
|---|---|
| [**Project**](models/project.md) | Your research container — groups datasets and samples, and determines who can access them. Roughly maps to a user proposal at a user facility. |
| [**Dataset**](models/dataset.md) | The primary data object: structured metadata (measurement type, instrument, scientific parameters, keywords) with optional attached files. Datasets can be chained (raw → processed) and linked to the samples they came from. |
| [**Sample**](models/sample.md) | The physical or computational material that was studied. Samples form parent-child hierarchies to capture provenance (boule → wafer → thin film) and link to every dataset measured from them. |
| [**Instrument**](models/instrument.md) | The physical equipment from which a dataset originated. Instruments are shared across projects, but each distinct physical instrument gets its own entry — two labs that both own a Verios SEM are two separate instruments. |

---

## Getting started

1. [Install the package](installation.md)
2. [Configure your API key](installation.md#configuration)
3. [Follow the quick start guide](quickstart.md)

---

## Support

- **Discord**: [Join our server](https://discord.gg/Wrepphsgbx)
- **GitHub Issues**: [Report a bug or request a feature](https://github.com/MolecularFoundryCrucible/nano-crucible/issues)
- **Email**: mkwall@lbl.gov, roncoroni@lbl.gov, esbarnard@lbl.gov
