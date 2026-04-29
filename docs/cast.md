# Batch Recipes (.crux)

The **cast** system lets you declare datasets and samples in a YAML file (`.crux`) and apply them to Crucible idempotently. This is useful for scripted pipelines, instrument automation, and bulk uploads where you want reproducible, resumable behavior.

## Why use .crux files?

- **Idempotent** — re-running the same `.crux` file won't create duplicates; already-created records are reused.
- **Resumable** — a lock file tracks which uploads and ingestion requests have completed, so interrupted runs pick up where they left off.
- **Declarative** — describe what you want, not the steps to get there.

## Running a .crux file

```bash
crucible cast my_experiment.crux
```

Preview without making changes:

```bash
crucible cast my_experiment.crux --dry-run
```

## File format

A `.crux` file has three top-level sections: `config`, `samples`, and `datasets`.

```yaml
config:
  project_id: my-project
  owner_orcid: 0000-0001-2345-6789

samples:
  - id: silicon_wafer          # local alias used for linking below
    sample_name: Silicon wafer A
    sample_type: substrate
    description: 100-orientation, 4-inch, FZ silicon

datasets:
  - dataset_name: XRD run 5
    measurement: X-ray diffraction
    instrument_name: Beamline 12.3.2
    files:
      - xrd_run5.xy
    scientific_metadata:
      wavelength_angstrom: 0.7749
      temperature_K: 300
    keywords:
      - XRD
      - powder diffraction
    samples:
      - silicon_wafer          # link to the sample defined above
```

## Linking datasets to samples

Reference the sample's `id` alias (defined in the `samples` section) in the dataset's `samples` list. The executor resolves this to the actual `smid` after creation.

## Linking datasets to each other

```yaml
datasets:
  - id: raw_data
    dataset_name: Raw XRD
    files:
      - raw.xy

  - dataset_name: Processed XRD
    files:
      - processed.xy
    parents:
      - raw_data               # establishes a parent-child link
```

## Python API

You can also build and apply `.crux` plans programmatically:

```python
from crucible.cast import Cast, CastExecutor

# Build a plan
cast = Cast(project_id="my-project")
cast.add_sample("silicon_wafer", sample_name="Silicon wafer A", sample_type="substrate")
cast.add_dataset(
    dataset_name="XRD run 5",
    files=["xrd_run5.xy"],
    samples=["silicon_wafer"],
)

# Write to a .crux file
cast.save("my_experiment.crux")

# Or apply directly
executor = CastExecutor(client)
executor.apply(cast.plan)
```

## Lock file

The cast system writes a `<recipe>.lock` file alongside the `.crux` file to track created IDs and completed uploads. Do not delete the lock file while a run is in progress. If you want to force a full re-run (e.g., after an error), delete the lock file first.
