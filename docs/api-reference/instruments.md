# InstrumentOperations

Access via `client.instruments`.

Store instruments by MFID (`unique_id`). The instrument slug (`instrument_id`) is for human lookup and ignores case; every method that takes an instrument reference accepts either. `instrument_name` is free-text display, may repeat, and must not be used to identify an instrument.

Instrument members work like project members (`list_users()`, `add_user()`, `remove_user()`, `update_user_role()`, each returning `ProjectMember` records): every member reads the instrument's datasets, `editor` also edits details, and `admin` also changes status, binds service accounts, and manages members. Service accounts are bound with `bind_service_account()` instead. `set_access()` and `revoke_access()` raise `RemovedError` for instruments; `list_access()`, `set_public()`, and `set_private()` still work.

::: crucible.resources.instruments.InstrumentOperations
    options:
      inherited_members: true
      members:
        - list
        - get
        - search
        - create
        - update
        - set_status
        - list_users
        - add_user
        - remove_user
        - update_user_role
        - list_service_accounts
        - bind_service_account
        - unbind_service_account
        - list_access
        - set_public
        - set_private
        - transfer_ownership
