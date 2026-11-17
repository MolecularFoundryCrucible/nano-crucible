# Upgrading to 4.0

nano-crucible 4.0 removes everything that 3.x deprecated, follows the Crucible API 4.0 contract, and changes a few defaults. This page lists what existing scripts and habits need to change; the [changelog](changelog.md) has every change.

## Before you upgrade

- Use Python 3.11 or later.
- Use a Crucible API at version 4.0 or later. The client relies on routes that older servers lack, such as signed multipart uploads, project join requests, instrument members, and `owner_ref`; keep nano-crucible 3.3 for a 3.x server.
- Run your scripts on 3.3 with `python -W default::DeprecationWarning`. Every method and keyword it warns about is removed in 4.0; the few removals that never warned are listed below.

## Removed

Calling a removed method, keyword, or setting raises `crucible.RemovedError`, a `TypeError` whose message names the replacement. Removed CLI commands and options stop with the one to use; the [CLI reference](cli/reference.md#removed-in-400) lists them.

These were removed without an earlier deprecation:

| Removed | Use instead |
|---|---|
| `datasets.request_carrier_segmentation()`, `request_insitu_aggregation()`, `request_rga_analysis()`, `request_mosaic_stitch()` | `datasets.postprocess(dataset_mfid, pipeline)` |
| `users.verify_api_key()` | `users.get(user)['api_key_status']` |
| `instruments.set_access()`, `instruments.revoke_access()` | `instruments.add_user()`, `update_user_role()`, `remove_user()` |
| `upload_file_gcs_multipart()`, `upload_file_gcs_resumable()` | `upload_file_gcs()`, or `datasets.add_file()` |
| `google-cloud-storage`, installed with nano-crucible | install it yourself if your code imports it |
| The basic shell used when prompt_toolkit is missing | reinstall nano-crucible |

The settings `graph_explorer_url`, `current_session`, `upload_protocol`, and `upload_chunk_size_mb` are ignored; `config show` lists them and `config unset` removes them. Setting `CRUCIBLE_CURRENT_PROJECT` stops the CLI; pass `--project-id` instead.

## Results with a new shape

- Instrument member methods and `Instrument.members` return `ProjectMember` records (username, name, role) instead of `AccessGrant` records.
- `samples.get()` and `client.get()` no longer include a sample's datasets. Pass `include_links=True`, or call `datasets.list(sample_mfid=...)`.
- `datasets.create()` results name the new dataset `dataset_mfid` instead of `dsid`, and `get_links()` results use `direction` instead of `relationship`.
- `AccessGrant` exposes `principal_id`, `principal_type`, and `permission` instead of `principal`, `kind`, and `effective_permission`.
- Records carry nested `owner`, `project`, and `instrument` references. The API deprecates the flat `owner_orcid`, `project_id`, `instrument_id`, and `instrument_name` response fields, and `lead` and `project_lead_orcid` on projects.
- API errors raise `crucible.CrucibleAPIError` with `status`, `code`, `detail`, and `request_id`. It is a `requests.HTTPError`, so existing `except` blocks still catch it. A client created without an API key or stored sign-in raises `crucible.NotSignedInError`, a `ValueError` as before.

## New defaults

- Instrument `add_user()` and `instrument add-user` give new members `viewer` instead of `editor`.
- A signed-in platform administrator runs in normal mode; an administrator's API key still runs elevated. Set `privilege_mode` to choose explicitly, and check `client.is_elevated` or `crucible whoami`.
- Create and update requests (POST and PATCH) without an `Idempotency-Key` are not retried after a 502, 503, 504, or lost response, so a retry cannot create a duplicate record.
- Links and `crucible open` go to the Crucible Hub (`hub_url`) instead of the Graph Explorer.
- A cast recipe's `instrument` is an instrument ID or MFID, not a name.

## Renamed, still working

Old names keep working with a warning (a `DeprecationWarning` in Python, a notice on stderr in the CLI) and will be removed in a later release. The ones scripts meet most often:

| Old | New |
|---|---|
| `owner_id`, `owner_id_is_null` filters | `owner_ref` (up to 10 owners), `owner_is_null` |
| `project_lead`, `project_lead_orcid`, `project_lead_email`, `project_lead_username` on project create | `owner` |
| `project create --lead` | `project create --owner` |
| `datasets.graph()`, `samples.graph()` | `graphs.get()` |
| `include_datasets=True` on `samples.get()` | `include_links=True` |

The changelog's "Changed" section lists the remaining method, parameter, and command renames.
