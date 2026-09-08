# Sample Model

| Field | Description | Settable |
|---|---|---|
| `sample_name` | Human-readable name for the sample | create, update |
| `sample_type` | Category or type of sample (used for filtering) | create, update |
| `project_id` | Project this sample belongs to | create; later changes use `reassign_project()` |
| `project_mfid` | Canonical project selector for creation | create |
| `project` | Current project title, ID, and canonical identity when the relationship resolves | server-assigned |
| `description` | Free-text description of the sample | create, update |
| `timestamp` | Date associated with the sample (ISO 8601 format) | create, update |
| `public` | Whether the sample is publicly accessible (default: `False`) | create, update |
| `owner_orcid` | Canonical owner identifier returned by the API; deprecated as a creation input | read; deprecated for create |
| `owner` | Flexible owner identifier on create; public-safe user record on singleton reads | create with an ORCID, MFID, username, or email; expanded by default on `get()` |
| `unique_id` | System-assigned MFID identifier | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |
| `capabilities` | Optional caller-specific actions calculated for an exact response | server-assigned |

### Relationships

| Relationship | Key(s) | Description |
|---|---|---|
| **Scientific metadata** | `scientific_metadata` in `create()`; `metadata` in `update_scientific_metadata()` / `replace_scientific_metadata()` | A free-form JSON object for sample-specific properties (e.g. solubility, physical location). |
| **Datasets** | `dataset_mfid` in `link_dataset(sample_mfid, dataset_mfid)` | A sample can be linked to one or more datasets, and a dataset to one or more samples, capturing which material was measured. |
| **Parent/child samples** | `parent_mfid`, `child_mfid` in `link()`; parent and child records are also accepted in `create()` | Samples form hierarchies to represent provenance, such as boule to wafer to thin film. |

# Working with Samples

## Creating a sample
```python
from crucible.models import Sample

sample = client.samples.create(
    Sample(
        sample_name="Au nanoparticles batch 7",
        sample_type="nanoparticle suspension",
        project_id="my-project",
        description="5 nm Au NPs in citrate buffer, synthesized by Turkevich method",
        timestamp="2024-03-10",
    )
)

sample_mfid = sample["unique_id"]
```

Applications may provide `project_mfid` instead of `project_id`, or provide both when they identify the same project. Conflicting selectors produce an API validation error. The CLI keeps `--project-id` as its normal interactive input and exposes `--project-mfid` for integrations and automation.

## Retrieving a sample

```python
sample = client.samples.get("0td7evvtg5wb90005k1j97ak94")
sample_with_details = client.samples.get(
    "0td7evvtg5wb90005k1j97ak94",
    include_links=True,
    include_datasets=False,
)
```

Samples are retrieved only by their canonical 26-character MFID. Sample names are display values, not identifiers.

Sample detail responses retain the legacy embedded `datasets` collection by default for compatibility. The field is deprecated. Pass `include_datasets=False` to avoid loading complete dataset records, use `include_links=True` for lightweight relationship references, or use `client.datasets.list(sample_mfid=sample_mfid)` for complete paginated dataset records.

Singleton retrieval expands `owner` by default as a public-safe user record containing `unique_id`, `username`, `first_name`, and `last_name`. Pass `include_owner=False` to suppress expansion. List operations remain opt-in with `include_owner=True`. The canonical owner identifier remains available as `owner_orcid`.

Canonical detail responses include caller-specific `capabilities` when the server has calculated them. Sample capabilities always report `can_change_status=False` because samples have no lifecycle-status operation. Collections and search results normally return `capabilities=None`, which means the guidance was not calculated rather than that every action is denied. The API remains authoritative for each mutation.

Sample responses include a lightweight `project` reference when the canonical relationship resolves. Use its `title` and `project_id` for display and its `unique_id` for stable navigation. The flat `project_id` remains the compatibility fallback for legacy records. A project reference does not imply permission to retrieve the complete project.

## Listing samples

```python
# All samples in a project
samples = client.samples.list(project_id="my-project", limit=50)

# Samples shared with a project but assigned elsewhere or unassigned
shared = client.samples.list(project_id="my-project", project_scope="shared")

# Assigned and shared samples using the project's canonical MFID
visible = client.samples.list(
    project_mfid="0tkn2knjast3h0008nyq9zps2c",
    project_scope="all",
)

# Samples linked to a specific dataset
samples = client.samples.list(dataset_mfid="0tkn2knjast3h0008nyq9zps2c")

# Samples readable by a user and directly accessible to a project
samples = client.samples.list(
    accessible_to_user="alice",
    accessible_to_project="my-project",
)
```

Pass the project slug as `project_id` or the canonical project MFID as `project_mfid`. Both may be supplied when they identify the same project; conflicting identifiers produce an API validation error. `project_scope` accepts `assigned`, `shared`, or `all` and defaults to `assigned`. Scoped collection results expose `project_relation` as `assigned` or `shared`; `project` may be `None` when a shared resource has no primary project.

The `dataset_mfid` relationship filter uses the normal paginated sample collection and can be combined with compatible sample and access filters. Results follow cursor pagination and include only samples the caller may read.

Multiple user and project access selectors use intersection semantics and never broaden what the authenticated caller may read.

## Updating a sample

```python
client.samples.update(
    "0td7evvtg5wb90005k1j97ak94",
    description="5 nm Au NPs, annealed at 200 C for 2h after synthesis",
)
```

Project and ownership changes use preview-first workflows:

```python
project_preview = client.samples.reassign_project(sample_mfid, "new-project")
client.samples.reassign_project(sample_mfid, "new-project", confirm=True)
owner_preview = client.samples.transfer_ownership(sample_mfid, "new-owner@example.org")
client.samples.transfer_ownership(sample_mfid, "new-owner@example.org", confirm=True)
```

## Managing access

```python
grants = client.samples.list_access(sample_mfid)
client.samples.set_access(sample_mfid, "users", "0000-0002-1825-0097", "viewer")
client.samples.publish(sample_mfid)
client.samples.unpublish(sample_mfid)
```

Normal access grants accept `viewer`, `contributor`, `editor`, or `admin`. Use `transfer_ownership()` for ownership.

## Sample hierarchies

Samples can form parent-child trees to represent provenance. Use `link()` to connect an existing parent to a child:

```python
# Link a wafer (child) to the boule it was cut from (parent)
client.samples.link(
    parent_mfid=boule_sample_mfid,
    child_mfid=wafer_sample_mfid,
)
```

You can also pass `parents` or `children` lists at creation time:

```python
thin_film = client.samples.create(
    Sample(
        sample_name="TiO2 thin film on Si",
        sample_type="thin film",
        project_id="my-project",
    ),
    parents=[{"unique_id": wafer_sample_mfid}],
)
```

Navigate the hierarchy:

```python
parents = client.samples.list_parents(sample_mfid)
children = client.samples.list_children(sample_mfid)
```

## Linking samples to datasets

```python
# Link a dataset to a sample
client.samples.link_dataset(sample_mfid=sample_mfid, dataset_mfid=dataset_mfid)

# Remove the link
client.samples.unlink_dataset(sample_mfid=sample_mfid, dataset_mfid=dataset_mfid)
```

## Viewing the sample graph

```python
# First-degree connections (datasets, parent/child samples)
graph = client.samples.graph(sample_mfid)

# Full connected component
graph = client.samples.graph(sample_mfid, recursive=True)

# As a networkx DiGraph (requires networkx)
import networkx as nx
G = client.samples.graph(sample_mfid, recursive=True, as_networkx=True)
```
