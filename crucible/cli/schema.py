#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Canonical field definitions for Dataset and Sample.

Single source of truth for:
  - Display order and labels  (used by _show_dataset / _show_sample)
  - Edit order                (used by _edit_dataset / _edit_sample)
  - Updatable field set       (used by _dataset_updatable_fields / _sample_updatable_fields)
  - JSON output key order     (used by --json flag)
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FieldDef:
    key:      str   # API/model dict key
    label:    str   # Human-readable display label
    editable: bool  # Can be changed via update / edit
    verbose:  bool  # Hidden in default view; shown with --verbose


DATASET_FIELDS: List[FieldDef] = [
    FieldDef('dataset_name',               'Name',          editable=True,  verbose=False),
    FieldDef('unique_id',                  'MFID',          editable=False, verbose=False),
    FieldDef('measurement',                'Measurement',   editable=True,  verbose=False),
    FieldDef('session_name',               'Session',       editable=True,  verbose=False),
    FieldDef('instrument_name',            'Instrument',    editable=True,  verbose=False),
    FieldDef('project_id',                 'Project',       editable=True,  verbose=False),
    FieldDef('timestamp',                  'Timestamp',     editable=True,  verbose=False),
    FieldDef('description',                'Description',   editable=True,  verbose=False),
    FieldDef('public',                     'Public',        editable=True,  verbose=True),
    FieldDef('owner_orcid',                'Owner ORCID',   editable=False, verbose=True),
    FieldDef('owner_user_id',              'Owner ID',      editable=False, verbose=True),
    FieldDef('data_format',                'Data Format',   editable=False, verbose=True),
    FieldDef('instrument_id',              'Instrument ID', editable=False, verbose=True),
    FieldDef('size',                       'Size',          editable=False, verbose=True),
    FieldDef('source_folder',              'Source',        editable=False, verbose=True),
    FieldDef('sha256_hash_file_to_upload', 'SHA256',        editable=False, verbose=True),
    FieldDef('creation_time',              'Created',       editable=False, verbose=True),
    FieldDef('modification_time',          'Modified',      editable=False, verbose=True),
]

SAMPLE_FIELDS: List[FieldDef] = [
    FieldDef('sample_name',                'Name',          editable=True,  verbose=False),
    FieldDef('unique_id',                  'MFID',          editable=False, verbose=False),
    FieldDef('sample_type',                'Type',          editable=True,  verbose=False),
    FieldDef('project_id',                 'Project',       editable=True,  verbose=False),
    FieldDef('timestamp',                  'Timestamp',     editable=True,  verbose=False),
    FieldDef('description',                'Description',   editable=True,  verbose=False),
    FieldDef('owner_orcid',                'Owner ORCID',   editable=False, verbose=True),
    FieldDef('owner_user_id',              'Owner ID',      editable=False, verbose=True),
    FieldDef('creation_time',              'Created',       editable=False, verbose=True),
    FieldDef('modification_time',          'Modified',      editable=False, verbose=True),
]


# Helpers
def editable_keys(fields: List[FieldDef]) -> List[str]:
    """Ordered list of keys that can be set via update / edit."""
    return [f.key for f in fields if f.editable]


def visible_fields(fields: List[FieldDef], verbose: bool = False) -> List[FieldDef]:
    """Fields to show at the given verbosity level (default view or --verbose)."""
    return [f for f in fields if verbose or not f.verbose]


def ordered_dict(fields: List[FieldDef], data: dict,
                 verbose: bool = True, editable_only: bool = False) -> dict:
    """Build a canonically-ordered dict from *data*.

    Args:
        fields:       DATASET_FIELDS or SAMPLE_FIELDS
        data:         raw API response dict
        verbose:      include verbose fields
        editable_only: only include editable fields (for edit JSON)
    """
    return {
        f.key: data.get(f.key)
        for f in visible_fields(fields, verbose)
        if not editable_only or f.editable
    }
