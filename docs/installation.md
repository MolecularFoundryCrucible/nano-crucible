# Installation

## Requirements

- Python 3.9 or later
- A Crucible account and API key ([crucible.lbl.gov](https://crucible.lbl.gov))

## Install from PyPI

```bash
pip install nano-crucible
```

### Optional extras

```bash
# Parser support (includes ASE for LAMMPS/MatEnsemble parsers)
pip install nano-crucible[parsers]
```

> **Note:** `google-cloud-storage` (GCS parallel upload) and `prompt_toolkit` (interactive shell) are included as core dependencies — no extra needed.

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

This securely prompts for your API key without displaying it and writes a config file at `~/.config/nano-crucible/config.ini` (path varies by OS). All subsequent CLI and Python API calls will use it automatically. If a corresponding environment variable is set, it takes precedence and the wizard reports that override.

You can review or change settings at any time:

```bash
crucible config show       # view current settings
crucible config set KEY VALUE
crucible config unset KEY  # remove an override
crucible config edit       # open in your editor
```

Useful config keys:

| Key | Description |
|---|---|
| `api_key` | Your Crucible API key |
| `api_url` | Optional API override (default: `https://crucible.lbl.gov/api/v3`) |
| `current_project` | Current project ID used when a command omits `--project-id` |

### Alternative: pass credentials directly in Python

```python
from crucible import CrucibleClient

client = CrucibleClient(
    api_key="your-api-key",
)
```

### Alternative: environment variables (useful for CI/automation)

```bash
export CRUCIBLE_API_KEY="your-api-key"
```

Set `CRUCIBLE_API_URL` only when targeting staging or another non-default deployment. Environment variables take priority over the config file when both are present.

Use explicit `--project-id` arguments for automation. `CRUCIBLE_CURRENT_PROJECT` is deprecated because it can silently redirect operations away from the project saved by the interactive shell.

If an older config explicitly selects API v1 or v2, Nano displays a migration warning. Run `crucible config unset api_url` to inherit the API v3 endpoint packaged with Nano, or set the override to the desired deployment explicitly.

---

## Getting your API key

Log in and visit [crucible.lbl.gov/api/v3/user_apikey](https://crucible.lbl.gov/api/v3/user_apikey) to generate or retrieve your API key.

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
