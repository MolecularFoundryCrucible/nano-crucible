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
        - list_datasets
        - check_dataset_access
        - list_access_groups
        - add_to_access_group
        - remove_from_access_group
        - get_projects
        - verify_api_key
        - set_platform_role
        - revoke_api_keys
