# CrucibleClient

The main entry point for the nano-crucible Python API. Instantiating `CrucibleClient` loads credentials from config or environment variables and initializes all resource namespaces.

```python
from crucible import CrucibleClient

client = CrucibleClient()
# or with explicit credentials:
client = CrucibleClient(api_url="https://crucible.lbl.gov/api/v2", api_key="your-key")
```

## Resource namespaces

| Attribute | Type | Description |
|---|---|---|
| `client.datasets` | `DatasetOperations` | Dataset CRUD, file upload, metadata, ingestion |
| `client.samples` | `SampleOperations` | Sample CRUD, hierarchies, dataset links |
| `client.projects` | `ProjectOperations` | Project CRUD, user management |
| `client.instruments` | `InstrumentOperations` | Instrument CRUD |
| `client.users` | `UserOperations` | User management (admin) |
| `client.graphs` | `GraphOperations` | Entity graph traversal |
| `client.deletions` | `DeletionOperations` | Deletion request management |

## Reference

::: crucible.client.CrucibleClient
    options:
      members:
        - __init__
        - health
        - whoami
        - get
        - get_resource_type
        - get_links
        - link
        - unlink
        - download
