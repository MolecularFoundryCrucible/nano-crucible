# ServiceAccountOperations

Access via `client.service_accounts`. Service accounts are non-human users for instruments and automated pipelines. `get_admin()`, `list_admin()`, and `set_platform_role()` are for platform administrators and elevate on their own.

```python
account = client.service_accounts.create("xrd-uploader")
rotated = client.service_accounts.rotate_key(account["unique_id"])
```

::: crucible.resources.service_accounts.ServiceAccountOperations
    options:
      members:
        - create
        - rotate_key
        - get
        - list
        - update
        - list_access_groups
        - get_admin
        - list_admin
        - set_platform_role
