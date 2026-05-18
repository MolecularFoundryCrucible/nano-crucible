#!/usr/bin/env python3
"""Exercise all ACL-affected endpoints.

Usage:
    python examples/test_acl_endpoints.py admin
    python examples/test_acl_endpoints.py self
"""

import sys
import base64
import os
import tempfile
from crucible import CrucibleClient
from crucible.models import Dataset, Instrument

mode     = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("admin", "self") else sys.exit("Usage: test_acl_endpoints.py <admin|self>")
is_admin = mode == "admin"

client     = CrucibleClient()
account    = client.whoami()
my_orcid   = account.get("user_unique_id") or account.get("access_group_name")
projects   = client.projects.list()
project_id = projects[0]["project_id"] if projects else None

print(f"Mode: {mode} | ORCID: {my_orcid} | Project: {project_id}\n")


# ── create fixtures ───────────────────────────────────────────────────────────
# sample     = client.samples.create(sample_name="acl-test-sample-3", project_id=project_id)
# print(f'{sample=}')
# ds_result  = client.datasets.create(Dataset(dataset_name="acl-test-dataset-3", project_id=project_id, measurement="test"))
# print(f'{ds_result=}')
ds2_result = client.datasets.create(Dataset(dataset_name="acl-test-child-3",   project_id=project_id, measurement="test"))
print(f'{ds2_result=}')

# sample_id  = sample["unique_id"]
# dsid       = ds_result["dsid"]
child_dsid = ds2_result["dsid"]

sample_id = '0tf7shn2m5xkn000jymh0by7bg'
dsid = '0tf7tv9pt5x35000g346xwty7g'

# ── datasets ──────────────────────────────────────────────────────────────────
# print(client.datasets.list(limit=5))
# print(client.datasets.get(dsid))
# print(client.datasets.update(dsid, dataset_name="acl-test-updated"))
# print(client.datasets.get_scientific_metadata(dsid))
# print(client.datasets.add_scientific_metadata(dsid, {"k": 1}))
# print(client.datasets.update_scientific_metadata(dsid, {"k": 2}))
# print(client.datasets.get_thumbnails(dsid))
# print(client.datasets.get_associated_files(dsid))
# print(client.datasets.get_keywords(dsid))
# print(client.datasets.add_keyword(dsid, "acl-test"))
# print(client.datasets.add_sample(dsid, sample_id))
# print(client.samples.list(dataset_id=dsid))
# print(client.datasets.link_parent_child(dsid, child_dsid))
# print(client.datasets.list_children(dsid))
# print(client.datasets.list_parents(child_dsid))


# ── admin-only dataset endpoints ──────────────────────────────────────────────
#if is_admin:
   # print(client.datasets.get_access_groups(dsid))
    # print(client.datasets.add_access_group(dsid, "MFP00000"))
    # print(client.datasets.remove_sample(dsid, sample_id))
    # print(client.datasets.remove_child(dsid, child_dsid))

# # ── samples ───────────────────────────────────────────────────────────────────
print(client.samples.list(limit=5))
print(client.samples.get(sample_id))
print(client.datasets.list(sample_id=sample_id))

# ── instruments ───────────────────────────────────────────────────────────────
print(client.instruments.create(Instrument(instrument_name="acl-test-inst-3", owner='x', location="y")))

# ── users (admin or self) ─────────────────────────────────────────────────────
print(len(client.users.list_datasets(my_orcid)))
print(client.users.check_dataset_access(my_orcid, dsid))

# ── misc ──────────────────────────────────────────────────────────────────────
print(client.datasets.search_scientific_metadata("test"))
