# Data Models

nano-crucible uses [Pydantic v2](https://docs.pydantic.dev/latest/) models to represent API objects. All models live in `crucible.models` and are exported directly from the top-level `crucible` package.

```python
from crucible.models import Dataset, Sample, Project, Instrument
# or equivalently:
from crucible import Dataset, Sample, Project, Instrument
```

## Overview

| Model | Description |
|---|---|
| [`Project`](project.md) | Top-level organizational unit and access group |
| [`Dataset`](dataset.md) | A measurement file plus structured and scientific metadata |
| [`Sample`](sample.md) | A physical or computational sample with provenance tracking |
| [`Instrument`](instrument.md) | A registered piece of equipment |

## How models are used

Models are used when **creating** objects. Pass a model instance to `client.datasets.create()`, `client.projects.create()`, etc.

```python
from crucible.models import Dataset

ds = Dataset(
    dataset_name="My experiment",
    measurement="X-ray diffraction",
    project_id="my-project",
)
result = client.datasets.create(dataset=ds)
```

API responses are returned as plain `dict` objects (not model instances), so you can work with them directly or validate them into a model if needed:

```python
raw = client.datasets.get("ds-abc123")
ds = Dataset(**raw)
```

## Field defaults

All fields in every model are `Optional` with a `None` default, except `Project.project_id` and `Project.organization` which are required. The API will reject requests that are missing fields it requires server-side.
