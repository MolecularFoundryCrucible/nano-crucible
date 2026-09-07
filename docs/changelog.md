# Changelog

## Unreleased

### Added

- Dataset-to-dataset and sample-to-sample links can record a `relationship_type` of `is_derived_from` or `is_part_of`, describing the child relative to the parent. It is optional, settable through `link_parent_child()`, `samples.link()`, `client.link()`, and `--relationship-type` on `crucible link`, `dataset link`, and `sample link`, and filterable on `list_parents()` and `list_children()`. Re-linking an existing pair without it preserves the stored type. Dataset-sample associations are undirected and reject it.
- The interactive shell displays a centered compact pixel-art Crucible banner on a light-blue panel on terminals wide enough to show it.
- Sample responses expose a typed project reference when supplied by the API, while retaining the flat project ID fallback.
- Dataset responses expose typed project and instrument references with canonical MFIDs while retaining legacy flat fields.
- The CLI supports `--no-color` and the standard `NO_COLOR` environment variable.
- Instrument operations can list bound service accounts and change lifecycle status through the dedicated API routes.
- Dataset listing accepts a canonical instrument MFID in the Python client and CLI without implicitly narrowing to the saved current project.
- Exact dataset, sample, project, and instrument responses expose typed caller-specific resource capabilities when supplied by the API.

### Changed

- **Breaking:** entries returned by `client.get_links()` renamed `relationship` to `direction` and changed its values from `parent`/`child`/`associated` to `source`/`target`/`undirected`. The meaning is unchanged — links are stored parent to child, so `source` is a parent of the resource you asked about and `target` is a child — but the new name no longer collides with `relationship_type`, which is a different thing: `direction` is computed per query and flips depending on which end you read from, while `relationship_type` is stored on the link and always reads child-relative-to-parent. There is no compatibility alias; code reading `link['relationship']` must be updated.
- Python resource namespaces now use `publish()` and `unpublish()` for public access; `set_public()` and `unset_public()` remain as deprecated compatibility aliases.
- The interactive shell now remembers the project selected by `use PROJECT_ID`, `unuse` clears it, and project context sources are visible; `CRUCIBLE_CURRENT_PROJECT` is deprecated because it can silently redirect operations.
- The interactive shell status bar now renders the Crucible dark blue, light blue, and orange brand palette in true color on capable terminals while keeping autocomplete menus visually plain.
- Sample detail methods can suppress the deprecated embedded dataset expansion; existing Python and JSON behavior remains compatible, while human CLI workflows avoid loading it.
- CLI colors now consistently distinguish clickable navigation, identifiers, statuses, roles, and secondary context; project IDs, instrument IDs, and usernames are treated as plain slugs when another field carries navigation.
- CLI user identifiers and owner names now link to Crucible Explorer profiles instead of external ORCID pages.
- Resource detail views group identity, project, instrument, access, and timing fields; related labels link to the Explorer without displaying related MFIDs, and human names use given-name initials.
- Generic `crucible get MFID` now renders projects in addition to datasets, samples, and instruments.
- CLI project and sample-type options use consistent canonical flags, and interactive completion now discovers flags and searches resource endpoints for identifier values.
- CLI failures now preserve HTTP status codes while formatting API validation details and warnings for readable terminal and JSON output.
- Human and service-account creation now normalize usernames and validate the API's complete username rules before submitting a request, with immediate retry prompts during interactive creation.
- Project membership methods and commands validate named roles before requests, document strict lower-role management and owner-or-self removal, and `project add-user` reports API errors through the shared status-preserving formatter.
- Interactive creation and configuration prompts now share required, optional, default, secret, and choice handling; invalid values prompt again, API keys remain hidden, and missing required input fails clearly outside a terminal.
- Destructive CLI confirmations now use consistent yes-or-no handling, default to cancellation, and require `--yes` when no interactive terminal is available.
- Resource detail views now distinguish slugs from MFIDs, format nullable booleans and statuses consistently, and show project timing and member expansion clearly.
- CLI tables now adapt to terminal width while preserving full usernames, resource slugs, and MFIDs whenever space permits.
- Project listing, resource searches, user discovery, and service-account retrieval now support raw JSON output with structured JSON validation errors.
- Empty CLI listings now identify the resource or request type instead of displaying generic placeholder text.
- CLI mutations now use consistent `Success:` messages, while compact status checks retain TTY-only symbols with text fallbacks for redirected output.
- `crucible status` now shows the configured endpoint, readiness state, client and API versions, deployed branch and commit, database latency and schema revisions, and authenticated identity.
- Instrument search accepts an optional lifecycle-status filter in the Python client and CLI.
- Instrument creation guidance now reflects that human callers may register instruments while service accounts may not.
- Project member tables use role-priority ordering and semantic role colors, display the owner as the project lead, and the interactive shell status bar again identifies project, user, and API context with symbols.
- Dataset and sample relationship listing now uses canonical collection filters with cursor pagination instead of deprecated nested read routes.

### Fixed

- Instrument creation no longer sends inherited response-only fields rejected by API v3.

## 3.2.0

### Added
- `add_file(skip_ingestion=True)` uploads a file without requesting ingestion. Updates ingestion request table with provenance details for local parsing. 
- Dataset, sample, and project lists accept repeated user and project access selectors.
- Development skills for API, CLI, parser, and cast changes.
- Agent-agnostic contributor guidance and a skill for safe client workflows.
- New `file request-ingestion` CLI command to (re)request ingestion for a cataloged file.
- New `client.datasets.add_remote_file()` and `client.files.update()` to catalog files that live outside GCS (Globus, NERSC, a shared filesystem) without uploading them.
- `dataset create --no-upload`/`--backend`/`--access-note` to catalog files by path instead of uploading them.
- New `ag get` command and `client.access_groups.get()`.
- Shell autocomplete for `ag` request IDs.
- Shell autocomplete extended to more `user`/`project`/`sa`/`ag` commands.
- Shell autocomplete for `instrument get` and `--project`/`-pid` flags.
- Shell autocomplete for dataset/sample IDs across most subcommands.
- Shell autocomplete for `user search` shows live matches while typing.
- New `dataset`/`sample`/`project reassign-project` and `transfer-ownership` commands.
- New `dataset`/`sample`/`project access list`/`grant`/`revoke` and `publish`/`unpublish` commands.
- New `project update-user-role` command and `add-user --role` flag.
- `project list-users` now shows each member's role.
- `instrument create` requires a new `--instrument-id` flag (a unique slug, separate from its ID and name).
- `project get --include-members` shows the project's member list and roles; `--members` remains as a deprecated alias.
- `project create`/`client.projects.create()` accept a flexible `project_lead` field as an alternative to the explicit ORCID/email/username fields.

### Changed

- The built-in production endpoint now targets API v3; explicit v1/v2 overrides display a migration warning, and `config unset api_url` restores the package default.
- Instrument retrieval expands typed public owner records by default; instrument lists support owner expansion and lifecycle-status filtering.
- Instrument creation defaults ownership to the authenticated identity, while ownership changes use `transfer_ownership()` and `instrument transfer-ownership` instead of update fields.
- Human users may be created without an ORCID, receiving a server-assigned MFID that user and owner displays treat as a canonical user ID rather than an ORCID.
- User operations that require a canonical identity use `user_unique_id`; the previous `orcid` keyword remains temporarily supported with a deprecation warning.
- Health checks and `crucible status` accept deployment provenance from the nested API readiness response while remaining compatible with the legacy flat response during rollout.
- Singleton dataset and sample retrieval expands typed public owner records by default; `owner_orcid` creation inputs are deprecated in favor of flexible `owner` identifiers.
- Project membership mutations resolve usernames and emails before using canonical user identifiers; the old `orcid` keyword remains temporarily supported.
- Generic access-group mutation helpers and CLI commands are deprecated in favor of typed resource, project, and instrument operations.
- Exact user lookups show email to self and platform administrators and omit the email row when it is not disclosed; other user, project-lead, member, and operator views remain public-safe.
- `user list-datasets` now uses the canonical paginated dataset collection and supports `--limit`.
- `client.users.check_dataset_access()` and `user check-access` now report the canonical effective access role.
- MFID-only parameters now use role-specific `_mfid` names, including `parent_mfid` and `child_mfid`; project and instrument slugs retain `_id`, and previous keywords remain temporarily supported.
- Resource lookups now dispatch canonical MFIDs to single-resource routes and resolve project slugs, instrument slugs, usernames, and emails through exact collection filters without a second request. Returned records retain `unique_id` as their canonical identifier.
- README now focuses on installation, navigation, and project essentials.
- CLI reference now documents all command families from one canonical location.
- `dataset get`/`dataset list-files` now show each file's MFID alongside its name.
- `dataset get` shows a dataset's files by default; no longer requires `--verbose`.
- `datasets.create()`'s `files_to_upload` renamed to `files` (accepts a mix of local paths and `AssociatedFile` objects); old name still works with a deprecation warning.
- `ag list`/`ag mine` now default to pending requests, matching `deletion list`.
- `deletion list` and `ag list`/`ag mine` share one `--status` flag.
- `ag approve`/`ag reject` accept multiple request IDs.
- Shell username autocomplete now works for non-admins and completes to username.
- Broken third-party parsers now log a warning instead of silently disappearing.
- `project update` no longer accepts `--lead-email`/`--lead-orcid`; use `project transfer-ownership` instead.
- `project update --project-id` now renames the project.
- `sample update` no longer accepts `--project`/`--owner`; use `sample reassign-project`/`transfer-ownership` instead.
- `dataset update`/`sample update --set` no longer accept `project_id`/`owner_orcid`; use the new reassign/transfer commands instead.
- Generic access grants accept roles up to `admin`; ownership changes use `transfer-ownership`.
- Dataset update fields now match the supported mutation contract: `data_format` is editable, while unsupported `description` and frozen instrument-assignment fields are excluded.
- Dataset, sample, and project operations expose only the access-control, ownership, and project-assignment capabilities supported by their API contracts.
- Project member add, role-update, and removal methods consistently return `list[ProjectMember]`.

### Fixed

- CLI tables display usernames up to their full 24-character limit and project or instrument slugs up to their full 25-character limit.
- Instrument CLI get/list output formats expanded owners correctly and `instrument list --include-metadata --json` exposes requested metadata.
- Project and instrument lookup remains compatible with legacy slugs outside the current creation limits.
- Access-control operations now use the API's canonical principal and permission fields.
- Paginated list operations now request only the number of records needed to satisfy `limit` instead of over-fetching full server pages.
- Quick-start examples now use current dataset creation return values.
- Download guides now use current namespaced methods and overwrite options.
- `files.download()` crashed with a raw exception on a non-GCS file instead of a clear error.
- `AssociatedFile` silently dropped `storage_backend`/`access_note` fields returned by the API.
- `cast`: uploading files in a recipe always crashed.
- `cast`: resuming a recipe after a partial failure always crashed.
- `dataset create`/parser-based uploads forced generic ingestion instead of letting the server auto-detect.
- Parser-based uploads sent a stale, unused field to the server.
- Users without a username disappeared from shell autocomplete; they now show by ORCID.
- Some `edit` commands silently ignored `--debug`.
- Docs and the tutorial notebook referenced removed/renamed methods and wrong parameter names in several places.

## 3.1.0

- `projects.get()`/`search()` no longer require membership; `lead`/`scientific_metadata` are membership-gated.
- New `client.access_groups` resource: `request_join()`, `list_join_requests()`, `approve_join_request()`, `reject_join_request()` (requires the pending `feat/access-group-join-requests` API branch).
- `client.projects.request_join()`/`list_join_requests()` delegate to `access_groups`.
- `client.account.join_requests()` lists the caller's own join-request history.
- New `crucible access-group`/`ag` CLI: `request`, `list`, `mine`, `approve`, `reject`.
- New `crucible project request-join` and `crucible project list-join-requests`.
- Fix `access_groups.request_join()`: always send a JSON body (API requires it even with no reason).
- Join request and deletion request lists now show usernames instead of raw ORCIDs, drop the reason column, and show dates as `YYYY-MM-DD`.
- New shared CLI helpers: `helpers.resolve_usernames()`, `term.fmt_date()`, `term.status_label()`, `term.fmt_name()` (de-duplication pass, no behavior change).
- CLI: unified user identification. Most `user` subcommands and `project add-user`/`remove-user` now accept ORCID, username, or email directly. Old identifier flags are deprecated but still work.
- CLI: unified service account identification. `sa` subcommands accept MFID or username directly. Old flags deprecated but still work.
- New `client.service_accounts.list_access_groups()`/`add_to_access_group()`/`remove_from_access_group()` and matching `sa` CLI commands.
- Fix `deletion approve`/`deletion reject`: batch commands now exit 1 if any request fails.
- Fix `dataset add-access-group`: removed the decorative `--read` flag (read access is always granted; `--write` adds write).
- `search_metadata()`: response unwrapped from the paginated envelope; default limit now 20; results include `resource_type`, `name`, `owner_orcid`, timestamps, `rank`.
- `include_owner=True` on `datasets`/`samples` `get()`/`list()` and `client.get()` resolves the owner into a public-safe user object.
- `client.files.delete()` and `crucible file delete` to delete a file by MFID.
- `samples.create()` now takes a `Sample` model as its first argument, consistent with `datasets.create()`.
- `crucible project list-users` shows usernames and correctly reads `unique_id` as the ORCID.
- Default graph explorer URL updated to `https://crucible.lbl.gov/explore`.

## 3.0.1

- Fix `datasets.download()`: data files now saved inside `output_dir/{dsid}/` alongside `record.json`, not directly in `output_dir/`.

## 3.0.0

This is a major release. The flat `client.*` API that was deprecated in 2.x has been
removed. All operations now live under typed resource namespaces.

!!! danger "Breaking changes"
    **Before upgrading**, update any code that uses the old flat API:

    | Old (removed) | New |
    |---|---|
    | `client.get_dataset(dsid)` | `client.datasets.get(dsid)` |
    | `client.create_new_dataset(...)` | `client.datasets.create(...)` |
    | `client.list_datasets(...)` | `client.datasets.list(...)` |
    | `client.get_sample(sid)` | `client.samples.get(sid)` |
    | `client.add_sample(...)` | `client.samples.create(...)` |
    | `client.list_samples(...)` | `client.samples.list(...)` |
    | `client.get_project(pid)` | `client.projects.get(pid)` |
    | `client.get_user(orcid=...)` | `client.users.get(orcid=...)` |
    | `client.download(resource_id)` | `client.datasets.download(dsid)` or `client.samples.download(sid)` |
    | `pip install nano-crucible[shell]` | `pip install nano-crucible` (now core) |
    | `pip install nano-crucible[gcs]` | `pip install nano-crucible` (now core) |
    | `pip install nano-crucible[all]` | `pip install nano-crucible` |

### New resource namespaces

- **`client.account`** — self-service profile management (`profile()`, `update_profile()`,
  `api_key()`, `verify()`, `whoami()`). No admin required.
- **`client.ingestions`** — ingestion request management (`list()`, `get()`, `wait()`, `update()`).
- **`client.files`** is now a proper peer resource (previously a base class for `DatasetOperations`).
  Scoped to file MFIDs: `get()`, `list()`, `download()`, `get_download_link()`, `request_ingestion()`.

### Architecture changes

- `DatasetOperations` no longer inherits from `FileOperations`. All dataset-scoped file
  operations (`add_file`, `list_files`, `get_download_links`, `download`, thumbnails,
  ingestion) now live directly on `DatasetOperations`.
- Upload logic extracted to `crucible/resources/gcs/upload.py` — standalone functions
  testable in isolation.
- Download logic extracted to `crucible/resources/gcs/download.py` — parallel file downloads
  via `ThreadPoolExecutor`.
- Scientific metadata methods (`search_metadata`, `get_scientific_metadata`,
  `update_scientific_metadata`, `get_access_groups`, `add_access_group`) unified on
  `BaseResource` — available on all resource types.
- `search_scientific_metadata()` renamed to `search_metadata()` (deprecated alias kept).

### New features

- **Parallel GCS multipart upload** — `add_file()` uses `transfer_manager.upload_chunks_concurrently()`
  by default (8 workers, 64 MiB chunks, benchmarked). Falls back to sequential resumable upload
  with `multipart=False`. Upload settings configurable via `crucible config set upload_chunk_size_mb`
  and `upload_max_workers`.
- **Sequential per-dataset downloads** — files within a dataset download sequentially; to
  parallelise across datasets, wrap `datasets.download()` in a `ThreadPoolExecutor` at the
  caller level.
- **Fuzzy name search** — `datasets.search(q)`, `samples.search(q)`, `projects.search(q)`,
  `instruments.search(q)` via new API endpoints. Typo-tolerant, returns top-N by relevance.
- **Scientific metadata search** renamed — `search_metadata(q)` on all resources.
- **Username support** — `users.get(username=...)`, `users.search(q)`, `user set-username`,
  `project add-user -u USERNAME`.
- **`samples.download(sid)`** — saves sample record as `record.json`.
- **`files.download(file_id)`** — single-file download by MFID.
- **`ingestions.wait(request_id)`** — public polling method.

### Packaging

- `google-cloud-storage>=2.7.0` and `prompt_toolkit>=3.0` moved to core dependencies.
- `[shell]`, `[gcs]`, and `[all]` extras removed — `pip install nano-crucible` installs everything.
- `[parsers]` remains optional (ASE/LAMMPS support).

### CLI additions

- `crucible account` — `show`, `edit`, `update`, `api-key`, `verify`
- `crucible ingestion` — `list`, `get`, `wait`
- `crucible user search TERM` — non-admin user lookup
- `crucible {dataset,sample,project,instrument} search TERM` — fuzzy name search
- `crucible {dataset,sample,project,instrument} search-metadata TERM` (also `search-md`)
- `crucible dataset list-access-groups`, `add-access-group`
- `crucible user add-access-group`, `remove-access-group`
- `crucible deletion list-deleted`, `get-deleted`, `delete --force`
- `--json` flag on all `get` and `list` commands (replaces `--output json`)
- `sample update` — named flags (`-n`, `-t`, `--description`, `--project`, `--public`)

### Deprecations (still work, emit warnings)

- `client.download()` → `client.datasets.download()` or `client.samples.download()`
- `datasets.get_associated_files()` → `datasets.list_files()`
- `datasets.search_scientific_metadata()` → `datasets.search_metadata()`
- `datasets.add_file_to_dataset()` → `datasets.add_file()`
- `datasets.graph()` → `client.graphs.get()`
- `datasets.get_ingestion_requests()` → `client.ingestions.list()`
- `datasets.get_request_status()` → `client.ingestions.get()`
- `datasets.update_ingestion_status()` → `client.ingestions.update()`
- `users.me()` → `client.account.profile()`
- `users.get_api_key()` → `client.account.api_key()`

---

## 2.1.0 → 2.1.2

Although versioned as a patch series, this span (late March to mid-May) is effectively a
feature release. The notes below focus on what affects code you write against the client.

!!! warning "Likely breaking changes"
    Most users only need to address three things:

    - User responses now key identity as `unique_id` instead of `orcid` (e.g. `user["orcid"]` → `user["unique_id"]`).
    - File methods now live under `client.files` (backward-compat shims on `client.*` still work).
    - `add_metadata` was renamed to `replace_scientific_metadata`.

### New resource namespaces

- **`client.files`** — file operations moved here from `datasets`: chunked GCS upload, plus
  listing, inspecting, and downloading files by `dataset_mfid` or SHA-256 hash.
- **`client.deletions`** — deletion-request workflow (request / approve / reject).
- **`client.graphs`** — graph queries.

### New top-level client methods

- `client.live()` / `client.health()` — unauthenticated health checks.
- `client.search_scientific_metadata(q)` — full-text search across scientific metadata.
- `client.get_links(resource_id)` — immediate links for any resource.

### Moved or renamed methods

- **File methods moved `datasets` → `files`**: `add_associated_file`, `get_associated_files`,
  `upload_file`, and download helpers. Backward-compat shims on `client.*` still work.
- **Scientific-metadata methods moved to the shared base resource** — now available on
  `datasets`, `samples`, `projects`, *and* `instruments`.
- **`add_metadata` → `replace_scientific_metadata`** (rename). Use
  `update_scientific_metadata(..., overwrite=False)` to merge (PATCH) or `overwrite=True` to
  replace (POST).
- **`users`**: removed `get_or_create` and `get_user_from_api`; added `update()`,
  `get_api_key()`, and `remove_from_access_group()`.
- **`projects`**: added `update()`, `remove_user()`, `add_scientific_metadata()`, and
  `update_scientific_metadata()`.
- **`instruments`**: added `update()`, `add_scientific_metadata()`, and
  `update_scientific_metadata()`.
- **`samples` / `datasets`**: added `count()` and `graph()`.

### Model field changes

- **`User`**: `orcid` field renamed to `unique_id` (with a `.orcid` property alias for
  backward compatibility); removed `lbl_email` and `employee_number`; added
  `is_service_account`.
- **`Sample`**: added `public`, `scientific_metadata`, `datasets`, `links`,
  `deletion_request`, `resource_type`; removed `owner_user_id`.
- **`Dataset`**: added `data_type`, `scientific_metadata`, `links`, `deletion_request`,
  `resource_type`; removed `owner_user_id` and `instrument_id`; dropped `file_to_upload` and
  `sha256_hash_file_to_upload`.
- **`Project`**: `project_lead_email` is now optional (previously required); added
  `project_lead_orcid`, `lead`, `scientific_metadata`, and timestamp fields.
- New **`DeletionRequest`** model.

### Behavior changes

- `projects.add_user()` / `remove_user()` accept an email directly — no more client-side
  ORCID resolution.
- Chunked GCS uploads: 32 MiB chunks with per-chunk CRC32C and incremental SHA-256, verified
  at `/complete`.
- Fixed a hashing bug affecting larger files (the actual 2.1.1 → 2.1.2 change).
- Public-sample support (`sample create --public`).

### Packaging

- New required dependencies: `configupdater`, `pyyaml`, `google-crc32c`.
- New optional extras: `[shell]` (`prompt_toolkit`) and `[docs]` (mkdocs).

### CLI

New subcommands: `crucible file`, `crucible deletion`, `crucible status`, `crucible qr`,
`crucible tree`, and `crucible cast`, plus an interactive shell when you run `crucible` with
no arguments.
