# Models

Pydantic v2 models for all Crucible API objects. Import them from `crucible.models`. The core record models (`Project`, `Dataset`, `Sample`, `Instrument`, `User`, `PublicUser`, `InstrumentReference`, `ProjectReference`, `ResourceCapabilities`, `EffectiveResourceAccess`) are also importable directly from `crucible`.

```python
from crucible.models import Dataset, Sample, Project, Instrument, InstrumentReference, ProjectReference, User, PublicUser, ResourceCapabilities, DeletionRequest, FacetResponse
```

::: crucible.models.Project

::: crucible.models.Dataset

::: crucible.models.InstrumentReference

::: crucible.models.ProjectReference

::: crucible.models.Sample

::: crucible.models.Instrument

::: crucible.models.User

::: crucible.models.PublicUser

::: crucible.models.ResourceCapabilities

::: crucible.models.EffectiveResourceAccess

::: crucible.models.FacetBucket

::: crucible.models.FacetResponse

::: crucible.models.ServiceAccountAdmin

::: crucible.models.ServiceAccountKeyStatus

::: crucible.models.EntryCapabilities

::: crucible.models.DeletionRequest

::: crucible.models.DeletionRequestCapabilities

::: crucible.models.JoinRequest

::: crucible.models.JoinRequestCapabilities

::: crucible.models.Pipeline

::: crucible.models.PostprocessingRun
