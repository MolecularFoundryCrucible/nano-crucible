# DeletionOperations

Access via `client.deletions`. Anyone who may request deletion of a record files a request with a reason; platform administrators review it. `delete()` removes a record directly and is for administrators only.

```python
request = client.deletions.request(dataset_mfid, reason="Superseded dataset")
client.deletions.get(request["id"])
```

::: crucible.resources.deletion.DeletionOperations
    options:
      members:
        - request
        - list
        - get
        - approve
        - reject
        - list_deleted
        - get_deleted
        - delete
