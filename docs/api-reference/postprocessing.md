# PostprocessingOperations

Access via `client.postprocessing`. Start a run with `client.datasets.postprocess()`, then follow it here. A retried request that repeats an `idempotency_key` returns the original run instead of starting another, so automated flows should pass a stable key per task.

```python
for pipeline in client.postprocessing.pipelines():
    print(pipeline["name"], pipeline["description"])

run = client.datasets.postprocess(
    dataset_mfid, "mosaic_stitch",
    idempotency_key=f"{flow_run_id}:mosaic_stitch:{dataset_mfid}",
)
run = client.postprocessing.get(run["run_id"])
```

::: crucible.resources.postprocessing.PostprocessingOperations
    options:
      members:
        - pipelines
        - list
        - get
        - update
