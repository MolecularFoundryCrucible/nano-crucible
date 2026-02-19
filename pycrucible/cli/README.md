# Crucible CLI

Command-line interface for uploading and managing datasets in Crucible.

## Quick Start

### 1. Configure API Access

First-time setup:

```bash
crucible config init
```

This will prompt you for:
- **API Key** (required) - Get it from https://crucible.lbl.gov/testapi/user_apikey (includes user authentication)
- **API URL** (optional) - Defaults to https://crucible.lbl.gov/testapi
- **Cache Directory** (optional) - Where to cache downloaded data
- **Graph Explorer URL** (optional) - For opening datasets in browser
- **Default Project** (optional) - Project to use when `-pid` not specified

### 2. Upload a Dataset

**Generic upload** (no parsing):
```bash
crucible upload -i mydata.csv -pid my-project -u
```

**LAMMPS simulation**:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u
```

**With metadata and keywords**:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u \
    -n "Water MD Simulation" \
    --metadata '{"temperature": 300, "pressure": 1.0}' \
    --keywords "validation,benchmark"
```

## Upload Command

### Basic Syntax

```bash
crucible upload -i <files> -t <type> -pid <project> -u [options]
```

### Required Arguments

- `-i, --input FILE [FILE ...]` - Input file(s) to upload

### Common Options

- `-t, --type TYPE` - Dataset type (lammps, base, etc.) - if not specified, uploads without parsing
- `-pid, --project-id ID` - Crucible project ID (uses config default if not specified)
- `-u, --upload` - Actually upload to Crucible (without this, just parses/validates)
- `-n, --name NAME` - Human-readable dataset name
- `-v, --verbose` - Show detailed output

### Advanced Options

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

## Examples

### Basic Upload

Upload a single file without parsing:
```bash
crucible upload -i data.csv -pid my-project -u
```

### LAMMPS Simulation

Parse and upload LAMMPS data:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u
```

### With Metadata

Add custom metadata to parsed data:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u \
    --metadata '{"experiment_id": "EXP-001", "run_number": 5}' \
    --keywords "production,validated"
```

### Metadata from File

Use a JSON file for complex metadata:
```bash
# metadata.json contains: {"sample": "Au-nanoparticles", "size_nm": 10, ...}
crucible upload -i data.csv -pid my-project -u --metadata metadata.json
```

### Complete Example

Upload with all options:
```bash
crucible upload -i input.lmp -t lammps -pid my-project -u \
    -n "Water MD at 300K" \
    --session "2024-Q1-water-study" \
    --metadata '{"temperature": 300, "ensemble": "NVT"}' \
    --keywords "water,molecular-dynamics,validation" \
    --instrument "NERSC-Perlmutter" \
    --public
```

### Without Uploading

Parse and validate without uploading (omit `-u`):
```bash
crucible upload -i input.lmp -t lammps -pid my-project
```

Shows what would be uploaded without actually uploading.

## Available Parsers

Check current parsers:
```bash
crucible upload --help
```

Currently available:
- **base** - Generic upload, no parsing
- **lammps** - LAMMPS molecular dynamics simulations

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

## Other Commands

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
   crucible upload -i data.csv -u  # Uses default project
   ```

2. **Parse without uploading** to check what will be uploaded:
   ```bash
   crucible upload -i input.lmp -t lammps -pid my-project
   # Omit -u flag to see what would be uploaded
   ```

3. **Use JSON files** for complex metadata:
   ```bash
   # Create metadata.json with your metadata
   crucible upload -i data.csv -pid my-project -u --metadata metadata.json
   ```

4. **Combine user and parser metadata** - Parser-extracted metadata merges with your custom metadata:
   ```bash
   # LAMMPS parser extracts atoms, volume, etc.
   # Your metadata adds experiment-specific info
   crucible upload -i input.lmp -t lammps -pid my-project -u \
       --metadata '{"experiment_id": "EXP-001"}'
   ```

## Getting Help

```bash
# General help
crucible --help

# Upload command help
crucible upload --help

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
- Run `crucible upload --help` to see available parser types
- Use `-t base` or omit `-t` for generic upload

**"mfid package not installed"**
- Install mfid: `pip install mfid`
- Or provide explicit mfid: `--mfid your-unique-id`

## Documentation

- **Parser Development**: See `../parsers/README.md` for creating custom parsers
- **Configuration**: Stored in `~/.config/pycrucible/config.ini`
- **Cache**: Stored in `~/.cache/pycrucible/`
