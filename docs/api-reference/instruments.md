# InstrumentOperations

Access via `client.instruments`.

Store instruments by MFID (`unique_id`). The instrument slug (`instrument_id`) is for human lookup and ignores case; every method that takes an instrument reference accepts either. `instrument_name` is free-text display, may repeat, and must not be used to identify an instrument.

An instrument's owner and maintainers manage the instrument record (`get_users()`, `add_user()`, `remove_user()`, `update_user_role()`). Maintainer roles never grant access to the instrument's datasets; only service accounts bound with `bind_service_account()` reach those.

::: crucible.resources.instruments.InstrumentOperations
    options:
      members:
        - list
        - get
        - search
        - create
        - update
        - set_status
        - get_users
        - add_user
        - remove_user
        - update_user_role
        - list_service_accounts
        - bind_service_account
        - unbind_service_account
        - list_access
        - set_access
        - revoke_access
        - set_public
        - set_private
        - transfer_ownership
