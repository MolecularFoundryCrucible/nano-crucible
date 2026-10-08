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

Endpoints distinguish normal ACL-derived authorization from explicit platform-administrator elevation, selected with the `Crucible-Privilege-Mode` header. By default the client sends no header, so the server applies its legacy behavior: a platform administrator runs elevated and sees every record, and everyone else gets their normal, ACL-derived access. `client.is_elevated` reports which applies.

Pass `privilege_mode="normal"` to see only what you can access through your own memberships and grants, or `"elevated"` to request elevation explicitly. The `privilege_mode` config key and `CRUCIBLE_PRIVILEGE_MODE` environment variable set the same thing.

```python
client = CrucibleClient(privilege_mode="normal")
```

A future release will default to `normal`. Platform administrators who rely on seeing every record should set `privilege_mode = elevated` now.

Administrator-only operations, such as service-account administration and deletion review, request elevation per call, so they work without elevating the whole client. Requesting elevation as an ineligible caller is rejected with a 403, so those calls elevate only when `client.can_elevate` is true.

## Authorization and capabilities

`client.authorization` (an `AccountAuthorization`) and `client.capabilities` (an `AccountCapabilities`) expose the caller's platform role and account-level permissions. They are read once from `/account/profile` and cached; call `client.refresh_profile()` to re-read them, for example after changing `privilege_mode` or after an administrator changes your role.

```python
if client.capabilities.can_create_project:
    client.projects.create(...)
```

A flag the profile did not report is `None`, so check for an explicit `False` before refusing; otherwise attempt the operation and let the API decide.

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
