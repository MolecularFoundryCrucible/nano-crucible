# nano-crucible

**N**ational **A**rchive for **N**SRC **O**bservations - Crucible

A Python client library for the Crucible API - the Molecular Foundry data lakehouse containing experimental synthesis and characterization data, along with information about users, projects, and instruments.

## Features

- **Dataset Management**: Create, update, list, and retrieve datasets with metadata
- **File Operations**: Upload, download, and manage dataset files and thumbnails
- **Scientific Metadata**: Store and retrieve experimental parameters and instrument settings
- **Sample Tracking**: Manage samples with hierarchical relationships and type-specific metadata
- **Instrument Integration**: Register and manage scientific instruments
- **Project Organization**: Create and manage projects 
- **Processing Workflows**: Request data ingestion and SciCat synchronization
- **Access Control**: Manage permissions and user access to datasets and resources

## Installation

```bash
pip install git+https://github.com/MolecularFoundryCrucible/nano-crucible
```

## Quick Start
API keys can be retrieved at https://crucible.lbl.gov/testapi/user_apikey

```python
from crucible import CrucibleClient

# Initialize the client
client = CrucibleClient(
    api_url="https://crucible.lbl.gov/testapi",
    api_key="your-api-key"
)

# List your datasets
datasets = client.list_datasets()

# Get a specific dataset with metadata
dataset = client.get_dataset("dataset-id", include_metadata=True)

# Upload a file
client.upload_dataset("dataset-id", "path/to/file.txt")

# Create a new dataset (example)
# 
new_dataset = client.build_new_dataset_from_json(
    dataset_name="My Experiment",
    measurement="XRD",
    public=False,
    scientific_metadata={
        "temperature": 298.15,
        "voltage": 200,
        "sample_preparation": "standard protocol"
    },
    keywords=["crystallography", "materials"]
)
```


## Core Concepts

## Main Functions

### Dataset Operations
- `list_datasets()` - List accessible datasets with filtering
- `get_dataset(dsid)` - Retrieve specific dataset details
- `build_dataset_from_json()` - Create new dataset record in Crucible even if no physical data files exist. Useful for synthesis parameters. 
- `build_dataset_from_file()` - Create new dataset record in Crucible based on an input data file.  Includes the option to use a pre-existing ingestion class or provide metadata manually. 
- `download_dataset(dsid)` - Download dataset files
- `add_dataset_to_sample(dataset_id, sample_id)` - Link a dataset to a sample
  
### Metadata Management
- `get_scientific_metadata(dsid)` - Get experimental parameters
- `update_scientific_metadata(dsid, metadata)` - Add scientific metadata to a datasets existing scientific metadata entry
- `add_dataset_keyword(dsid, keyword)` - Tag datasets with additional keywords
- `add_associated_file(dsid, file_path, filename)` - Link a file to a dataset record
  
### Sample Management
- `list_samples()` - List samples you have access to view
- `add_sample()` - Create new sample records
- `add_sample_to_dataset(dataset_id, sample_id)` - Link samples to datasets
- `link_samples(parent_id, child_id)` - Link samples to other samples (parent-child relationship)

### Processing Workflows
- `request_ingestion(dsid)` - Process uploaded files
- `send_to_scicat(dsid)` - Sync to SciCat catalog
- `wait_for_request_completion()` - Monitor processing status

## License

This project is licensed under the BSD License - see the LICENSE file for details.
