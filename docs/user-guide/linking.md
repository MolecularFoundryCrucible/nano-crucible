# Linking Resources

Crucible supports links between datasets and between datasets and samples. Links let you represent relationships like:

- A processed dataset derived from a raw dataset (dataset → dataset)
- A sample that a dataset was measured from (dataset ↔ sample)
- A sample synthesized from another sample (sample → sample)

---

## Dataset ↔ Sample links

```python
# Link a dataset to a sample
client.samples.link_dataset(sample_mfid=sample_mfid, dataset_mfid=dataset_mfid)

# Or equivalently from the dataset side
client.datasets.link_sample(dataset_mfid=dataset_mfid, sample_mfid=sample_mfid)

# Remove a link
client.samples.unlink_dataset(sample_mfid=sample_mfid, dataset_mfid=dataset_mfid)
```

List the readable resources on either side of the relationship through the canonical collection filters:

```python
datasets = client.datasets.list(sample_mfid=sample_mfid)
samples = client.samples.list(dataset_mfid=dataset_mfid)
```

These methods use cursor pagination and return only related resources the caller may read. The older nested relationship reads remain an API compatibility surface but are not used by current Nano methods.

---

## Dataset → Dataset (parent-child)

Use parent-child links to represent processing pipelines:

```python
# Establish raw → processed relationship
client.datasets.link(
    parent_mfid=raw_dataset_mfid,
    child_mfid=processed_dataset_mfid,
    relationship_type='is_derived_from',   # optional
)

# Remove it
client.datasets.unlink(
    parent_mfid=raw_dataset_mfid,
    child_mfid=processed_dataset_mfid,
)

# Navigate, optionally filtering by the kind of link
parents = client.datasets.list_parents(processed_dataset_mfid)
children = client.datasets.list_children(
    raw_dataset_mfid, relationship_type='is_derived_from')
```

---

## Relationship types

Parent-child links — dataset → dataset and sample → sample — can record what
kind of link they are. The value describes the **child relative to the
parent**, so a link `(parent=A, child=B, 'is_part_of')` reads "B is_part_of A".

| Value | Meaning |
| --- | --- |
| `is_derived_from` | The child was produced from the parent (processing, measurement, synthesis) |
| `is_part_of` | The child is a component or subset of the parent |

The type is optional. Omitting it leaves the link untyped, which is also how
every link created before relationship types existed reads. Because the server
treats a supplied type as an overwrite, re-linking an existing pair **without**
`relationship_type` preserves whatever type is already stored rather than
clearing it — pass the new value explicitly to change it.

Dataset ↔ sample associations have no parent-child direction, so they carry no
relationship type. Passing one raises `ValueError`.

---

## Sample → Sample (parent-child)

```python
# Establish provenance: boule → wafer
client.samples.link(
    parent_mfid=boule_sample_mfid,
    child_mfid=wafer_sample_mfid,
    relationship_type='is_part_of',   # optional
)

# Remove it
client.samples.unlink(
    parent_mfid=boule_sample_mfid,
    child_mfid=wafer_sample_mfid,
)

# Navigate
parents = client.samples.list_parents(wafer_sample_mfid)
children = client.samples.list_children(boule_sample_mfid)
```

---

## Generic link/unlink (auto-detects types)

If you have two IDs and don't want to look up their types first:

```python
# Works for dataset-sample, dataset-dataset, or sample-sample pairs
client.link(dataset_mfid, sample_mfid)
client.unlink(dataset_mfid, sample_mfid)

# A relationship type may be given for parent-child pairs only
client.link(parent_mfid, child_mfid, relationship_type='is_derived_from')
```

---

## Viewing all links for a resource

```python
# Returns immediate links for any resource MFID
links = client.get_links(dataset_mfid)
```

Each link exposes `direction` as `source`, `target`, or `undirected`. Nano also retains the legacy `relationship` alias with the corresponding `parent`, `child`, or `associated` value for compatibility with existing applications.

---

## Graph traversal

For a visual or programmatic view of the full relationship graph:

```python
# First-degree connections
graph = client.graphs.get(dataset_mfid)

# Full connected component
graph = client.graphs.get(dataset_mfid, recursive=True)

# All resources in a project
graph = client.graphs.project("MFP12345")

# As a networkx DiGraph
G = client.graphs.get(dataset_mfid, recursive=True, as_networkx=True)
```

Relationship lists and graphs are authorized views. An inaccessible starting resource returns 403, while readable graphs omit resources the caller cannot access and any edges connected to them. A smaller graph therefore does not imply that records or relationships were deleted.

---

## CLI

```bash
# Link any two resources (type auto-detected)
crucible link -p PARENT_MFID -c CHILD_MFID

# Unlink
crucible unlink MFID_A MFID_B

# View the graph for a resource
crucible tree RESOURCE_MFID
```
