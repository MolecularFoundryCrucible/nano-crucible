# AccessGroupOperations

Access via `client.access_groups`. Project join requests: any signed-in user can ask to join a project, follow the request, and withdraw it. Project editors and above, and platform administrators, review requests and choose the role to grant, which must be below their own.

```python
req = client.access_groups.request_join("thin-films", reason="XRD campaign")

queue = client.access_groups.list_join_requests(scope="reviewable", status="pending")
client.access_groups.approve_join_request(queue[0]["id"], role="viewer")

counts = client.access_groups.join_request_facets("project", scope="reviewable", status="pending")
```

::: crucible.resources.access_groups.AccessGroupOperations
    options:
      members:
        - request_join
        - list_join_requests
        - join_request_facets
        - get
        - approve_join_request
        - reject_join_request
        - withdraw_join_request
