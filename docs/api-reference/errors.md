# Errors

Errors the client raises, importable from `crucible`.

```python
from crucible import CrucibleAPIError, RemovedError

try:
    client.datasets.get(dataset_mfid)
except CrucibleAPIError as exc:
    print(exc.status, exc.code, exc.detail, exc.request_id)
```

`CrucibleAPIError` is raised when the API answers with an error status. It subclasses `requests.HTTPError`, so existing handlers keep working. Quote `request_id` when reporting a problem.

`RemovedError` is raised when code calls a method, parameter, or setting removed in 4.0.0. It subclasses `TypeError`, and its message names the replacement.

::: crucible.errors.CrucibleAPIError
    options:
      members: false

::: crucible.errors.RemovedError
