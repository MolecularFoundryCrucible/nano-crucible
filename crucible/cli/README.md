# Crucible CLI

Command-line interface for managing datasets, samples, projects, and instruments in Crucible.

## Quick Start

### 1. Configure API Access

First-time setup:

```bash
crucible config init
```

This will prompt you for:
- **API Key** (required) - Get it from https://crucible.lbl.gov/api/v1/user_apikey (includes user authentication)
- **API URL** (optional) - Defaults to https://crucible.lbl.gov/api/v1
- **Cache Directory** (optional) - Where to cache downloaded data
- **Graph Explorer URL** (optional) - For opening datasets in browser
- **Default Project** (optional) - Project to use when `-pid` not specified

### 2. Basic Operations

**List projects**:
```bash
crucible project list
```

**List datasets in a project**:
```bash
crucible dataset list -pid my-project
```

**Create and upload a dataset** (generic upload):
```bash
crucible dataset create -i mydata.csv -pid my-project
```

**Create and upload a LAMMPS dataset**:
```bash
crucible dataset create -i input.lmp -t lammps -pid my-project
```

**With metadata and keywords**:
```bash
crucible dataset create -i input.lmp -t lammps -pid my-project \
    -n "Water MD Simulation" \
    --metadata '{"temperature": 300, "pressure": 1.0}' \
    --keywords "validation,benchmark"
```

## Command Structure

The CLI is organized by resource type, similar to the Python client API:

```
crucible <resource> <action> [options]
```

### Resource Commands

- **dataset** - Dataset operations (list, get, create, update-metadata, link)
- **sample** - Sample operations (list, get, create, link, link-dataset)
- **project** - Project operations (list, get, create)
- **instrument** - Instrument operations (list, get)

### Utility Commands

- **config** - Manage configuration
- **upload** - [Legacy] Upload datasets (use `dataset create` instead)
- **open** - Open resources in Graph Explorer
- **link** - Link resources directly
- **completion** - Install shell autocomplete

## Dataset Commands

### List Datasets

List all datasets in a project:
```bash
crucible dataset list -pid my-project
crucible dataset list -pid my-project --limit 50
```

### Get Dataset

Get detailed information about a specific dataset:
```bash
crucible dataset get <dataset-id>
crucible dataset get <dataset-id> --include-metadata
```

### Create Dataset

Create and upload a new dataset:

#### Basic Syntax

```bash
crucible dataset create -i <files> -t <type> -pid <project> [options]
```

#### Required Arguments

- `-i, --input FILE [FILE ...]` - Input file(s) to upload

#### Common Options

- `-t, --type TYPE` - Dataset type (lammps, matensemble, base, etc.) - if not specified, uploads without parsing
- `-pid, --project-id ID` - Crucible project ID (uses config default if not specified)
- `-n, --name NAME` - Human-readable dataset name
- `-v, --verbose` - Show detailed output

#### Advanced Options

**Metadata & Keywords:**
- `--metadata JSON` - Scientific metadata as JSON string or path to JSON file
- `-k, --keywords WORDS` - Comma-separated keywords
- `-m, --measurement TYPE` - Measurement type (for generic uploads)

**Dataset Properties:**
- `--session NAME` - Session name for grouping related datasets
- `--public` - Make dataset public (default: private)
- `--instrument NAME` - Instrument name
- `--data-format FORMAT` - Data format type

**Identifiers:**
- `--mfid ID` - Unique dataset ID (auto-generated if not provided)

#### Examples

**Basic upload** (no parsing):
```bash
crucible dataset create -i data.csv -pid my-project
```

**LAMMPS simulation**:
```bash
crucible dataset create -i input.lmp -t lammps -pid my-project
```

**With metadata and keywords**:
```bash
crucible dataset create -i input.lmp -t lammps -pid my-project \
    --metadata '{"experiment_id": "EXP-001", "run_number": 5}' \
    --keywords "production,validated"
```

**Metadata from file**:
```bash
# metadata.json contains: {"sample": "Au-nanoparticles", "size_nm": 10, ...}
crucible dataset create -i data.csv -pid my-project --metadata metadata.json
```

**Complete example with all options**:
```bash
crucible dataset create -i input.lmp -t lammps -pid my-project \
    -n "Water MD at 300K" \
    --session "2024-Q1-water-study" \
    --metadata '{"temperature": 300, "ensemble": "NVT"}' \
    --keywords "water,molecular-dynamics,validation" \
    --instrument "NERSC-Perlmutter" \
    --public
```

### Update Dataset Metadata

Update scientific metadata for an existing dataset:
```bash
crucible dataset update-metadata <dataset-id> --metadata '{"temperature": 300}'
crucible dataset update-metadata <dataset-id> --metadata metadata.json
```

### Link Datasets

Create parent-child relationships between datasets:
```bash
crucible dataset link -p <parent-id> -c <child-id>
```

## Sample Commands

### List Samples

```bash
crucible sample list -pid my-project
```

### Get Sample

```bash
crucible sample get <sample-id>
```

### Create Sample

```bash
crucible sample create -n "Silicon Wafer A" -pid my-project
crucible sample create -n "Sample 001" -pid my-project --description "Test sample"
```

### Link Samples

Create parent-child relationships:
```bash
crucible sample link -p <parent-sample-id> -c <child-sample-id>
```

### Link Sample to Dataset

Associate a dataset with a sample:
```bash
crucible sample link-dataset -s <sample-id> -d <dataset-id>
```

## Project Commands

### List Projects

```bash
crucible project list
```

### Get Project

```bash
crucible project get <project-id>
```

### Create Project

```bash
crucible project create -n "My Project" -f "ALS"
crucible project create -n "Q1 2024 Experiments" -f "Molecular Foundry" --description "..."
```

## Instrument Commands

### List Instruments

```bash
crucible instrument list
```

### Get Instrument

```bash
crucible instrument get <instrument-name>
crucible instrument get <instrument-id> --by-id
```

## Available Parsers

Check current parsers:
```bash
crucible dataset create --help
```

Currently available:
- **base** - Generic upload, no parsing
- **lammps** - LAMMPS molecular dynamics simulations
- **matensemble** - MatEnsemble format files

## Configuration Management

### View Configuration

```bash
crucible config show
```

### Get a Value

```bash
crucible config get api_key
crucible config get current_project
```

### Set a Value

```bash
crucible config set current_project my-project
crucible config set graph_explorer_url https://custom-url.com
```

### Edit Config File

```bash
crucible config edit
```

### Config File Location

```bash
crucible config path
```

## Link Command

For direct resource linking (datasets or samples):
```bash
crucible link -p <parent-id> -c <child-id>
```

This command works with both datasets and samples. For resource-specific linking, use:
- `crucible dataset link` for datasets
- `crucible sample link` for samples

## Other Commands

### Legacy Upload Command

The `crucible upload` command is maintained for backward compatibility:
```bash
crucible upload -i data.csv -pid my-project -u
```

**Note:** This command requires the `-u` flag to actually upload. The new `crucible dataset create` command uploads by default and is recommended for new workflows.

### Open in Browser

Open a dataset in Graph Explorer:
```bash
# Open Graph Explorer home
crucible open

# Open project page
crucible open -pid my-project

# Open specific dataset
crucible open <mfid> -pid my-project

# Print URL instead of opening
crucible open <mfid> -pid my-project --print-url
```

### Shell Autocomplete

Install autocomplete for your shell:
```bash
# Bash
crucible completion bash

# Zsh
crucible completion zsh

# Fish
crucible completion fish
```

## Output

### Normal Output (INFO level)

Shows essential information:
```
=== Dataset Information ===
Project: my-project
Parser: LAMMPSParser
Name: Water MD Simulation
Measurement: LAMMPS
Data format: LAMMPS
Public: No

Files to upload (2):
  - input.lmp
  - data.lmp

Keywords (5): LAMMPS, molecular dynamics, H, O, water

Scientific Metadata (8 fields):
  elements: ['H', 'O']
  natoms: 648
  volume: 1000.5
  ...

=== Uploading to Crucible ===
Waiting for ingest request to complete...
Request completed with status: completed

✓ Upload successful!
Dataset ID: abc123xyz
```

### Verbose Output (DEBUG level)

Add `-v` for detailed debugging information:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u -v
```

Shows API requests, file operations, and detailed progress.

## Tips

1. **Set a default project** to avoid typing `-pid` every time:
   ```bash
   crucible config set current_project my-project
   crucible dataset create -i data.csv  # Uses default project
   ```

2. **List resources** to find IDs:
   ```bash
   crucible project list
   crucible dataset list -pid my-project
   crucible sample list -pid my-project
   ```

3. **Use JSON files** for complex metadata:
   ```bash
   # Create metadata.json with your metadata
   crucible dataset create -i data.csv -pid my-project --metadata metadata.json
   ```

4. **Combine user and parser metadata** - Parser-extracted metadata merges with your custom metadata:
   ```bash
   # LAMMPS parser extracts atoms, volume, etc.
   # Your metadata adds experiment-specific info
   crucible dataset create -i input.lmp -t lammps -pid my-project \
       --metadata '{"experiment_id": "EXP-001"}'
   ```

5. **Use resource-specific commands** for better organization:
   ```bash
   # Instead of generic link command
   crucible dataset link -p parent-id -c child-id
   crucible sample link-dataset -s sample-id -d dataset-id
   ```

## Getting Help

```bash
# General help
crucible --help

# Resource command help
crucible dataset --help
crucible sample --help
crucible project --help
crucible instrument --help

# Specific operation help
crucible dataset create --help
crucible sample list --help
crucible project get --help

# Config command help
crucible config --help
```

## Troubleshooting

**"API key not found"**
- Run `crucible config init` to set up your API key

**"Project ID required"**
- Specify `-pid project-id` or set default: `crucible config set current_project project-id`

**"Input file not found"**
- Check file path is correct and file exists

**"Unknown dataset type"**
- Run `crucible dataset create --help` to see available parser types
- Use `-t base` or omit `-t` for generic upload

**"mfid package not installed"**
- Install mfid: `pip install mfid`
- Or provide explicit mfid: `--mfid your-unique-id`

**"Dataset/Sample/Project not found"**
- Use list commands to find available resources:
  - `crucible project list`
  - `crucible dataset list -pid my-project`
  - `crucible sample list -pid my-project`

## Documentation

- **Parser Development**: See `../parsers/README.md` for creating custom parsers
- **Configuration**: Stored in `~/.config/pycrucible/config.ini`
- **Cache**: Stored in `~/.cache/pycrucible/`
