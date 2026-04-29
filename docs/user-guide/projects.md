# Project Management

## Listing projects

```python
projects = client.projects.list()
for p in projects:
    print(p["project_id"], p["title"])
```

## Getting a project

```python
project = client.projects.get("MFP12345")
```

## Creating a project

```python
from crucible.models import Project

result = client.projects.create(Project(
    project_id="MFP12345",
    organization="LBNL",
    project_lead_orcid="0000-0001-2345-6789",
    title="Nanoparticle synthesis study",
    status="active",
))
```

`project_id` must be unique across the system. `project_lead_orcid` must correspond to an existing Crucible user.

## Updating a project

```python
client.projects.update("MFP12345", title="Nanoparticle synthesis study — phase 2", status="active")
```

## Managing users

### List users in a project

```python
users = client.projects.get_users("MFP12345")
for u in users:
    print(u["unique_id"], u["email"])
```

### Add a user

```python
client.projects.add_user(orcid="0000-0002-3456-7890", project_id="MFP12345")
```

### Remove a user

```python
client.projects.remove_user(project_id="MFP12345", orcid="0000-0002-3456-7890")
```


## Setting a default project in the CLI

Set a default project so you don't have to pass `-pid` on every command:

```bash
crucible config set current_project MFP12345
```

Or switch the active project in the interactive shell:

```bash
crucible
> use MFP12345
```
