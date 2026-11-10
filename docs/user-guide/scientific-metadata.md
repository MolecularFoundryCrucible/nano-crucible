# Scientific Metadata

Scientific metadata lets you attach experiment-specific parameters to a dataset as a free-form JSON object. Unlike the structured fields on the `Dataset` model (measurement type, instrument, etc.), scientific metadata can hold any key-value pairs relevant to your experiment.

## Adding scientific metadata

Pass `scientific_metadata` at dataset creation time:

```python
result = client.datasets.create(
    dataset=Dataset(dataset_name="CVs at 50 mV/s", project_id="my-project"),
    files=["cv_50mVs.txt"],
    scientific_metadata={
        "scan_rate_mV_s": 50,
        "electrolyte": "0.1 M KOH",
        "working_electrode": "Pt disk",
        "potential_range_V": [-0.2, 1.2],
    },
)
```

Or merge new keys into an existing dataset's metadata:

```python
client.datasets.update_scientific_metadata(
    "0tkn2knjast3h0008nyq9zps2c",
    metadata={"temperature_K": 300, "pressure_bar": 1.013},
)
```

To replace all existing metadata entirely, use `replace_scientific_metadata()`:

```python
client.datasets.replace_scientific_metadata(
    "0tkn2knjast3h0008nyq9zps2c",
    metadata={"temperature_K": 300, "pressure_bar": 1.013},
)
```

## Retrieving scientific metadata

```python
meta = client.datasets.get_scientific_metadata("0tkn2knjast3h0008nyq9zps2c")
print(meta)
# {'temperature_K': 300, 'pressure_bar': 1.013, ...}
```

For a full dataset record including metadata:

```python
ds = client.datasets.get("0tkn2knjast3h0008nyq9zps2c", include_metadata=True)
```

## Searching by scientific metadata

Full-text search across all scientific metadata in your accessible datasets:

```python
results = client.datasets.search_metadata("temperature", limit=20)
```

The search is ranked and operates across all key names and string values in the metadata store.

## CLI

```bash
# Attach or replace scientific metadata from a JSON string
crucible dataset update DATASET_MFID --metadata '{"temperature_K": 300}'

# Merge new keys into existing metadata (keeps untouched keys)
crucible dataset update DATASET_MFID --metadata '{"pressure_bar": 1.0}'

# Replace all metadata (overwrites everything)
crucible dataset update DATASET_MFID --metadata '{"new_key": "value"}' --overwrite

# Search
crucible dataset search-metadata "temperature" --limit 10

# Get a dataset record including metadata
crucible dataset get DATASET_MFID --include-metadata
# or as JSON:
crucible dataset get DATASET_MFID --json
```

## Tips

- Use consistent key naming within a project to make searching and filtering reliable (e.g., always `temperature_K` rather than mixing `temperature`, `temp_K`, `T`).
- Store numeric values as numbers, not strings — this keeps metadata useful for downstream analysis.
- Avoid deeply nested structures; flat or one-level-deep objects work best with the search index.
