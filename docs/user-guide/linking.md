# Linking Resources

Crucible supports links between datasets and between datasets and samples. Links let you represent relationships like:

- A processed dataset derived from a raw dataset (dataset → dataset)
- A sample that a dataset was measured from (dataset ↔ sample)
- A sample synthesized from another sample (sample → sample)

---

## Dataset ↔ Sample links

```python
# Link a dataset to a sample
client.samples.add_dataset(sample_id="sm-abc123", dataset_id="ds-xyz789")

# Or equivalently from the dataset side
client.datasets.add_sample(dataset_id="ds-xyz789", sample_id="sm-abc123")

# Remove a link
client.samples.remove_dataset(sample_id="sm-abc123", dataset_id="ds-xyz789")
```

---

## Dataset → Dataset (parent-child)

Use parent-child links to represent processing pipelines:

```python
# Establish raw → processed relationship
client.datasets.link_parent_child(parent_id="ds-raw", child_id="ds-processed")

# Remove it
client.datasets.remove_child(parent_id="ds-raw", child_id="ds-processed")

# Navigate
parents = client.datasets.list_parents("ds-processed")
children = client.datasets.list_children("ds-raw")
```

---

## Sample → Sample (parent-child)

```python
# Establish provenance: boule → wafer
client.samples.link(parent_id="sm-boule", child_id="sm-wafer")

# Remove it
client.samples.remove_child(parent_id="sm-boule", child_id="sm-wafer")

# Navigate
parents = client.samples.list_parents("sm-wafer")
children = client.samples.list_children("sm-boule")
```

---

## Generic link/unlink (auto-detects types)

If you have two IDs and don't want to look up their types first:

```python
# Works for dataset-sample, dataset-dataset, or sample-sample pairs
client.link("ds-abc123", "sm-xyz789")
client.unlink("ds-abc123", "sm-xyz789")
```

---

## Viewing all links for a resource

```python
# Returns immediate links for any resource ID
links = client.get_links("ds-abc123")
```

---

## Graph traversal

For a visual or programmatic view of the full relationship graph:

```python
# First-degree connections
graph = client.graphs.get("ds-abc123")

# Full connected component
graph = client.graphs.get("ds-abc123", recursive=True)

# All resources in a project
graph = client.graphs.project("MFP12345")

# As a networkx DiGraph
G = client.graphs.get("ds-abc123", recursive=True, as_networkx=True)
```

---

## CLI

```bash
# Link any two resources (type auto-detected)
crucible link PARENT_ID CHILD_ID

# Unlink
crucible unlink ID_A ID_B

# View the graph for a resource
crucible tree RESOURCE_ID
```
