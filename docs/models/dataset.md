# Dataset

A dataset is the primary data object in Crucible. It pairs a file (or set of files) with structured metadata describing what was measured, how, and when.

## Field guidance

### Measurement vs. data_type

These two fields serve different purposes:

- **`measurement`** should use terminology that is interpretable across institutions — e.g., `"X-ray diffraction"`, `"UV-Vis spectroscopy"`, `"SEM imaging"`. Think of this as the *technique*.
- **`data_type`** is more institution- or instrument-specific — e.g., `"4D-STEM"`, `"EELS map"`, `"powder diffractogram"`. Think of this as the *output format or data product*.

### timestamp vs. creation_time

- **`timestamp`** is the time the data was *collected*. Set this yourself to reflect when the experiment ran.
- **`creation_time`** is when the Crucible record was created. This is assigned automatically by the server and is read-only.

### Upload-only fields

`file_to_upload`, `size`, and `sha256_hash_file_to_upload` are used by the client during upload. They are not stored as queryable metadata on the server after upload completes.

## Example

```python
from crucible.models import Dataset

dataset = Dataset(
    dataset_name="Au NP SAXS run 7",
    measurement="Small-angle X-ray scattering",
    data_type="1D SAXS profile",
    instrument_name="ALS Beamline 7.3.3",
    session_name="2024-03-beamtime",
    project_id="MFP12345",
    timestamp="2024-03-15T14:30:00",
    public=False,
)

result = client.datasets.create(
    dataset=dataset,
    files_to_upload=["saxs_run7.dat"],
    scientific_metadata={"energy_keV": 10.0, "q_range": "0.01-0.3"},
    keywords=["SAXS", "gold nanoparticles"],
)
```
