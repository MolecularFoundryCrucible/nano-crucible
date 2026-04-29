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
