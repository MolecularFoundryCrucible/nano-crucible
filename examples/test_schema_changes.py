#!/usr/bin/env python3
"""
Test script for schema-change endpoints (Table 2).

Exercises the following endpoints affected by schema changes:
  POST  /users              — UserCreate now accepts is_service_account
  PATCH /users/{orcid}      — UserUpdate now accepts is_service_account
  GET   /users/{orcid}      — UserRead now returns is_service_account
  GET   /users              — same
  POST  /projects           — email lookup simplified (no lbl_email)
  PATCH /projects/{proj_id} — same
  GET   /account            — AccountInfo field renamed to user_unique_id
"""
import sys
from crucible import CrucibleClient
from crucible.models import Project

client = CrucibleClient()

# ── POST /users — create with is_service_account ─────────────────────
print("=== Create service-account user ===")
svc_user = client.users.create(
    {
        "first_name": "Pipeline",
        "last_name": "Bot",
        "orcid": "0000-0000-0000-9999",
        "email": "pipeline-bot@example.com",
        "is_service_account": True,
    },
    project_ids=[],
)
print(f"Created user: {svc_user}")
print(f"  is_service_account = {svc_user.get('is_service_account')}")
test_orcid = svc_user["unique_id"]

# ── PATCH /users/{orcid} — update is_service_account ─────────────────
print("\n=== Update is_service_account flag ===")
patched = client.users.update(test_orcid, is_service_account=False)
print(f"Updated user: {patched}")
print(f"  is_service_account = {patched.get('is_service_account')}")

# ── GET /users/{orcid} — verify is_service_account in response ───────
print("\n=== Get user (check is_service_account) ===")
user = client.users.get(orcid=test_orcid)
print(f"User: {user}")
print(f"  is_service_account = {user.get('is_service_account')}")

# ── GET /users — list users, check new field ──────────────────────────
print("\n=== List users ===")
users = client.users.list(limit=5)
for u in users:
    print(f"  {u.get('orcid')} — is_service_account={u.get('is_service_account')}")

# ── POST /projects — simplified email lookup (no lbl_email) ──────────
print("\n=== Create project ===")
project = Project(
    project_id="test-schema-project-4",
    organization="Test Org",
    project_lead_orcid="0000-0000-0000-0000",
)
created_project = client.projects.create(project)
print(f"Created project: {created_project}")
proj_id = created_project["project_id"]

# ── PATCH /projects/{proj_id} ─────────────────────────────────────────
print("\n=== Update project ===")
updated_project = client.projects.update(proj_id, title="Updated Title")
print(f"Updated project: {updated_project}")

# ── GET /account — AccountInfo with user_unique_id ────────────────────
print("\n=== Get account info (whoami) ===")
account = client.whoami()
print(f"Account info: {account}")
print(f"  user_unique_id = {account.get('user_unique_id')}")

print("\nDone.")
