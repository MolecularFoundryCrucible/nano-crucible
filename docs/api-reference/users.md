# UserOperations

Access via `client.users`.

!!! note
    Most user management operations require admin privileges.

For self-service profile and API key operations see `client.account`.

::: crucible.resources.users.UserOperations
    options:
      members:
        - get
        - search
        - list
        - resolve
        - create
        - update
        - approve
        - reject
        - check_dataset_access
        - list_access_groups
        - list_projects
        - set_platform_role
        - list_api_keys
        - revoke_api_key
        - revoke_api_keys
