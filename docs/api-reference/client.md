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

Endpoints distinguish normal ACL-derived authorization from explicit platform-administrator elevation, selected with the `Crucible-Privilege-Mode` header. The client sends `normal` by default, so ordinary reads and writes return what the caller can actually access. Omitting the header instead makes the server apply legacy behavior, which for a platform administrator means elevated, so the default is sent explicitly rather than left off.

Pass `privilege_mode="elevated"` to elevate every request, or set the `privilege_mode` config key or `CRUCIBLE_PRIVILEGE_MODE` environment variable.

```python
client = CrucibleClient(privilege_mode="elevated")
```

Administrator-only operations, such as service-account administration and deletion review, request elevation per call, so they work without elevating the whole client. Requesting elevation as an ineligible caller is rejected with a 403, so those calls elevate only when `client.can_elevate` is true.

## Authorization and capabilities

`client.authorization` and `client.capabilities` expose the caller's platform role and account-level permissions, read once from `/account/profile` in normal mode and cached. Use them to decide whether an action is worth attempting.

```python
if client.capabilities.get("can_create_project"):
    client.projects.create(...)
```

Both return an empty dict if the profile cannot be read, so callers degrade to attempting the operation and letting the API decide.

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
