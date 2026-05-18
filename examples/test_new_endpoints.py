#!/usr/bin/env python3
"""
Test script for new endpoints (Table 1).

Exercises the following non-DELETE endpoints:
  GET  /users
  GET  /users/{orcid}
  POST /users
  PATCH /users/{orcid}
  GET  /users/{orcid}/datasets
  GET  /users/{orcid}/datasets/{dsid}
  POST /users/{orcid}/access_groups/{group_name}
  PATCH /datasets/{dsid}/ingest/{reqid}
  GET  /datasets/{dsid}/access_groups
  POST /datasets/{dsid}/access_groups
  GET  /deletion_requests
  GET  /deletion_requests/{request_id}
  PATCH /deletion_requests/{request_id}
"""
import sys
from crucible import CrucibleClient

account = sys.argv[1]
your_orcid = sys.argv[2]

client = CrucibleClient()

# ── Users ─────────────────────────────────────────────────────────────
# GET /users
if account == 'admin':
    print("=== List users ===")
    users = client.users.list(limit=5)
    print(f"Found {len(users)} users")
    for u in users:
        print(f"  {u.get('first_name')} {u.get('last_name')} — {u.get('orcid')}")

# POST /users  (create / upsert)
if account == 'admin':
    print("\n=== Create user ===")
    new_user = client.users.create(
        {
            "first_name": "Test",
            "last_name": "User",
            "orcid": "0000-0000-0000-0000",
            "email": "testuser@example.com",
        },
        project_ids=[],
    )
    print(f"Created/updated user: {new_user}")
    test_orcid = new_user["unique_id"]

# GET /users/{orcid}
if account == 'admin':
    print("\n=== Get user by ORCID ===")
    user = client.users.get(orcid=test_orcid)
    print(f"User: {user}")

print("\n=== Get your user by ORCID ===")
user = client.users.get(orcid=your_orcid)
print(f"User: {user}")

# PATCH /users/{orcid}
if account == 'admin':
    print("\n=== Update user ===")
    updated = client.users.update(test_orcid, first_name="Updated")
    print(f"Updated user: {updated}")



# GET /users/{orcid}/datasets
ds_ids = None
if account == 'admin':
    print("\n=== List user datasets ===")
    ds_ids = client.users.list_datasets(test_orcid)
    print(f"Accessible dataset IDs: {ds_ids}")

print("\n=== List your user datasets ===")
your_ds_ids = client.users.list_datasets(your_orcid)
print(f"Accessible dataset IDs: {your_ds_ids}")


# GET /users/{orcid}/datasets/{dsid}
if ds_ids:
    print("\n=== Check dataset access ===")
    if account == 'admin':
        access = client.users.check_dataset_access(test_orcid, ds_ids[0])
        print(f"Access for {ds_ids[0]}: {access}")

if your_ds_ids:
    print("\n=== Check your dataset access ===")
    access = client.users.check_dataset_access(your_orcid, your_ds_ids[0])
    print(f"Access for {your_ds_ids[0]}: {access}")

# POST /users/{orcid}/access_groups/{group_name}
if account == 'admin':
    print("\n=== Add user to access group ===")
    ag_result = client.users.add_to_access_group(test_orcid, "test-group")
    print(f"Access group result: {ag_result}")

# ── Datasets — access groups ─────────────────────────────────────────
if ds_ids:
    dsid = ds_ids[0]

    # GET /datasets/{dsid}/access_groups
    print("\n=== Get dataset access groups ===")
    groups = client.datasets.get_access_groups(dsid)
    print(f"Access groups for {dsid}: {groups}")

    # POST /datasets/{dsid}/access_groups
    print("\n=== Add access group to dataset ===")
    add_ag = client.datasets.add_access_group(dsid, "test-group", read=True, write=False)
    print(f"Added access group: {add_ag}")

# ── Datasets — ingestion status ──────────────────────────────────────
# PATCH /datasets/{dsid}/ingest/{reqid}
# (Uncomment and fill in real IDs to test)
# print("\n=== Update ingestion status ===")
# result = client.datasets.update_ingestion_status(
#     dsid="<dataset-id>",
#     reqid="<request-id>",
#     status="complete",
# )
# print(f"Ingestion status update: {result}")

# ── Deletion requests ─────────────────────────────────────────────────
if account == 'admin':
    # GET /deletion_requests
    print("\n=== List deletion requests ===")
    del_reqs = client.deletions.list()
    print(f"Found {len(del_reqs)} deletion requests")

    # GET /deletion_requests/{request_id}
    if del_reqs:
        rid = del_reqs[0]["id"]
        print(f"\n=== Get deletion request {rid} ===")
        dr = client.deletions.get(rid)
        print(f"Deletion request: {dr}")

        # PATCH /deletion_requests/{request_id}  (approve)
        if dr["status"] == "pending":
            print(f"\n=== Approve deletion request {rid} ===")
            approved = client.deletions.approve(rid, reviewer_notes="Approved via test script")
            print(f"Approved: {approved}")

print("\nDone.")
