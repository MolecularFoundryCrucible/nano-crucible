# nano-crucible : **N**ational **A**rchive for **N**SRC **O**bservations

[![PyPI version](https://img.shields.io/pypi/v/nano-crucible.svg)](https://pypi.org/project/nano-crucible/) [![PyPI downloads](https://img.shields.io/pypi/dm/nano-crucible.svg)](https://pypi.org/project/nano-crucible/) [![GitHub release](https://img.shields.io/github/v/release/MolecularFoundryCrucible/nano-crucible)](https://github.com/MolecularFoundryCrucible/nano-crucible/releases) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/) [![License](https://img.shields.io/badge/license-BSD-green.svg)](LICENSE) [![GitHub stars](https://img.shields.io/github/stars/MolecularFoundryCrucible/nano-crucible?style=social)](https://github.com/MolecularFoundryCrucible/nano-crucible)

A Python client library and CLI tool for Crucible - the Molecular Foundry's data lakehouse for scientific research. Crucible stores experimental and synthetic data from DOE Nanoscale Science Research Centers (NSRCs), along with comprehensive metadata about samples, projects, instruments, and users.

## 🔬 What is Crucible?

Crucible is the centralized data infrastructure for the [Molecular Foundry](https://foundry.lbl.gov/) and other [DOE Nanoscale Science Research Centers](https://science.osti.gov/bes/suf/User-Facilities/Nanoscale-Science-Research-Centers), providing:

- **Unified data storage** for experimental and synthetic data
- **Rich metadata** capture for to associate to datasets
- **Sample provenance** tracking with parent-child relationships

## ✨ Features

### 🐍 Python API

- **Dataset Management**: Create, query, update, and download datasets
- **Sample Tracking**: Manage samples with hierarchical relationships and provenance
- **Metadata**: Store and retrieve scientific metadata and experimental parameters
- **Linking**: Connect datasets, samples, and create relationships programmatically

### 🖥️ Command-Line Interface

- **`crucible config`**: One-time setup and configuration management
- **`crucible upload`**: Upload datasets with automatic parsing and metadata extraction
- **`crucible open`**: Open resources in the Crucible Web Explorer with one command
- **`crucible link`**: Create relationships between datasets and samples

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

### Python API

#### Creating and Uploading Datasets

```python
from crucible import CrucibleClient, BaseDataset
from crucible.config import config

# Get client
client = config.client

# Method 1: Create dataset (no files)
dataset = client.create_new_dataset(
    unique_id = "my-unique-dataset-id",  # Optional, auto-generated if None
    dataset_name="High-Temperature Synthesis",
    measurement="XRD",
    project_id="nanomaterials-2024",
    public=False,
    scientific_metadata={
        "temperature_C": 800,
        "pressure_bar": 1.0,
        "duration_hours": 12,
        "atmosphere": "nitrogen"
    },
    keywords=["synthesis", "high-temperature", "oxides"]
)

# Method 2: Upload dataset with files using BaseDataset
dataset = BaseDataset(
    unique_id="my-unique-dataset-id",  # Optional, auto-generated if None
    dataset_name="Electron Microscopy Images",
    measurement="TEM",
    project_id="nanomaterials-2024",
    public=False,
    instrument_name="TEM-2100",
    data_format="TIFF",
    file_to_upload="/path/to/image.tiff"
)

# Upload with metadata and files
result = client.create_new_dataset_from_files(
    dataset=dataset,
    scientific_metadata={
        "magnification": 50000,
        "voltage_kV": 200,
        "spot_size": 3
    },
    keywords=["TEM", "imaging", "nanoparticles"],
    files_to_upload=["/path/to/image.tiff", "/path/to/calibration.txt"],
    thumbnail="/path/to/thumbnail.png",  # Optional
    ingestor='ApiUploadIngestor',
    wait_for_ingestion_response=True
)

print(f"Dataset created: {result['created_record']['unique_id']}")
```

#### Linking Resources

```python
# Link two datasets
client.link_datasets("parent-dataset", "child-dataset")
# Link two samples
client.link_samples("parent-sample", "child-sample")
# Link sample to dataset
client.add_sample_to_dataset("dataset-id", "sample-id")
```

### Command-Line Interface

#### 1. Initial Configuration

```bash
# One-time setup
crucible config init

# View your configuration
crucible config show

# Update settings
crucible config set api_key YOUR_NEW_KEY
```

Get your API key at: [https://crucible.lbl.gov/api/v1/user_apikey](https://crucible.lbl.gov/api/v1/user_apikey)

#### 2. Upload Data with Parsers

```bash
# Upload with generic dataset
crucible upload -i data.txt -pid my-project \
    --metadata '{"temperature=300,pressure=1.0"}' \
    --keywords "experiment,test"

# Upload specific dataset (e.g. LAMMPS simulation)
# Works only if the parser exists
crucible upload -i simulation.lmp -t lammps -pid my-project
```

#### 3. Link Resources

```bash
# Link two datasets
crucible link -p parent_dataset_id -c child_dataset_id
# Link two samples
crucible link -p parent_sample_id -c child_sample_id
# Link sample to dataset
crucible link -d dataset_id -s sample_id
```

#### 4. Open in Browser

```bash
# Open the Crucible Web Explorer
crucible open
# Open to a specific resource
crucible open RESOURCE_MFID
```

## 📖 Documentation

- **CLI Documentation**: See [cli/README.md](crucible/cli/README.md)
- **Parser Documentation**: See [parsers/README.md](crucible/parsers/README.md)
- **API Reference**: Coming soon

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
