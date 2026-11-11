# AccountOperations

Access via `client.account`. Self-service operations — no admin required.

::: crucible.resources.account.AccountOperations
    options:
      members:
        - whoami
        - profile
        - update_profile
        - create_api_key
        - list_api_keys
        - rename_api_key
        - revoke_api_key
        - verify
        - join_requests
        - sync_projects
