# CLI Command Reference

Use `crucible <resource> <action> --help` for full option details on any command.

---

## dataset

| Command | Key options | Description |
|---|---|---|
| `dataset list` | `-pid ID` `-m TYPE` `-k WORD` `--session NAME` `--limit N` `-v` | List datasets with optional filters |
| `dataset get ID` | `-v` `--include-metadata` `-o json` | Get dataset details; `-v` shows ownership, file info, keywords; `-o json` prints raw record |
| `dataset create -i FILE` | `-t TYPE` `-pid ID` `-n NAME` `-m TYPE` `--timestamp DATE` `--metadata JSON` `-k WORDS` `--session NAME` `--instrument NAME` `--public` `--mfid [ID]` `--dry-run` | Upload file(s) and create a dataset record |
| `dataset update ID` | `--set KEY=VALUE` `--metadata JSON` `--overwrite` | Update model fields (`--set`) and/or scientific metadata (`--metadata`) |
| `dataset list-files ID` | | List associated files with download links and sizes |
| `dataset add-file ID FILE` | | Upload and attach a file to an existing dataset |
| `dataset download ID` | `--output-dir DIR` `--include PATTERN` `--exclude PATTERN` `-f FILE` `--overwrite` | Download dataset files |
| `dataset delete ID` | `-y` | Permanently delete a dataset (prompts for confirmation) |
| `dataset search QUERY` | `--limit N` `-v` | Search datasets by scientific metadata |
| `dataset link` | `-p PARENT_ID -c CHILD_ID` | Create a parent-child link between two datasets |
| `dataset add-sample ID` | `-s SAMPLE_ID` | Link a sample to a dataset |
| `dataset remove-sample ID` | `-s SAMPLE_ID` | Unlink a sample from a dataset |
| `dataset list-parents ID` | `--limit N` | List parent datasets |
| `dataset list-children ID` | `--limit N` | List child datasets |
| `dataset list-samples ID` | `--limit N` `-v` | List samples linked to a dataset |
| `dataset add-keyword ID WORD` | | Add a keyword tag |
| `dataset list-keywords ID` | `-v` | List keywords (with usage counts with `-v`) |
| `dataset parsers` | | List available client-side parsers |
| `dataset ingestors` | | List available server-side ingestors |

**Updatable fields** (via `--set`): `dataset_name`, `measurement`, `data_format`, `session_name`, `instrument_name`, `instrument_id`, `project_id`, `owner_orcid`, `source_folder`, `file_to_upload`, `public`, `timestamp`

```bash
# Upload a file
crucible dataset create -i data.csv -pid my-project

# Upload with metadata and keywords
crucible dataset create -i run.lmp -t lammps -pid my-project \
    --metadata '{"temperature": 300}' --keywords "NVT,water"

# Update a field and scientific metadata
crucible dataset update DSID --set measurement=XRD --metadata '{"pressure": 1.5}'

# Search scientific metadata
crucible dataset search "temperature" --limit 10
```

---

## sample

| Command | Key options | Description |
|---|---|---|
| `sample list` | `-pid ID` `--limit N` `-v` | List samples |
| `sample get ID` | `-v` `-o json` | Get sample details; `-v` shows linked datasets |
| `sample create` | `-n NAME` `-pid ID` `--type TYPE` `--description TEXT` `--timestamp DATE` | Create a new sample |
| `sample update ID` | `--set KEY=VALUE` | Update sample fields |
| `sample link` | `-p PARENT_ID -c CHILD_ID` | Create a parent-child relationship |
| `sample add-dataset ID` | `-d DATASET_ID` | Link a dataset to a sample |
| `sample remove-dataset ID` | `-d DATASET_ID` | Unlink a dataset from a sample |
| `sample list-parents ID` | `--limit N` | List parent samples |
| `sample list-children ID` | `--limit N` | List child samples |
| `sample list-datasets ID` | `--limit N` `-v` | List datasets linked to a sample |

**Updatable fields** (via `--set`): `sample_name`, `sample_type`, `description`, `project_id`, `owner_orcid`, `timestamp`

```bash
crucible sample create -n "Silicon Wafer A" -pid my-project --type substrate
crucible sample update SAMPLE_ID --set description="Annealed at 900C"
crucible sample add-dataset SAMPLE_ID -d DATASET_ID
```

---

## project

| Command | Key options | Description |
|---|---|---|
| `project list` | `--limit N` | List all accessible projects |
| `project get ID` | `-v` | Get project details |
| `project create` | `--project-id ID` `-o ORG` `-e EMAIL` `--title TEXT` `--lead-name NAME` `--status STATUS` | Create a project (interactive if args omitted) |
| `project list-users ID` | `--limit N` | List users in a project |
| `project add-user ID` | `--orcid ORCID` | Add a user to a project |

```bash
crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov"
crucible project list-users my-project
```

---

## instrument

| Command | Key options | Description |
|---|---|---|
| `instrument list` | `--limit N` | List all instruments |
| `instrument get NAME` | `--by-id` | Get instrument by name (or by ID with `--by-id`) |
| `instrument create` | `-n NAME` `--owner OWNER` `--location LOC` `--manufacturer MFR` `--model MODEL` `--type TYPE` `--description TEXT` | Create an instrument (interactive if args omitted) |

---

## user *(admin)*

| Command | Key options | Description |
|---|---|---|
| `user list` | `--limit N` | List all users |
| `user get` | `--orcid ORCID` or `--email EMAIL` | Get a user |
| `user create` | `--orcid` `--first-name` `--last-name` `--email` `--projects` | Create a user (interactive if args omitted) |
| `user list-datasets ORCID` | | List dataset IDs accessible to a user |
| `user check-access ORCID DATASET_ID` | | Check read/write permissions for a user |
| `user list-access-groups ORCID` | | List access groups a user belongs to |
| `user list-projects ORCID` | `-v` | List projects associated with a user |

---

## Utility commands

| Command | Key options | Description |
|---|---|---|
| `download ID` | `--output-dir DIR` `--include PATTERN` `--exclude PATTERN` `--no-files` `--overwrite` | Download a dataset or sample by ID |
| `link PARENT_ID CHILD_ID` | | Link two resources (type auto-detected) |
| `unlink ID_A ID_B` | | Unlink two resources |
| `open ID` | | Open a resource in the Crucible web explorer |
| `get ID` | `-v` `-o json` | Get any resource by ID |
| `whoami` | | Show account info for the current API key |
| `status` | | Check API health |
| `tree ID` | | Display the relationship graph for a resource |

---

## config

| Command | Description |
|---|---|
| `config init` | Interactive setup wizard |
| `config show` | Print current configuration |
| `config get KEY` | Print a single config value |
| `config set KEY VALUE` | Set a config value |
| `config path` | Show config file path |
| `config edit` | Open config file in editor |

**Config keys:** `api_key`, `api_url`, `cache_dir`, `graph_explorer_url`, `current_project`

---

## cache

| Command | Key options | Description |
|---|---|---|
| `cache show` | `--top N` | Show cache path, size, and top-N largest datasets |
| `cache clear` | `-y` `--older-than DAYS` `--dataset ID` | Delete cached files |

```bash
crucible cache show --top 20
crucible cache clear --older-than 30
crucible cache clear --dataset DATASET_ID
crucible cache clear -y    # wipe everything
```
