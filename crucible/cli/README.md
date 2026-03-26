# Crucible CLI Cheat Sheet

The `crucible CLI` provides command-line access to Crucible. Commands follow the pattern:

```
crucible [--debug] <resource> <action> [options]
```

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
| `dataset get ID` | `-v` `--include-metadata` | Get dataset details; `-v` shows keywords and linked samples |
| `dataset create -i FILE` | `-t TYPE` `-pid ID` `-n NAME` `-m TYPE` `--metadata JSON` `-k WORDS` `--session NAME` `--instrument NAME` `--public` `--mfid [ID]` `--dry-run` | Upload file(s) and create a dataset record |
| `dataset update ID` | `--set KEY=VALUE` `--metadata JSON` `--overwrite` | Update model fields (`--set`) and/or scientific metadata (`--metadata`) |
| `dataset download ID` | `--output-dir DIR` `--include PATTERN` `--exclude PATTERN` `-f FILE` `--overwrite` | Download dataset files with optional glob filters |
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

**Updatable fields** (via `--set`): `dataset_name`, `measurement`, `data_format`, `session_name`, `instrument_name`, `instrument_id`, `project_id`, `owner_orcid`, `source_folder`, `file_to_upload`, `json_link`, `public`, `timestamp`

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
| `sample get ID` | `-v` | Get sample details; `-v` shows linked datasets |
| `sample create` | `-n NAME` `-pid ID` `--type TYPE` `--description TEXT` | Create a new sample |
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

## Linking & Utilities

| Command | Description |
|---------|-------------|
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
