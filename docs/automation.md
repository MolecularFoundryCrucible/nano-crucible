# Automation and coding agents

The Crucible client can be used from scripts, notebooks, CI jobs, and coding agents. The same rule applies in every environment: keep credentials out of code and make live data changes deliberate.

## Choose the CLI or Python API

Use the CLI for interactive work, shell scripts, and quick inspection:

```bash
crucible status
crucible whoami
crucible dataset list --project-id my-project --limit 20
crucible dataset get DATASET_ID
```

Use Python when you need control flow, data transformation, or integration with
another application:

```python
from crucible import CrucibleClient

client = CrucibleClient()
for dataset in client.datasets.list(project_id="my-project", limit=20):
    print(dataset["unique_id"], dataset.get("dataset_name"))
```

The 3.x client uses resource namespaces: `client.datasets`, `client.samples`, `client.projects`, `client.instruments`, `client.files`, and others. Flat methods from older releases, such as `client.get_dataset()`, have been removed.

## Supply credentials safely

For a workstation, initialize the platform-specific config file:

```bash
crucible config init
```

For CI or another non-interactive environment, inject credentials through its
secret manager:

```bash
export CRUCIBLE_API_KEY="..."
```

Nano uses its packaged production API URL by default, allowing client upgrades to adopt the matching production API version. Set `CRUCIBLE_API_URL` only for staging or another non-default deployment.

Do not commit API keys, place them in notebooks, include them in prompts, or print the full client configuration. Use `crucible whoami` to verify identity without displaying the key.

## Separate reads from writes

These common operations read from Crucible without changing records:

- `status`, `whoami`, `get`, `list`, and `search`
- listing files, links, metadata, access entries, or ingestion requests
- downloading records and files to a new local destination

These operations change the live service and should have an explicit target and purpose:

- creating or updating datasets, samples, projects, instruments, or users
- uploading files or cataloging external file locations
- linking resources or changing scientific metadata
- changing public visibility, granting access, reassigning projects, or transferring ownership
- requesting ingestion or deletion

For unattended automation, log the operation, project ID, and affected resource ID. Do not log authorization headers, API keys, signed download URLs, or sensitive local paths.

## Create records predictably

Use Pydantic models for shared fields and a separate dictionary for flexible scientific metadata:

```python
from crucible import CrucibleClient
from crucible.models import Dataset

client = CrucibleClient()
result = client.datasets.create(
    Dataset(
        dataset_name="XRD measurement",
        measurement="X-ray diffraction",
        project_id="my-project",
    ),
    scientific_metadata={"temperature_K": 300},
    keywords=["XRD"],
    files=["xrd_data.xy"],
)

print(result["dataset_mfid"])
```

String paths in `files` are uploaded to Crucible storage by default. To register paths without uploading their contents, set `upload_files=False`. To catalog a file held by an external system, pass an `AssociatedFile` with its `storage_backend`, `storage_path`, and any access instructions. Choose these modes intentionally: a catalog entry does not make an external file accessible to another user by itself.

An omitted `ingestor` lets the server detect a supported format. If detection
fails, inspect the server-advertised choices with:

```bash
crucible dataset ingestors
```

## Make agent-assisted work reviewable

When asking a coding agent to operate Crucible, include the API environment and project name, whether it may perform writes, and the desired resource relationships. Do not include credentials. A useful request is:

> Using my configured test account, list datasets in `my-project` and propose the sample links. Do not create or change anything until I approve the proposed links.

This gives the agent enough context to inspect safely while reserving the live
mutation for review. The repository also ships a reusable agent skill at
`skills/nano-crucible/SKILL.md` with client-specific operating guidance.
