#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic models for Crucible API request and response objects.
"""

from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import Dict, List, Optional

#%% Models

class Sample(BaseModel):
    '''
    Physical or computational sample. Samples can form many to many relationships
    with samples and other datasets to capture parent-child relationships and 
    information about the sample synthesis or measured properties. 

    Attributes:                                                                                                                                                                                                                                                                                        
         unique_id: System-assigned unique identifier for the sample generated with the mfid package.                                                                                                                                                                                                                               
         sample_name: Human-readable name.                                                                                                                                                                                                                                                              
         sample_type: Categorical label (e.g., ``"substrate"``, ``"thin film"``). Currently this allows any string.  It is recommended to use consistent sample types within a project.                                                                                                                                                                                                                
         owner_orcid: ORCID of the person who owns this sample.                                                                                                                                                                                                                                     
         timestamp: User-settable date for the sample (ISO 8601). Also accepted                                                                                                                                                                                                                         
             as ``date_created`` from legacy API responses.                                                                                                                                                                                                                                             
         creation_time: Server-assigned creation timestamp (read-only).                                                                                                                                                                                                                                 
         modification_time: Server-assigned last-modification timestamp (read-only).                                                                                                                                                                                                                    
         project_id: ID of the project this sample belongs to.                                                                                                                                                                                                                                          
         description: Free-text description of the sample.                                                                                                                                                                                                                                              
         links: Raw list of link objects returned by the API when                                                                                                                                                                                                                                       
             ``include_links=True`` is passed to the get endpoint. 

    '''
    unique_id: Optional[str] = None
    sample_name: Optional[str] = None
    sample_type: Optional[str] = None
    owner_orcid: Optional[str] = None
    # timestamp: user-settable date; accepts legacy 'date_created' from the API
    # until the server-side rename is complete
    timestamp: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("timestamp", "date_created")
    )
    # server-assigned; backfilled on existing records, present on new ones
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    resource_type: Optional[str] = None
    scientific_metadata: Optional[Dict] = None
    datasets: Optional[List[Dict]] = None
    deletion_request: Optional[Dict] = None
    links: Optional[List[Dict]] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


class Dataset(BaseModel):
    '''
    Dataset record plus optional file payload. 
    '''
    unique_id: Optional[str] = None
    dataset_name: Optional[str] = None
    public: Optional[bool] = False
    owner_orcid: Optional[str] = None
    project_id: Optional[str] = None
    instrument_name: Optional[str] = None
    measurement: Optional[str] = None
    data_type: Optional[str] = None
    session_name: Optional[str] = None
    timestamp: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("timestamp", "creation_date")
    )
    # server-assigned; backfilled on existing records, present on new ones
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    data_format: Optional[str] = None
    file_to_upload: Optional[str] = None
    size: Optional[int] = None
    sha256_hash_file_to_upload: Optional[str] = None
    source_folder: Optional[str] = None
    resource_type: Optional[str] = None
    scientific_metadata: Optional[Dict] = None
    deletion_request: Optional[Dict] = None
    links: Optional[List[Dict]] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')

class Project(BaseModel):
    '''
    Represents a collection of related datasets and samples within the platform.
    For user facilities, this roughly maps to a user proposal but can be used for other use cases as well. 
    Projects are also used as access groups to control
    which Crucible users have access to which datasets and samples. 

    Attributes:
        project_id: Unique but human-readable name for the project. (Historically this was the proposal_id with an organizational prefix, eg. MFP00000)
        organization: Organization or institution leading the project.
        project_lead_orcid: ORCID of the project lead. This is used to link the project to a user in the system and is required for project creation.
        project_lead_email: Backward-compat field; not sent to the API.
        status: Status of the project. (eg. "active", "completed").
        title: Optional descriptive title for the project.
        project_lead_name: Name of the project lead. This is populated based on the project_lead_orcid.
    '''
    project_id: str
    organization: str
    project_lead_orcid: Optional[str] = None
    project_lead_email: Optional[str] = None  # kept for backward compat; not sent to API
    status: Optional[str] = None
    title: Optional[str] = None
    project_lead_name: Optional[str] = None
    lead: Optional[Dict] = None
    scientific_metadata: Optional[Dict] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra='allow')


class User(BaseModel):
    '''
    Model for Crucible platform users. Includes both human users and service accounts. 

    Attributes:
        id: Internal database ID for the user (read-only).
        unique_id: Unique identifier for the user account. This is ORCID for human users and mfid-generated ID for service accounts.
        first_name: First name of the user.
        last_name: Last name of the user.
        email: Email address of the user.
        is_service_account: Whether this user account is a service account.
    '''
    id: Optional[int] = None
    unique_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("unique_id", "orcid"),
    )
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    is_service_account: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @property
    def orcid(self) -> Optional[str]:
        """Backward-compat alias for unique_id."""
        return self.unique_id


class Instrument(BaseModel):
    '''
    The instrument used to collect or generate the data. 
    Attributes:
        unique_id: Unique identifier for the instrument generated with mfid.
        instrument_name: Name of the instrument.
        manufacturer: Manufacturer of the instrument.
        model: Model of the instrument.
        owner: Organizational owner of the instrument. (eg. LBNL MF NCEM for Lawrence Berkeley National Laboratory, Molecular Foundry, National Center for Electron Microscopy)
        location: Physical location of the instrument. (eg. 72-123 for Building 72, room 123 at LBNL)
        description: Free-text description of the instrument.
        instrument_type: Categorical label for the type of instrument. Currently not restrictive.
        other_id: Optional field for storing an additional identifier for the instrument (eg. an internal inventory ID or a Research Resource Identifier (RRID)).
        other_id_source: If other_id is used, this field can be used to specify the source or type of the other_id (eg. "internal_inventory", "RRID").
        resource_type: The type of resource. This will be set to "instrument" for instrument records.
        creation_time: Server-assigned creation timestamp (read-only).
        modification_time: Server-assigned last-modification timestamp (read-only).
    '''
    # id: Optional[int] = None
    unique_id: Optional[str] = None
    instrument_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    owner: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    instrument_type: Optional[str] = None
    other_id: Optional[str] = None
    other_id_source: Optional[str] = None
    resource_type: Optional[str] = None
    creation_time: Optional[str] = None
    modification_time: Optional[str] = None
    scientific_metadata: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True)


class DeletionRequest(BaseModel):
    '''
    A pending or resolved request to delete a resource. Status is one of pending, approved, or rejected.
    Multiple deletion requests can be made for the same resource. Pending deletion requests will not
    appear in search results, but will still exist in the database until approved.

    Attributes:
        resource_type: The type of resource to be deleted ("dataset", "sample", "project", "instrument")
        resource_id: The unique identifier (mfid) of the resource to be deleted
        resource_name: The human-readable name of the resource to be deleted (for reference only; not used by the API)
        requester_id: The unique identifier (orcid or service account) of the user who made the deletion request
        reason: The reason provided by the requester for why the resource should be deleted
        status: The status of the deletion request ("pending", "approved", "rejected")
        request_time: Timestamp of when the deletion request was made (ISO 8601)
        review_time: Timestamp of when the deletion request was reviewed (ISO 8601; null if still pending)
        reviewer_id: The unique identifier (orcid or service account) of the user who reviewed the deletion request (null if still pending)
        reviewer_notes: Optional notes provided by the reviewer when approving or rejecting the deletion request
    '''  

    id: Optional[int] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    requester_id: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None          # "pending" | "approved" | "rejected"
    request_time: Optional[str] = None
    review_time: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra='allow')


#%% Backward-compatibility aliases (deprecated)

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
