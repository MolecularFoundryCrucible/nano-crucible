#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic models for Crucible API request and response objects.
"""

from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Literal, Optional, Union

#%% Base model

class CrucibleResource(BaseModel):
    """Shared fields common to all Crucible resources."""

    unique_id: Optional[str] = None
    public: Optional[bool] = False
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    resource_type: Optional[str] = None
    scientific_metadata: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


#%% Models

class PublicUser(BaseModel):
    """Public-safe user record embedded in resource responses."""

    unique_id: str
    username: Optional[str] = None
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True, extra='allow')


class ResourceCapabilities(BaseModel):
    """Caller-specific actions available for an exact resource response."""

    can_edit: bool
    can_manage_access: bool
    can_change_status: bool
    can_transfer: bool
    max_grant_role: Optional[Literal['viewer', 'contributor', 'editor', 'admin']] = None

    model_config = ConfigDict(from_attributes=True, extra='allow')


class InstrumentReference(BaseModel):
    """Lightweight instrument identity embedded in dataset responses."""

    unique_id: str
    instrument_id: Optional[str] = None
    instrument_name: str

    model_config = ConfigDict(from_attributes=True, extra='allow')


class ProjectReference(BaseModel):
    """Lightweight project identity embedded in dataset responses."""

    unique_id: str
    project_id: str
    title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra='allow')


class Sample(CrucibleResource):
    sample_name: Optional[str] = None
    sample_type: Optional[str] = None
    owner_orcid: Optional[str] = None
    owner: Optional[Union[str, PublicUser]] = None
    project_id: Optional[str] = None
    project_mfid: Optional[str] = None
    project: Optional[ProjectReference] = None
    project_relation: Optional[Literal['assigned', 'shared']] = None
    description: Optional[str] = None
    timestamp: Optional[str] = None
    datasets: Optional[List[Dict]] = None
    deletion_request: Optional[Dict] = None
    links: Optional[List[Dict]] = None
    capabilities: Optional[ResourceCapabilities] = None


class Dataset(CrucibleResource):
    dataset_name: Optional[str] = None
    owner_orcid: Optional[str] = None
    owner: Optional[Union[str, PublicUser]] = None
    project_id: Optional[str] = None
    project_mfid: Optional[str] = None
    instrument_name: Optional[str] = None
    instrument_id: Optional[str] = None
    instrument_mfid: Optional[str] = None
    instrument: Optional[InstrumentReference] = None
    project: Optional[ProjectReference] = None
    project_relation: Optional[Literal['assigned', 'shared']] = None
    measurement: Optional[str] = None
    data_type: Optional[str] = None
    session_name: Optional[str] = None
    data_format: Optional[str] = None
    size: Optional[int] = None
    timestamp: Optional[str] = None
    deletion_request: Optional[Dict] = None
    links: Optional[List[Dict]] = None
    capabilities: Optional[ResourceCapabilities] = None


class Instrument(CrucibleResource):
    instrument_id: Optional[str] = None
    instrument_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    owner_orcid: Optional[str] = None
    owner: Optional[Union[str, PublicUser]] = None
    location: Optional[str] = None
    description: Optional[str] = None
    instrument_type: Optional[str] = None
    other_id: Optional[str] = None
    other_id_source: Optional[str] = None
    status: Optional[str] = None
    capabilities: Optional[ResourceCapabilities] = None


class Project(BaseModel):
    project_id: str
    organization: str
    unique_id: Optional[str] = None
    lead: Optional[Dict] = None
    project_lead: Optional[str] = None
    project_lead_orcid: Optional[str] = None
    project_lead_email: Optional[str] = None
    project_lead_username: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    scientific_metadata: Optional[Dict] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    members: Optional[List['ProjectMember']] = None
    capabilities: Optional[ResourceCapabilities] = None

    model_config = ConfigDict(from_attributes=True, extra='allow')


class User(BaseModel):
    unique_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    is_service_account: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProjectMember(User):
    '''A project member's profile plus their standing role in the project.'''

    role: str


class AccessGrant(BaseModel):
    '''One principal's access to a resource (GET/PUT /resources/{mfid}/access/...).'''

    principal_id: str
    principal_type: Literal[
        'user', 'service_account', 'project', 'instrument', 'public', 'system', 'unknown'
    ]
    permission: Literal['viewer', 'contributor', 'editor', 'admin', 'owner']
    slug: Optional[str] = None
    display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @property
    def principal(self) -> str:
        """Deprecated alias for :attr:`principal_id`."""
        return self.principal_id

    @property
    def kind(self) -> str:
        """Deprecated alias for :attr:`principal_type`."""
        return self.principal_type

    @property
    def effective_permission(self) -> str:
        """Deprecated alias for :attr:`permission`."""
        return self.permission


class EffectiveResourceAccess(BaseModel):
    '''A user's effective permission on one resource.'''

    resource_mfid: str
    user_id: str
    effective_access: Literal[
        'none', 'viewer', 'contributor', 'editor', 'admin', 'owner', 'platform_admin'
    ]

    model_config = ConfigDict(from_attributes=True)


class OwnershipTransfer(BaseModel):
    '''Result of POST /resources/{mfid}/transfer_ownership.'''

    resource_id: str
    previous_owner: Optional[User] = None
    new_owner: User

    model_config = ConfigDict(from_attributes=True)


class ProjectReassignment(BaseModel):
    '''Result of POST /resources/{mfid}/project.'''

    resource_id: str
    previous_project_id: Optional[str] = None
    new_project_id: str

    model_config = ConfigDict(from_attributes=True)


class AssociatedFile(BaseModel):
    '''A file attached to a dataset.'''

    mfid: Optional[str] = None
    dataset_mfid: Optional[str] = None
    filename: Optional[str] = None
    storage_path: Optional[str] = None
    storage_backend: Optional[str] = 'gcs'
    access_note: Optional[str] = None
    size: Optional[int] = None
    sha256_hash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


class DeletionRequest(BaseModel):
    '''A pending or resolved request to delete a resource.'''

    id: Optional[int] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    project_id: Optional[str] = None
    requester_id: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None          # "pending" | "approved" | "rejected"
    request_time: Optional[str] = None
    review_time: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


class JoinRequest(BaseModel):
    '''A pending or resolved request to join an access group (currently always a project).'''

    id: Optional[int] = None
    group_name: Optional[str] = None
    requester_id: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None          # "pending" | "approved" | "rejected"
    request_time: Optional[str] = None
    review_time: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


class ResourceSearchResult(BaseModel):
    """A single result from search_metadata() (GET /resources/metadata/search).

    Returned by client.datasets.search_metadata(), client.samples.search_metadata(), etc.
    Results are ranked by relevance and may span datasets, samples, and instruments.
    """

    unique_id: Optional[str] = None
    resource_type: Optional[str] = None
    name: Optional[str] = None
    owner_orcid: Optional[str] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    rank: Optional[float] = None
    scientific_metadata: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


class DeletionAuditLog(BaseModel):
    '''Permanent record of a hard-deleted resource. Written before deletion; survives it.'''

    id: Optional[int] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    project_id: Optional[str] = None
    requester_id: Optional[str] = None
    reason: Optional[str] = None
    request_time: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    review_time: Optional[str] = None
    deleted_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')
