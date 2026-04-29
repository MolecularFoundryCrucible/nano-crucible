# Sample

A sample represents a physical or computational material in Crucible. Samples can be organized into parent-child hierarchies to capture provenance, and linked to the datasets measured from them.

## Notes

### sample_type

`sample_type` is a free-text field with no enforced vocabulary. It is recommended to use consistent values within a project to make samples filterable and comparable (e.g., always use `"thin film"` rather than mixing `"film"`, `"thin-film"`, and `"deposited layer"`).

### timestamp

Use `timestamp` to record when the sample was created or prepared, not when the Crucible record was created. `creation_time` is assigned automatically by the server.

### Provenance hierarchy

Use `client.samples.link(parent_id, child_id)` to connect samples in a parent-child relationship after creation. You can also pass `parent_id` or `child_id` directly to `client.samples.create()`.

## Example

```python
from crucible.models import Sample

# Parent sample
boule = client.samples.create(
    sample_name="Silicon boule #3",
    sample_type="bulk crystal",
    project_id="MFP12345",
    description="CZ silicon, p-type, resistivity 1-10 Ω·cm",
)

# Child sample — a wafer cut from the boule
wafer = client.samples.create(
    sample_name="Silicon wafer A",
    sample_type="substrate",
    project_id="MFP12345",
    description="100-orientation, 4-inch, double-side polished",
)

# Establish the parent-child relationship
client.samples.link(parent_id=boule["smid"], child_id=wafer["smid"])
```
