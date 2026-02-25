# nano-crucible : **N**ational **A**rchive for **N**SRC **O**bservations

[![PyPI version](https://img.shields.io/pypi/v/nano-crucible.svg)](https://pypi.org/project/nano-crucible/) [![PyPI downloads](https://img.shields.io/pypi/dm/nano-crucible.svg)](https://pypi.org/project/nano-crucible/) [![GitHub release](https://img.shields.io/github/v/release/MolecularFoundryCrucible/nano-crucible)](https://github.com/MolecularFoundryCrucible/nano-crucible/releases) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/) [![License](https://img.shields.io/badge/license-BSD-green.svg)](LICENSE) [![GitHub stars](https://img.shields.io/github/stars/MolecularFoundryCrucible/nano-crucible?style=social)](https://github.com/MolecularFoundryCrucible/nano-crucible)

A Python client library and CLI tool for Crucible - the Molecular Foundry's data lakehouse for scientific research. Crucible stores experimental and synthetic data from DOE Nanoscale Science Research Centers (NSRCs), along with comprehensive metadata about samples, projects, instruments, and users.

## 🔬 What is Crucible?

Crucible is the centralized data infrastructure for the [Molecular Foundry](https://foundry.lbl.gov/) and other [DOE Nanoscale Science Research Centers](https://science.osti.gov/bes/suf/User-Facilities/Nanoscale-Science-Research-Centers), providing:

- **Unified data storage** for experimental and synthetic data
- **Rich metadata** capture to associate with datasets
- **Sample provenance** tracking with parent-child relationships

## ✨ Features

### 🐍 Python API

- **Dataset Management**: Create, query, update, and download datasets
- **Sample Tracking**: Manage samples with hierarchical relationships and provenance
- **Metadata**: Store and retrieve scientific metadata and experimental parameters
- **Linking**: Connect datasets, samples, and create relationships programmatically

### 🖥️ Command-Line Interface

- **`crucible config`**: One-time setup and configuration management
- **`crucible dataset`**: Create, list, update, and manage datasets
- **`crucible sample`**: Create, list, and manage samples with relationships
- **`crucible project`**: Manage projects and users (admin)
- **`crucible open`**: Open resources in the Crucible Web Explorer with one command

## 📦 Installation

### From PyPI (Recommended)

```bash
pip install nano-crucible
```

### From GitHub (Latest Development)

```bash
pip install git+https://github.com/MolecularFoundryCrucible/nano-crucible
```

### With Optional Dependencies

```bash
# Install with parser support (includes ASE for LAMMPS and MatEnsemble parsers)
pip install nano-crucible[parsers]

# Install everything
pip install nano-crucible[all]

# For development
pip install nano-crucible[dev]
```

### For Development

```bash
git clone https://github.com/MolecularFoundryCrucible/nano-crucible.git
cd nano-crucible
pip install -e ".[dev]"
```

## 🚀 Quick Start

### Configuration

First, configure your API credentials:

```bash
crucible config init
```

Get your API key at: [https://crucible.lbl.gov/api/v1/user_apikey](https://crucible.lbl.gov/api/v1/user_apikey)

**Alternative (without terminal access)**: Initialize the client directly with your credentials:

```python
from crucible import CrucibleClient
client = CrucibleClient(
    api_url="https://crucible.lbl.gov/api/v1",
    api_key="your-api-key-here"
)
```

### Python API

```python
from crucible import CrucibleClient
from crucible.models import BaseDataset

# Initialize client
client = CrucibleClient()

# Create a dataset
dataset = BaseDataset(
    dataset_name="My Experiment",
    measurement="XRD",
    project_id="my-project",
    public=False
)

result = client.datasets.create(
    dataset=dataset,
    scientific_metadata={"temperature_C": 300},
    keywords=["experiment", "test"]
)

print(f"Dataset created: {result['dsid']}")
```

**📓 For complete examples, see the tutorial notebooks:**
- [**Main Tutorial**](examples/crucible_tutorial.ipynb) - Creating datasets, samples, linking, and downloading
- [**Project Management**](examples/crucible_project_management.ipynb) - Managing projects and users (admin)

### Command-Line Interface

```bash
# Configure API credentials
crucible config init

# Create a dataset with files
crucible dataset create -i data.csv -n "My Dataset" -m "XRD" -pid my-project

# List datasets in a project
crucible dataset list -pid my-project

# Get dataset details
crucible dataset get DATASET_ID

# Create a sample
crucible sample create -n "Sample A" -pid my-project

# Link sample to dataset
crucible sample add-to-dataset SAMPLE_ID DATASET_ID

# Open a resource in your browser
crucible open DATASET_ID
```

**📖 For complete CLI documentation, see [cli/README.md](crucible/cli/README.md)**

## 📖 Documentation

- **Tutorial Notebooks**: See [examples/](examples/) - Comprehensive Jupyter notebooks with runnable examples
  - [Main Tutorial](examples/crucible_tutorial.ipynb) - Datasets, samples, linking, downloading
  - [Project Management](examples/crucible_project_management.ipynb) - Projects and users (admin)
- **CLI Documentation**: See [cli/README.md](crucible/cli/README.md) - Complete command-line reference
- **Parser Documentation**: See [parsers/README.md](crucible/parsers/README.md) - Custom data format parsers

## 🤝 Contributing

We welcome contributions! Areas where you can help:

- **New parsers** for additional data formats
- **Bug reports** and feature requests
- **Documentation** improvements
- **Example notebooks** and tutorials

## 📄 License

This project is licensed under the BSD-3-Clause License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Crucible API**: [https://crucible.lbl.gov/api/v1](https://crucible.lbl.gov/api/v1)
- **Crucible Web Interface**: [https://crucible-graph-explorer-776258882599.us-central1.run.app](https://crucible-graph-explorer-776258882599.us-central1.run.app)

## 💬 Support

For issues, questions, or feature requests:

- **GitHub Issues**: [https://github.com/MolecularFoundryCrucible/nano-crucible/issues](https://github.com/MolecularFoundryCrucible/nano-crucible/issues)
- **Email**: mkwall@lbl.gov, roncoroni@lbl.gov, esbarnard@lbl.gov

---

**nano-crucible** is developed and maintained by the [Data Group](https://foundry.lbl.gov/expertise-instrumentation/#data-and-analytics-expertise) at the Molecular Foundry at Lawrence Berkeley National Laboratory.
