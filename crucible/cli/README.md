# Crucible CLI Cheat Sheet

The `crucible CLI` provides command-line access to Crucible. Resource commands follow the pattern:

```
crucible [--debug] <resource> <action> [options]
```

Utility commands (`status`, `download`, `link`, `unlink`, `open`, `whoami`, `cache`) operate directly on IDs without a sub-action and auto-detect the resource type where relevant.

Running `crucible` with no arguments starts an **interactive shell** with tab-completion, command history, and a status bar showing the active project and user. Built-in shell commands:

| Command | Description |
|---------|-------------|
| `use PROJECT_ID` | Switch active project (tab-completes project IDs) |
| `unuse` | Clear active project and session |
| `refresh` | Re-fetch project list and user info |
| `reload` | Re-exec the process — picks up source code changes |
| `debug on` / `debug off` | Enable or disable debug logging for the current session |
| `debug` | Show current debug state |
| `help` | Print available commands |
| `exit` / `quit` | Leave the shell |

Use `crucible <resource> <action> --help` for full option details on any command.

---

## Setup

```bash
crucible config init          # First-time interactive setup (API key, URL, project)
crucible completion bash       # Install shell tab-completion (bash/zsh/fish)
```

Set a default project to avoid typing `-pid` on every command:
```bash
crucible config set current_project my-project
```

---

## Global Flags

| Flag | Effect |
|------|--------|
| `--debug` | Enable debug logging: HTTP calls, raw responses, tracebacks. Must come **before** the resource. |
| `--version` | Print version and exit. |

```bash
crucible --debug dataset list   # debug must precede the subcommand
```

---

## Dataset

| Command | Key options | Description |
|---------|-------------|-------------|
| `dataset list` | `-pid ID` `-m TYPE` `-k WORD` `--session NAME` `--limit N` `-v` | List datasets, with optional filters |
| `dataset get ID` | `-v` `--include-metadata` `-o json` | Get dataset details; `-v` shows ownership, file info, keywords, and associated files; `-o json` prints the raw record as JSON (always includes scientific metadata) |
| `dataset create -i FILE` | `-t TYPE` `-pid ID` `-n NAME` `-m TYPE` `--timestamp DATE` `--metadata JSON` `-k WORDS` `--session NAME` `--instrument NAME` `--public` `--mfid [ID]` `--dry-run` | Upload file(s) and create a dataset record |
| `dataset update ID` | `--set KEY=VALUE` `--metadata JSON` `--overwrite` | Update model fields (`--set`) and/or scientific metadata (`--metadata`) |
| `dataset list-files ID` | | List associated files with clickable download links (valid 1 hour) and sizes |
| `dataset add-file ID FILE` | | Upload and attach a file to an existing dataset |
| `dataset download ID` | `--output-dir DIR` `--include PATTERN` `--exclude PATTERN` `-f FILE` `--overwrite` | Download dataset files with optional glob filters (delegates to `crucible download`) |
| `dataset delete ID` | `-y` | Permanently delete a dataset (prompts for confirmation) |
| `dataset search QUERY` | `--limit N` `-v` | Search datasets by scientific metadata |
| `dataset link` | `-p PARENT_ID -c CHILD_ID` | Create a parent-child relationship between two datasets |
| `dataset add-sample ID` | `-s SAMPLE_ID` | Link a sample to this dataset |
| `dataset remove-sample ID` | `-s SAMPLE_ID` | Unlink a sample from this dataset *(admin)* |
| `dataset list-parents ID` | `--limit N` | List parent datasets |
| `dataset list-children ID` | `--limit N` | List child datasets |
| `dataset list-samples ID` | `--limit N` `-v` | List samples linked to a dataset |
| `dataset add-keyword ID WORD` | | Add a keyword tag |
| `dataset list-keywords ID` | `-v` | List keywords (with usage counts with `-v`) |
| `dataset parsers` | | List available client-side parsers |
| `dataset ingestors` | | List available server-side ingestors |

**Updatable fields** (via `--set`): `dataset_name`, `measurement`, `data_format`, `session_name`, `instrument_name`, `instrument_id`, `project_id`, `owner_orcid`, `source_folder`, `file_to_upload`, `public`, `timestamp`

```bash
# Upload a file (server assigns ID)
crucible dataset create -i data.csv -pid my-project

# Upload with a LAMMPS parser, metadata, and keywords
crucible dataset create -i run.lmp -t lammps -pid my-project \
    --metadata '{"temperature": 300}' --keywords "NVT,water"

# Update a field and scientific metadata in one command
crucible dataset update DSID --set measurement=XRD --metadata '{"pressure": 1.5}'

# Search scientific metadata
crucible dataset search "temperature" --limit 10
```

---

## Sample

| Command | Key options | Description |
|---------|-------------|-------------|
| `sample list` | `-pid ID` `--limit N` `-v` | List samples, with optional filters |
| `sample get ID` | `-v` `-o json` | Get sample details; `-v` shows linked datasets; `-o json` prints the raw record as JSON |
| `sample create` | `-n NAME` `-pid ID` `--type TYPE` `--description TEXT` `--timestamp DATE` | Create a new sample |
| `sample update ID` | `--set KEY=VALUE` | Update sample fields |
| `sample link` | `-p PARENT_ID -c CHILD_ID` | Create a parent-child relationship between two samples |
| `sample add-dataset ID` | `-d DATASET_ID` | Link a dataset to this sample |
| `sample remove-dataset ID` | `-d DATASET_ID` | Unlink a dataset from this sample *(admin)* |
| `sample list-parents ID` | `--limit N` | List parent samples |
| `sample list-children ID` | `--limit N` | List child samples |
| `sample list-datasets ID` | `--limit N` `-v` | List datasets linked to a sample |

**Updatable fields** (via `--set`): `sample_name`, `sample_type`, `description`, `project_id`, `owner_orcid`, `timestamp`

```bash
crucible sample create -n "Silicon Wafer A" -pid my-project --type substrate
crucible sample update SAMPLE_ID --set description="Annealed at 900C"
crucible sample add-dataset SAMPLE_ID --dataset DATASET_ID
```

---

## Project

| Command | Key options | Description |
|---------|-------------|-------------|
| `project list` | `--limit N` | List all accessible projects |
| `project get ID` | `-v` | Get project details |
| `project create` | `--project-id ID` `-o ORG` `-e EMAIL` `--title TEXT` `--lead-name NAME` `--status STATUS` | Create a project (interactive if args omitted) |
| `project list-users ID` | `--limit N` | List users in a project *(admin)* |
| `project add-user ID` | `--orcid ORCID` | Add a user to a project *(admin)* |

```bash
crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov"
crucible project list-users my-project
```

---

## Instrument

| Command | Key options | Description |
|---------|-------------|-------------|
| `instrument list` | `--limit N` | List all instruments |
| `instrument get NAME` | `--by-id` | Get instrument by name (or by ID with `--by-id`) |
| `instrument create` | `-n NAME` `--owner OWNER` `--location LOC` `--manufacturer MFR` `--model MODEL` `--type TYPE` `--description TEXT` | Create an instrument (interactive if args omitted) |

---

## User *(admin)*

| Command | Key options | Description |
|---------|-------------|-------------|
| `user list` | `--limit N` | List all users |
| `user get` | `--orcid ORCID` or `--email EMAIL` | Get a user |
| `user create` | `--orcid` `--first-name` `--last-name` `--email` `--lbl-email` `--projects` | Create a user (interactive if args omitted) |
| `user list-datasets ORCID` | | List dataset IDs accessible to a user |
| `user check-access ORCID DATASET_ID` | | Check read/write permissions for a user on a dataset |
| `user list-access-groups ORCID` | | List access groups a user belongs to |
| `user list-projects ORCID` | `-v` | List projects a user is associated with |

---

## Config

| Command | Description |
|---------|-------------|
| `config init` | Interactive setup wizard |
| `config show` | Print current configuration |
| `config get KEY` | Print a single config value |
| `config set KEY VALUE` | Set a config value |
| `config path` | Show config file path |
| `config edit` | Open config file in editor |

**Config keys:** `api_key`, `api_url`, `cache_dir`, `graph_explorer_url`, `current_project`

---

## Cache

| Command | Key options | Description |
|---------|-------------|-------------|
| `cache show` | `--top N` | Show cache path, total size, and top-N largest datasets |
| `cache clear` | `-y` `--older-than DAYS` `--dataset ID` | Delete cached files (all, by age, or a single dataset) |

```bash
crucible cache show                        # full breakdown
crucible cache show --top 20               # show 20 largest datasets
crucible cache clear --older-than 30       # remove entries not accessed in 30+ days
crucible cache clear --dataset DATASET_ID  # remove a single dataset
crucible cache clear -y                    # wipe entire cache without prompt
```

---

## Download

Download any resource by ID — auto-detects whether it is a sample or dataset.
Always saves the API record as `record.json`. For datasets, also downloads associated files unless `--no-files` is given.

| Command | Key options | Description |
|---------|-------------|-------------|
| `download ID` | `-o DIR` `--no-files` `--no-record` `--no-overwrite` `--include PATTERN` `--exclude PATTERN` | Download a sample or dataset |

```bash
crucible download mf-abc123                          # record.json + all files → crucible-downloads/
crucible download mf-abc123 --no-files               # record.json only, skip data files
crucible download mf-abc123 --no-record              # data files only, skip record.json
crucible download mf-abc123 --include "*.h5"         # only .h5 files
crucible download mf-abc123 -o my-dir                # custom output directory
crucible download mf-abc123 --exclude "*.log" "*.tmp"
```

Output structure (default `crucible-downloads/`):
```
crucible-downloads/
  <mfid>/
    record.json            ← API record + scientific metadata (one per resource, no overwrites)
  <mfid>/file1.h5          ← dataset files at their server-side paths (already include mfid)
  <mfid>/subdir/file2.dat
```

---

## Deletion

Soft-deletion workflow: users submit requests, admins approve or reject them. While a request is pending, the resource is hidden from list results.

| Command | Key options | Description |
|---------|-------------|-------------|
| `deletion request RESOURCE_ID` | `-m TEXT` | Submit a deletion request for a dataset or sample |
| `deletion list` | `--approved` `--rejected` `--all` | List deletion requests, pending by default *(admin)* |
| `deletion get REQUEST_ID` | | Get a single deletion request by integer ID *(admin)* |
| `deletion approve REQUEST_ID` | `-m TEXT` | Approve a pending deletion request *(admin)* |
| `deletion reject REQUEST_ID` | `-m TEXT` | Reject a pending deletion request — resource is restored *(admin)* |

```bash
crucible deletion request mf-abc123 -m "Duplicate upload"
crucible deletion list
crucible deletion list --approved
crucible deletion approve 42 -m "Confirmed duplicate"
crucible deletion reject 42 -m "Still in use"
```

---

## Linking & Utilities

| Command | Description |
|---------|-------------|
| `status` | Check API connectivity, auth, and active config |
| `whoami` | Show current user info for the active API key |
| `link -p PARENT -c CHILD` | Link two resources (type auto-detected via API) |
| `link -d DATASET -s SAMPLE` | Link a sample to a dataset |
| `unlink -p ID -c ID` | Unlink two resources (dataset-sample only, type auto-detected) |
| `unlink -d DATASET -s SAMPLE` | Unlink a sample from a dataset *(admin)* |
| `open [MFID]` | Open Graph Explorer in browser (or a specific resource by ID) |
| `open MFID --print-url` | Print the URL instead of opening |

---

## Deprecated aliases

These still work but print a warning — use the new names:

| Old | New |
|-----|-----|
| `dataset update-metadata` | `dataset update --metadata` |
| `dataset get-keywords` | `dataset list-keywords` |
| `sample link-dataset` | `sample add-dataset` |
| `user get-access-groups` | `user list-access-groups` |
| `user get-projects` | `user list-projects` |
| `project get-users` | `project list-users` |
