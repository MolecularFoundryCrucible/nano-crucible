# CLI command reference

This page is the canonical command inventory for the Crucible CLI. Use `crucible <command> --help` or `crucible <resource> <action> --help` for the exact arguments, aliases, defaults, and examples supported by the installed version.

Project options use `--project-id` with the conventional `-p` short alias. Sample type options use `--type` with `-t`. Older spellings remain temporarily accepted with a deprecation warning but are omitted from current examples.

## Global options

| Option | Description |
|---|---|
| `--version` | Print the installed client version and exit |
| `--debug` | Enable Crucible debug logging; place it before the command |
| `--no-color` | Disable ANSI colors while retaining interactive terminal hyperlinks; place it before the command |

Running `crucible` without a command starts the interactive shell. See the [CLI overview](index.md) for setup, shell completion, and interactive usage.

`--json` is available for dataset, sample, and instrument `list` and `get`; project `list` and `get`; generic `get`; user `get`, `list`, and `search`; service-account `get` and `list`; account `show`; and dataset, sample, project, and instrument name or metadata searches. Collection and search commands return arrays, while singleton commands return objects.

## Dataset commands

| Command | Description |
|---|---|
| `dataset list` | List assigned or shared datasets by project ID or canonical project MFID, with instrument, metadata, and name-pattern filters |
| `dataset get MFID` | Show a dataset, its files, and linked resources |
| `dataset create [--input FILE ...]` | Create a dataset, optionally uploading or cataloging files |
| `dataset update MFID` | Update model fields or scientific metadata |
| `dataset edit MFID` | Edit dataset fields interactively |
| `dataset reassign-project MFID PROJECT` | Move a dataset to another project |
| `dataset transfer-ownership MFID USER` | Transfer dataset ownership |
| `dataset delete MFID` | Permanently delete a dataset after confirmation |
| `dataset search QUERY` | Search dataset names |
| `dataset search-metadata QUERY` | Search scientific metadata; `search-md` is an alias |
| `dataset link` | Link parent and child datasets; `--relationship-type` records the kind of link |
| `dataset remove-child` | Remove a dataset parent-child link |
| `dataset list-parents MFID` | List parent datasets; `--relationship-type` filters by kind of link |
| `dataset list-children MFID` | List child datasets; `--relationship-type` filters by kind of link |
| `dataset add-sample MFID` | Link a sample to a dataset |
| `dataset remove-sample MFID` | Unlink a sample from a dataset |
| `dataset list-samples MFID` | List samples linked to a dataset |
| `dataset add-file MFID FILE` | Upload files to an existing dataset |
| `dataset add-thumbnail MFID IMAGE` | Encode and add a local image as a dataset thumbnail |
| `dataset list-files MFID` | List associated files and available download links |
| `dataset download MFID` | Download dataset files with optional include and exclude patterns |
| `dataset ingestion MFID` | Show ingestion requests for a dataset |
| `dataset add-keyword MFID WORD` | Add a keyword |
| `dataset list-keywords MFID` | List a dataset's keywords and usage counts |
| `dataset list-access-groups MFID` | Deprecated compatibility command; use `dataset access list` |
| `dataset add-access-group MFID GROUP` | Deprecated compatibility command; use `dataset access grant` |
| `dataset access ...` | List, grant, or revoke direct access entries |
| `dataset publish MFID` | Make a dataset publicly viewable |
| `dataset unpublish MFID` | Remove public access from a dataset |
| `dataset parsers` | List installed client-side parsers |
| `dataset ingestors` | List server-advertised ingestion classes |

Common creation example:

```bash
crucible dataset create -i data.csv --project-id my-project \
    -n "XRD measurement" -m "X-ray diffraction" \
    --metadata '{"temperature_K": 300}' --keywords "XRD,powder"
```

Create a dataset record without attaching files:

```bash
crucible dataset create --project-id my-project --name "Planned experiment"
```

Dataset creation accepts `--project-id` or `--project-mfid` and `--instrument-id` or `--instrument-mfid`. Matching ID and MFID forms may be supplied together. Interactive use remains ID-oriented, while MFID flags support integrations and automation.

The `--type`, `--ingestor`, `--no-upload`, `--backend`, and `--access-note` options require at least one `--input` file.

Use `dataset list --project-id PROJECT --project-scope shared` to show resources shared with a project but assigned elsewhere or unassigned. Use `--project-scope all` to combine assigned and shared resources. `--project-mfid` accepts the canonical project MFID instead of a project ID. The interactive shell completes both identifiers through project search. Human-readable scoped results include the resource's actual project and its `assigned` or `shared` relation.

Fields normally updated through `dataset update --set` include `dataset_name`, `measurement`, `data_type`, `session_name`, `data_format`, `timestamp`, and `public`. Use `reassign-project` and `transfer-ownership` for project and owner changes. Instrument reassignment remains unavailable and is not exposed as ordinary metadata editing.

## Sample commands

| Command | Description |
|---|---|
| `sample list` | List assigned or shared samples by project ID or canonical project MFID, with name, type, and name-pattern filters |
| `sample get MFID` | Show a sample and its linked resources |
| `sample create` | Create a sample |
| `sample update MFID` | Update sample fields or scientific metadata |
| `sample edit MFID` | Edit sample fields interactively |
| `sample reassign-project MFID PROJECT` | Move a sample to another project |
| `sample transfer-ownership MFID USER` | Transfer sample ownership |
| `sample search QUERY` | Search sample names |
| `sample search-metadata QUERY` | Search scientific metadata; `search-md` is an alias |
| `sample link` | Link parent and child samples; `--relationship-type` records the kind of link |
| `sample remove-child` | Remove a sample parent-child link |
| `sample list-parents MFID` | List parent samples; `--relationship-type` filters by kind of link |
| `sample list-children MFID` | List child samples; `--relationship-type` filters by kind of link |
| `sample add-dataset MFID` | Link a dataset to a sample |
| `sample remove-dataset MFID` | Unlink a dataset from a sample |
| `sample list-datasets MFID` | List datasets linked to a sample |
| `sample access ...` | List, grant, or revoke direct access entries |
| `sample publish MFID` | Make a sample publicly viewable |
| `sample unpublish MFID` | Remove public access from a sample |

Fields normally updated through `sample update` include `sample_name`, `sample_type`, `description`, `timestamp`, and `public`. Use `reassign-project` and `transfer-ownership` for project and owner changes.

Sample creation accepts `--project-id` or `--project-mfid`, including both when they resolve to the same project. Interactive creation continues to prompt for the human-readable project ID.

`sample list` uses the same `--project-id` or `--project-mfid` selectors and `--project-scope assigned|shared|all` behavior as dataset listing. Human-readable shared and combined results include the actual project and project relation.

## Project commands

| Command | Description |
|---|---|
| `project list` | List accessible projects |
| `project get PROJECT [--include-members]` | Show a project by MFID or project slug, optionally with its members |
| `project create` | Create a project |
| `project update ID` | Update a project record or scientific metadata |
| `project edit ID` | Edit project fields interactively |
| `project search QUERY` | Search project names and IDs |
| `project search-metadata QUERY` | Search scientific metadata; `search-md` is an alias |
| `project list-users ID` | List project members and roles |
| `project add-user ID` | Add a user to a project |
| `project remove-user ID` | Remove a user from a project |
| `project update-user-role ID USER_ID ROLE` | Change a project member's role |
| `project transfer-ownership ID USER` | Transfer project ownership |
| `project request-join ID` | Request membership in a project |
| `project list-join-requests ID` | List project join requests |
| `project access ...` | List, grant, or revoke direct access entries |
| `project publish ID` | Make a project publicly viewable |
| `project unpublish ID` | Remove public access from a project |

`project add-user` and `project update-user-role` require editor or above and accept `viewer`, `contributor`, `editor`, or `admin`. The target member's current role and requested role must both be below the caller's role. Editors can manage viewers and contributors, admins can also manage editors, and owners can also manage admins. Platform administrators retain their bypass. Use `project transfer-ownership` to change ownership.

`project remove-user` permits project owners and platform administrators to remove members, while any member may remove themselves.

Project member tables sort by standing from lead through viewer, display the API `owner` role as `lead`, and use semantic role colors when terminal color is enabled: gold for lead, magenta for admin, blue for editor, the default foreground for contributor, and gray for viewer.

The `access grant` commands accept `viewer`, `contributor`, `editor`, or `admin`. Use the resource's `transfer-ownership` command to change ownership.

## Instrument commands

| Command | Description |
|---|---|
| `instrument list` | List instruments |
| `instrument get INSTRUMENT` | Show an instrument by MFID or instrument slug |
| `instrument create` | Register an instrument |
| `instrument update MFID` | Update an instrument record or scientific metadata |
| `instrument set-status MFID STATUS` | Change an instrument lifecycle status |
| `instrument transfer-ownership MFID USER` | Transfer instrument ownership |
| `instrument list-service-accounts MFID` | List service accounts bound as instrument operators |
| `instrument bind-sa MFID SA_MFID` | Bind a service account as an instrument operator |
| `instrument unbind-sa MFID SA_MFID` | Remove an instrument operator binding |
| `instrument edit MFID` | Edit instrument fields interactively |
| `instrument search QUERY [--status STATUS]` | Search names, types, and manufacturers with optional lifecycle filtering |
| `instrument search-metadata QUERY` | Search scientific metadata; `search-md` is an alias |

## User commands

Most user-management commands require administrator permissions.

| Command | Description |
|---|---|
| `user get USER` | Show a user by ORCID, MFID, username, or email |
| `user search QUERY` | Search names and usernames |
| `user list` | List users |
| `user create` | Create a user |
| `user update USER` | Update a user record |
| `user edit USER` | Edit a user record interactively |
| `user list-datasets USER [--limit N]` | List datasets accessible to a user |
| `user check-access USER DATASET_MFID` | Show a user's effective dataset access role |
| `user list-access-groups USER` | List a user's access groups |
| `user add-access-group USER GROUP` | Deprecated; use the typed project or instrument membership command |
| `user remove-access-group USER GROUP` | Deprecated; use the typed project or instrument membership command |
| `user list-projects USER` | List a user's projects |

Human users require a username and may optionally supply an ORCID during creation.
When the ORCID is omitted, the API assigns a canonical MFID.
Usernames are normalized to lowercase and must be 3 to 24 characters, start with a letter, contain only letters, digits, underscores, or hyphens, and contain no leading, trailing, or consecutive separators. Interactive creation validates each entry and prompts again when it is invalid.

## File commands

File commands operate on individual file MFIDs. Dataset-scoped file operations remain available under `dataset`.

| Command | Description |
|---|---|
| `file list` | List files globally or within a dataset |
| `file get ID` | Show file metadata and a download link when available |
| `file download ID` | Download one file |
| `file ingestion ID` | Show ingestion requests for a file |
| `file request-ingestion ID` | Request or repeat ingestion for a cataloged file |
| `file delete ID [--yes]` | Permanently delete a file after confirmation |

## Ingestion commands

| Command | Description |
|---|---|
| `ingestion list` | List ingestion requests |
| `ingestion get ID` | Show an ingestion request |
| `ingestion wait ID` | Wait for an ingestion request to finish |
| `ingestion list-ingestors` | List available ingestion classes |

## Service-account commands

`sa` is an alias for `service-account`. These commands require administrator permissions.
Service-account creation uses the same username rules and interactive validation as human-user creation.

| Command | Description |
|---|---|
| `sa create` | Create a service account |
| `sa rotate-key USER` | Generate a new key and invalidate the previous key |
| `sa get USER` | Show a service account |
| `sa list` | List service accounts |
| `sa update USER` | Update a service account |
| `sa edit USER` | Edit a service account interactively |
| `sa list-access-groups USER` | List access groups for a service account |
| `sa add-access-group USER GROUP` | Deprecated; use `project add-user` or `instrument bind-sa` |
| `sa remove-access-group USER GROUP` | Deprecated; use `project remove-user` or `instrument unbind-sa` |

## Access-group commands

`ag` is an alias for `access-group`.

| Command | Description |
|---|---|
| `ag request GROUP` | Request to join an access group or project |
| `ag mine` | List the current user's join requests |
| `ag list` | List join requests for review |
| `ag get ID` | Show a join request |
| `ag approve ID...` | Approve pending join requests |
| `ag reject ID...` | Reject pending join requests |

## Account commands

These commands operate on the currently authenticated account and do not require administrator permissions.

| Command | Description |
|---|---|
| `account show` | Show the current profile |
| `account update` | Update profile fields |
| `account edit` | Edit the current profile interactively |
| `account api-key` | Show the current API key |
| `account verify` | Check API-key validity and expiry |

Treat output from `account api-key` as a secret. Do not include it in logs, issue reports, or agent prompts.

## Deletion commands

The deletion-request workflow is separate from direct permanent deletion. Review and audit commands require administrator permissions.

| Command | Description |
|---|---|
| `deletion request RESOURCE` | Request deletion of a dataset or sample |
| `deletion list` | List deletion requests |
| `deletion get ID` | Show a deletion request |
| `deletion approve ID...` | Approve pending requests |
| `deletion reject ID...` | Reject pending requests |
| `deletion delete RESOURCE` | Permanently delete a resource |
| `deletion list-deleted` | List permanent-deletion audit records |
| `deletion get-deleted ID` | Show a permanent-deletion audit record |

## Cast command

`cast` loads a declarative `.crux` recipe containing datasets, samples, files, and links.

| Command | Description |
|---|---|
| `cast FILE` | Execute a recipe |
| `cast FILE --validate` | Validate references and cycles without executing |
| `cast FILE --dry-run` | Preview execution without API mutations |
| `cast FILE --show` | Show the plan and lock status |
| `cast FILE --force` | Clear the lock and recreate entities |
| `cast FILE --reupload` | Re-upload files without recreating records |

## Configuration and cache

| Command | Description |
|---|---|
| `config init` | Run interactive configuration setup |
| `config show` | Show the current configuration |
| `config get KEY` | Print one configuration value |
| `config set KEY VALUE` | Set one configuration value |
| `config unset KEY` | Remove a config-file override and return to the environment or package default |
| `config path` | Show the configuration-file path |
| `config edit` | Edit the configuration file |
| `cache show` | Show cache location and disk usage |
| `cache clear` | Remove cached files by dataset, age, or all entries |

Configuration values can come from environment variables, the platform-specific config file, or defaults. Avoid displaying `api_key` in shared terminals or logs.

`dataset delete`, `file delete`, and `cache clear` prompt before removing data. Use `--yes` only when the operation has already been explicitly approved, such as in a controlled noninteractive workflow.

## General utility commands

| Command | Description |
|---|---|
| `status` | Show endpoint reachability, deployment provenance, database readiness, and authentication identity |
| `whoami` | Show the identity associated with the configured key |
| `get MFID` | Show a dataset, sample, project, or instrument after detecting its resource type |
| `edit MFID` | Edit a dataset, sample, or instrument after detecting its type |
| `download MFID` | Save a record and, for datasets, associated files |
| `link` | Link parent-child resources or associate a dataset and sample; `--relationship-type` applies to parent-child links only |
| `unlink MFID1 MFID2` | Remove a resource relationship |
| `tree MFID` | Display connected ancestors and descendants |
| `open [ID]` | Open the Graph Explorer or print its URL |
| `qr ID` | Print a terminal QR code for an MFID |
| `completion [SHELL]` | Generate and install completion for bash, zsh, fish, or tcsh |
| `upload ...` | Deprecated upload command; use `dataset create` |

## Deprecated aliases

| Old form | Current form |
|---|---|
| `dataset update-metadata` | `dataset update --metadata` |
| `dataset get-keywords` | `dataset list-keywords` |
| `sample link-dataset` | `sample add-dataset` |
| `user get-access-groups` | `user list-access-groups` |
| `user get-projects` | `user list-projects` |
| `project get-users` | `project list-users` |
| `project get PROJECT --members` | `project get PROJECT --include-members` |

Deprecated forms remain available for compatibility but emit a warning. New documentation and scripts should use the current forms.
