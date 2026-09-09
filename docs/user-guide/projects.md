# Project Model

| Field | Description | Settable |
|---|---|---|
| `project_id` | Short, unique identifier (e.g. `MFP12345`) | create, update |
| `organization` | Free-text institution or group name (e.g. `"LBNL"`, `"Stanford"`) | create, update |
| `title` | Human-readable project title | create, update |
| `status` | Project status (e.g. `"active"`) | create, update |
| `project_lead` | Project lead identified by ORCID, MFID, username, or email | create |
| `lead` | Public-safe resolved project lead record without email | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |
| `capabilities` | Optional caller-specific actions calculated for an exact response | server-assigned |

# Project Management

## Listing projects

```python
projects = client.projects.list()
for p in projects:
    print(p["project_id"], p["title"])

shared_projects = client.projects.list(
    accessible_to_user="alice",
    accessible_to_project="my-project",
)
```

Typed access selectors accept one reference or a list of references. Multiple selectors use intersection semantics and only narrow projects readable by the authenticated caller.

## Getting a project

```python
project = client.projects.get("MFP12345")
```

`get()` accepts either a project ID or its canonical 26-character MFID. It dispatches MFIDs to the single-project route and resolves project IDs with one exact collection request. New and renamed project IDs must contain 3 to 25 characters, but lookup remains compatible with older IDs outside that range. Every returned project keeps `unique_id` as its canonical identifier. Use `project_id=` or `project_mfid=` when the intended identifier type must be explicit.

Use `include_members=True` to request the member list. Members and administrators can see membership-gated metadata and members; other authenticated users receive the public project view.

Exact MFID and slug lookups include caller-specific `capabilities` when the server has calculated them. General lists and searches normally return `capabilities=None`, which means the guidance was not calculated rather than that every action is denied. The API remains authoritative for each mutation.

Dataset and sample collections can use either `project_id` or `project_mfid` with `project_scope="assigned"`, `"shared"`, or `"all"`. The default `assigned` scope preserves the traditional project listing. The `shared` scope finds resources accessible through the project but assigned elsewhere or unassigned, while `all` combines both relationships. Singleton resource retrieval remains MFID-based and does not require project context.

Project capabilities expose the strict membership hierarchy through `max_grant_role`: editors receive `contributor`, admins receive `editor`, and owners receive `admin`. The value is guidance for the highest role the caller may grant, while the API still validates the target member and current project state.

```python
project = client.projects.get("MFP12345", include_metadata=True, include_members=True)
```

## Creating a project

```python
from crucible.models import Project

result = client.projects.create(Project(
    project_id="MFP12345",
    organization="LBNL",
    project_lead="lead-username",
    title="Nanoparticle synthesis study",
    status="active",
))
```

`project_id` must be unique across the system. The project lead must identify an existing Crucible user.

## Updating a project

```python
client.projects.update("MFP12345", title="Nanoparticle synthesis study, phase 2", status="active")
```

## Managing users

### List users in a project

```python
users = client.projects.get_users("MFP12345")
for u in users:
    print(u.unique_id, u.username, u.role)
```

Project lead, member, and operator records are public-safe and do not expose email addresses.

### Add a user

```python
members = client.projects.add_user(user_unique_id="0000-0002-3456-7890", project_id="MFP12345", role="contributor")
```

Member roles are the lowercase strings `viewer`, `contributor`, `editor`, and `admin`. Adding or managing a member requires editor or above, and both the target member's current role and requested role must be strictly below the caller's role. Editors can manage viewers and contributors, admins can also manage editors, and owners can also manage admins. Platform administrators retain their bypass. Ownership is changed only through `transfer_ownership()`.

Adding an existing member at a different role returns 409. Use `update_user_role()` to change existing standing.

### Change a member role

```python
members = client.projects.update_user_role("MFP12345", "0000-0002-3456-7890", "editor")
```

### Remove a user

```python
members = client.projects.remove_user(project_id="MFP12345", user_unique_id="0000-0002-3456-7890")
```

Project owners and platform administrators may remove members. Any member may remove themselves. Other member removal is not governed by the add and role-update hierarchy.

All three member mutations return the updated `list[ProjectMember]`.

## Ownership and access

Ownership transfer is preview-only unless `confirm=True`:

```python
preview = client.projects.transfer_ownership("MFP12345", "new-lead@example.org")
result = client.projects.transfer_ownership("MFP12345", "new-lead@example.org", confirm=True)
```

Direct access grants are managed separately:

```python
grants = client.projects.list_access("MFP12345")
client.projects.set_access("MFP12345", "users", "0000-0002-1825-0097", "viewer")
client.projects.revoke_access("MFP12345", "users", "0000-0002-1825-0097")
```

Normal access grants accept `viewer`, `contributor`, `editor`, or `admin`. Use `transfer_ownership()` for ownership.


## Selecting the current project in the CLI

Select a current project so you don't have to pass `--project-id` on every command:

```bash
crucible config set current_project MFP12345
```

You can also select it from the interactive shell:

```bash
crucible
> use MFP12345
```

The shell validates the project and saves the selection for future commands and shell sessions. Run `unuse` to clear it. An explicit `--project-id` applies only to that command and does not change the saved selection.

`CRUCIBLE_CURRENT_PROJECT` remains available temporarily for compatibility, but it is deprecated because it can silently override the saved selection. Prefer an explicit `--project-id` in automation.
