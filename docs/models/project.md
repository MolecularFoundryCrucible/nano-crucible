# Project

A project is the top-level organizational unit in Crucible. It groups related datasets and samples and controls which users have access to them.

## Notes

- `project_id` must be unique across the system and is chosen by the creator. Use a short, recognizable identifier (e.g., `MFP12345` for Molecular Foundry proposals).
- `organization` is a free-text field for the institution or group leading the project (e.g., `"LBNL"`, `"Stanford"`).
- `project_lead_orcid` is required when creating a project via `client.projects.create()`.
- `project_lead_name` and `project_lead_email` are read-only fields populated by the server based on the lead's ORCID.

## Example

```python
from crucible.models import Project

project = Project(
    project_id="MFP12345",
    organization="LBNL",
    project_lead_orcid="0000-0001-2345-6789",
    title="Nanoparticle synthesis study",
    status="active",
)

result = client.projects.create(project)
```
