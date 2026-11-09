# Installation

## Requirements

- Python 3.11 or later
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

> **Note:** `prompt_toolkit` (interactive shell) is a core dependency; no extra is needed.

### Development install

```bash
git clone https://github.com/MolecularFoundryCrucible/nano-crucible.git
cd nano-crucible
pip install -e ".[dev]"
```

---

## Configuration

### Sign in with a browser

```bash
crucible login            # opens your browser on this computer
crucible login --device   # over SSH or without a browser: approve a code on any device
crucible whoami           # shows "Signed in with"
crucible logout
```

The sign-in is kept in your OS keyring (macOS Keychain, Windows Credential Locker, or Secret Service on Linux). Where no keyring is reachable, such as a headless Linux machine or cluster node, it goes in a file only you can read in the config directory; set `auth_store` to `keyring`, `file`, or `memory` to choose. Sessions renew themselves and end after 14 days without use or 90 days at most.

Some actions, such as creating an API key, need a sign-in from the last 10 minutes. The CLI asks you to sign in again in your browser when that happens. A sign-in approved with a code (`--device`) cannot do these actions; use a computer with a browser or the Hub.

An API key still works and is the right choice for scripts, CI, and batch jobs. The CLI uses, in order: an `api_key` passed to `CrucibleClient`, `CRUCIBLE_API_KEY`, your sign-in, then `api_key` in the config file.

### API key: config file

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
| `hub_url` | Crucible Hub address (default: `https://crucible.lbl.gov/hub`) |
| `auth_store` | Where `crucible login` keeps tokens: `auto` (default), `keyring`, `file`, or `memory` |

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

Use explicit `--project-id` arguments for automation. `CRUCIBLE_CURRENT_PROJECT` was removed in 4.0.0 because it could silently redirect commands to another project; the CLI stops if it is set.

If an older config explicitly selects API v1 or v2, Nano displays a migration warning. Run `crucible config unset api_url` to inherit the API v3 endpoint packaged with Nano, or set the override to the desired deployment explicitly.

---

## Getting your API key

Sign in to the Crucible Hub and create a key on your account page: [crucible.lbl.gov/hub/account](https://crucible.lbl.gov/hub/account#api-keys). After `crucible login`, `crucible account keys create NAME` also creates one. A key is shown only once.

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
