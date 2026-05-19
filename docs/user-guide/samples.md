# Sample Model

| Field | Description | Settable |
|---|---|---|
| `sample_name` | Human-readable name for the sample | create, update |
| `sample_type` | Category or type of sample (used for filtering) | create, update |
| `project_id` | Project this sample belongs to | create, update |
| `description` | Free-text description of the sample | create, update |
| `timestamp` | Date associated with the sample (ISO 8601 format) | create, update |
| `public` | Whether the sample is publicly accessible (default: `False`) | create, update |
| `owner_orcid` | Sample owner — defaults to the authenticated user | create, update |
| `unique_id` | System-assigned MFID identifier | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |

### Relationships

| Relationship | Key(s) | Description |
|---|---|---|
| **Scientific metadata** | `scientific_metadata` in `create()`; `metadata` in `update_scientific_metadata()` / `replace_scientific_metadata()` | A free-form JSON object for sample-specific properties (e.g. solubility, physical location). |
| **Datasets** | `dataset_id` in `add_dataset(sample_id, dataset_id)` | A sample can be linked to one or more datasets, and a dataset to one or more samples — capturing which material was measured. |
| **Parent/child samples** | `parent_id`, `child_id` in `link(parent_id, child_id)`; also accepted in `create()` | Samples form hierarchies to represent provenance (e.g. boule → wafer → thin film). |

# Working with Samples

## Creating a sample
```python
sample = client.samples.create(
    sample_name="Au nanoparticles batch 7",
    sample_type="nanoparticle suspension",
    project_id="my-project",
    description="5 nm Au NPs in citrate buffer, synthesized by Turkevich method",
    timestamp="2024-03-10",
)

smid = sample["smid"]
```

## Retrieving a sample

```python
sample = client.samples.get("sm-abc123")
sample_with_links = client.samples.get("sm-abc123", include_links=True)
```

## Listing samples

```python
# All samples in a project
samples = client.samples.list(project_id="my-project", limit=50)

# Samples linked to a specific dataset
samples = client.samples.list(dataset_id="ds-xyz789")
```

## Updating a sample

```python
client.samples.update(
    "sm-abc123",
    description="5 nm Au NPs — annealed at 200°C for 2h after synthesis",
)
```

## Sample hierarchies

Samples can form parent-child trees to represent provenance. Use `link()` to connect an existing parent to a child:

```python
# Link a wafer (child) to the boule it was cut from (parent)
client.samples.link(parent_id=boule_smid, child_id=wafer_smid)
```

You can also pass `parent_id` or `child_id` at creation time:

```python
thin_film = client.samples.create(
    sample_name="TiO2 thin film on Si",
    sample_type="thin film",
    project_id="my-project",
    parent_id=wafer_smid,  # automatically links to wafer on creation
)
```

Navigate the hierarchy:

```python
parents = client.samples.list_parents("sm-abc123")
children = client.samples.list_children("sm-abc123")
```

## Linking samples to datasets

```python
# Link a dataset to a sample
client.samples.add_dataset(sample_id="sm-abc123", dataset_id="ds-xyz789")

# Remove the link
client.samples.remove_dataset(sample_id="sm-abc123", dataset_id="ds-xyz789")
```

## Viewing the sample graph

```python
# First-degree connections (datasets, parent/child samples)
graph = client.samples.graph("sm-abc123")

# Full connected component
graph = client.samples.graph("sm-abc123", recursive=True)

# As a networkx DiGraph (requires networkx)
import networkx as nx
G = client.samples.graph("sm-abc123", recursive=True, as_networkx=True)
```
