# Installation

## Requirements

- Python 3.8 or later
- A Crucible account and API key ([crucible.lbl.gov](https://crucible.lbl.gov))

## Install from PyPI

```bash
pip install nano-crucible
```

### Optional extras

```bash
# Parser support (includes ASE for LAMMPS/MatEnsemble parsers)
pip install nano-crucible[parsers]

# Interactive shell with tab-completion
pip install nano-crucible[shell]

# Everything
pip install nano-crucible[all]
```

### Development install

```bash
git clone https://github.com/MolecularFoundryCrucible/nano-crucible.git
cd nano-crucible
pip install -e ".[dev]"
```

---

## Configuration

### Recommended: config file

Run the interactive setup wizard once after installing:

```bash
crucible config init
```

This prompts for your API key and writes a config file at `~/.config/nano-crucible/config.ini` (path varies by OS). All subsequent CLI and Python API calls will use it automatically — no environment variables needed.

You can review or change settings at any time:

```bash
crucible config show       # view current settings
crucible config set KEY VALUE
crucible config edit       # open in your editor
```

Useful config keys:

| Key | Description |
|---|---|
| `api_key` | Your Crucible API key |
| `api_url` | API base URL (default: `https://crucible.lbl.gov/api/v2`) |
| `current_project` | Default project ID used by CLI commands |

### Alternative: pass credentials directly in Python

```python
from crucible import CrucibleClient

client = CrucibleClient(
    api_url="https://crucible.lbl.gov/api/v2",
    api_key="your-api-key",
)
```

### Alternative: environment variables (useful for CI/automation)

```bash
export CRUCIBLE_API_KEY="your-api-key"
export CRUCIBLE_API_URL="https://crucible.lbl.gov/api/v2"
```

Environment variables take priority over the config file when both are present.

---

## Getting your API key

Log in and visit [crucible.lbl.gov/api/v2/user_apikey](https://crucible.lbl.gov/api/v2/user_apikey) to generate or retrieve your API key.

---

## Verify your setup

```bash
crucible whoami
```

Or in Python:

```python
client = CrucibleClient()
print(client.whoami())
```
