# CrucibleClient

The main entry point for the nano-crucible Python API. Instantiating `CrucibleClient` loads credentials from config or environment variables and initializes all resource namespaces.

```python
from crucible import CrucibleClient

client = CrucibleClient()
# or with explicit credentials:
client = CrucibleClient(api_key="your-key")
```

## Resource namespaces

| Attribute | Type | Description |
|---|---|---|
| `client.datasets` | `DatasetOperations` | Dataset CRUD, file upload/download, thumbnails, metadata |
| `client.samples` | `SampleOperations` | Sample CRUD, hierarchies, dataset links |
| `client.projects` | `ProjectOperations` | Project CRUD, user management |
| `client.instruments` | `InstrumentOperations` | Instrument CRUD |
| `client.users` | `UserOperations` | User management (admin) |
| `client.files` | `FileOperations` | File lookup, download, and ingestion by MFID |
| `client.account` | `AccountOperations` | Self-service profile, API key, verification |
| `client.ingestions` | `IngestionOperations` | Ingestion request management |
| `client.graphs` | `GraphOperations` | Entity graph traversal |
| `client.deletions` | `DeletionOperations` | Deletion request management |

## Privilege mode

Administrative endpoints distinguish normal ACL-derived authorization from explicit platform-administrator elevation. Pass `privilege_mode="elevated"` to send the `Crucible-Privilege-Mode` header on every request, or set the `privilege_mode` config key or `CRUCIBLE_PRIVILEGE_MODE` environment variable. When none is set, no header is sent and the server default applies.

```python
client = CrucibleClient(privilege_mode="elevated")
```

## Reference

::: crucible.client.CrucibleClient
    options:
      members:
        - __init__
        - health
        - live
        - whoami
        - get
        - get_resource_type
        - get_links
        - link
        - unlink
