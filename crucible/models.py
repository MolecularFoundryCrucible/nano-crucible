#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic models for Crucible API request and response objects.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional


class Sample(BaseModel):
    unique_id: Optional[str] = None
    sample_name: Optional[str] = None
    sample_type: Optional[str] = None
    owner_orcid: Optional[str] = None
    owner_user_id: Optional[int] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    timestamp: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Dataset(BaseModel):
    unique_id: Optional[str] = None
    dataset_name: Optional[str] = None
    public: Optional[bool] = False
    owner_user_id: Optional[int] = None
    owner_orcid: Optional[str] = None
    project_id: Optional[str] = None
    instrument_id: Optional[int] = None
    instrument_name: Optional[str] = None
    measurement: Optional[str] = None
    session_name: Optional[str] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    timestamp: Optional[str] = None
    data_format: Optional[str] = None
    file_to_upload: Optional[str] = None
    size: Optional[int] = None
    sha256_hash_file_to_upload: Optional[str] = None
    source_folder: Optional[str] = None
    json_link: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Backward-compatibility aliases (deprecated)
# ---------------------------------------------------------------------------

def __getattr__(name: str):
    import warnings
    _aliases = {
        'BaseDataset': Dataset,
        'BaseSample':  Sample,
    }
    if name in _aliases:
        warnings.warn(
            f"'{name}' is deprecated; use '{_aliases[name].__name__}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _aliases[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Project(BaseModel):
    project_id: str
    organization: str
    project_lead_email: str
    status: Optional[str] = None
    title: Optional[str] = None
    project_lead_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
