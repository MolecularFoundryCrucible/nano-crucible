#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset resource operations for Crucible API.

Provides organized access to dataset-related API endpoints.
"""

import os
import re
import logging
import requests
import warnings
from pathlib import Path
from typing import Optional, List, Dict, Sequence, Union

import mfid

# internal modules
from .base import BaseResource
from .capabilities import AccessControlMixin, OwnershipMixin, ProjectAssignmentMixin
from ..constants import DEFAULT_LIMIT
from ..utils.deprecation import _deprecated, _deprecated_parameter
from ..utils.identifiers import is_mfid, require_canonical_identifier
from ..models import AssociatedFile

# upload/download
from .gcs.upload import upload_file_gcs

# set up logging
logger = logging.getLogger(__name__)


class DatasetOperations(ProjectAssignmentMixin, OwnershipMixin, AccessControlMixin, BaseResource):
    """Dataset-related API operations.

    Access via: client.datasets.get(), client.datasets.list(), etc.
    """

    @staticmethod
    def _parse(raw: Dict) -> Dict:
        """Validate a raw API response dict through the Dataset Pydantic model.

        Normalises field aliases (e.g. creation_date → timestamp) and preserves
        any extra fields returned by the server (keywords, scientific_metadata, …).
        """
        from ..models import Dataset
        return Dataset.model_validate(raw).model_dump()

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def get(self, dataset_mfid: str, include_metadata: bool = False,
            include_links: bool = False, include_owner: bool = True) -> Dict:
        """Get a dataset by its canonical MFID.

        Args:
            dataset_mfid (str): Dataset MFID
            include_metadata (bool): Whether to include scientific metadata
            include_links (bool): Whether to include immediate parent/child/associated links
            include_owner (bool): Resolve owner_orcid into a public-safe user object (default: True)

        Returns:
            Dict: Dataset object with optional metadata and links
        """
        return self._get_by_mfid(
            dataset_mfid,
            include_metadata=include_metadata,
            include_links=include_links,
            include_owner=include_owner,
        )

    def _get_by_mfid(self, dataset_mfid: str, include_metadata: bool = False,
                     include_links: bool = False,
                     include_owner: bool = True) -> Dict:
        """Get a dataset through its canonical single-resource route."""
        if not is_mfid(dataset_mfid):
            raise ValueError("dataset_mfid must be an exact 26-character MFID.")
        params = {}
        if include_links:
            params['include_links'] = True
        if include_metadata:
            params['include_metadata'] = True
        if include_owner:
            params['include_owner'] = True

        raw = self._request('get', f'/datasets/{dataset_mfid}', params=params or None)
        if raw is None:
            return None
        return self._parse(require_canonical_identifier(raw, 'dataset'))


    @_deprecated_parameter('sample_id', 'sample_mfid')
    def list(self, sample_mfid: Optional[str] = None, include_metadata: bool = False,
             include_links: bool = False, include_owner: bool = False,
             limit: int = DEFAULT_LIMIT, offset: int = 0,
             accessible_to_user: Optional[Union[str, Sequence[str]]] = None,
             accessible_to_project: Optional[Union[str, Sequence[str]]] = None,
             instrument_mfid: Optional[str] = None,
             project_id: Optional[str] = None,
             project_mfid: Optional[str] = None,
             project_scope: Optional[str] = None,
             **kwargs) -> List[Dict]:
        """List datasets with optional filtering and automatic pagination.

        Args:
            sample_mfid (str, optional): If provided, returns datasets for this sample
            limit (int): Maximum total results to return (default: 100). Larger
                         requests are handled transparently by following the
                         server's keyset cursor. Pass None to fetch all matches.
            offset (int): Deprecated. The /datasets collection uses keyset
                          pagination and ignores offset, including when filtered
                          by sample_mfid.
            include_metadata (bool): Include scientific metadata in results
            include_links (bool): Include linked resources (parents, children, associated) per dataset
            include_owner (bool): Resolve owner_orcid into a public-safe user object per dataset
            accessible_to_user: User reference or references whose effective access
                                must include every result
            accessible_to_project: Project reference or references whose direct access
                                   must include every result
            instrument_mfid: Canonical instrument MFID assigned to every result
            project_id: Project slug used to scope results by project relationship
            project_mfid: Canonical project MFID used to scope results by project relationship
            project_scope: Project relationship to include: assigned, shared, or all.
                           Requires project_id or project_mfid and defaults to assigned.
            **kwargs (Any): Query parameters for filtering. Supported fields include:
                keyword, unique_id, public, dataset_name, owner_orcid, project_id,
                instrument_name, timestamp, size, data_format, data_type, measurement,
                session_name. Filters expect exact matches (case sensitive) except for
                keywords, which are case insensitive and match substrings.

        Returns:
            List[Dict]: Dataset objects matching filter criteria
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        selectors = self._access_selector_params(
            accessible_to_user, accessible_to_project)
        params.update(selectors)
        params.update(self._project_scope_params(
            project_id, project_mfid, project_scope))
        if sample_mfid is not None:
            params['sample_mfid'] = sample_mfid
        if instrument_mfid is not None:
            params['instrument_mfid'] = instrument_mfid
        if include_metadata:
            params['include_metadata'] = True
        if include_links:
            params['include_links'] = True
        if include_owner:
            params['include_owner'] = True
        if offset:
            import warnings
            warnings.warn(
                "'offset' is ignored by /datasets, which uses keyset "
                "pagination; results start from the newest dataset.",
                DeprecationWarning, stacklevel=2,
            )
        raw = self._paginate('/datasets', params, limit, offset)
        return [self._parse(d) for d in raw]

    def count(self, project_id: Optional[str] = None,
              project_mfid: Optional[str] = None,
              project_scope: Optional[str] = None, **kwargs) -> int:
        """Return the total number of datasets matching the given filters without fetching items."""
        params = {k: v for k, v in kwargs.items() if v is not None}
        params.update(self._project_scope_params(
            project_id, project_mfid, project_scope))
        result = self._request('get', '/datasets', params={**params, 'limit': 1})
        return result['total']


    def create(self, dataset, scientific_metadata: Optional[Dict] = None,
               keywords: Optional[List[str]] = None,
               files: Optional[List[Union[str, AssociatedFile]]] = None,
               upload_files: bool = True,
               files_to_upload: Optional[List[str]] = None,
               ingestor: Optional[str] = None,
               verbose: bool = False,
               wait_for_ingestion_response: bool = False,
               skip_ingestion: bool = False) -> Dict:
        """Create a new dataset record with scientific metadata and keywords.

        Args:
            dataset (Dataset): Dataset object with dataset details. Use `owner` with
                an ORCID, MFID, username, or email to create for a
                specific owner. `owner_orcid` is deprecated for creation. Providing
                both owner fields is invalid. `project_id` and `instrument_id` accept
                human-readable IDs; `project_mfid` and `instrument_mfid` accept
                canonical MFIDs. Matching ID and MFID selectors may be supplied together.
            scientific_metadata (dict, optional): Scientific metadata
            keywords (list, optional): Keywords to associate with dataset
            files (list, optional): Files to attach. Each item is either a local
                path (str) or an AssociatedFile describing a file that lives
                elsewhere (Globus, NERSC, a shared filesystem, etc.).
                - A str path is uploaded to GCS when upload_files=True (default),
                  or cataloged by its resolved absolute path (storage_backend='local',
                  no upload) when upload_files=False.
                - An AssociatedFile is always cataloged via add_remote_file() -
                  it must set storage_backend to something other than 'gcs',
                  since there's no local file to upload from a model description.
            upload_files (bool): Whether str paths in `files` are uploaded to GCS
                (default: True) or just cataloged by their local path (False).
                Only affects str items - AssociatedFile items are routed by
                their own storage_backend regardless of this flag.
            files_to_upload (list, optional): Deprecated alias for `files`
                (str paths only, always uploaded). Use `files` instead.
        Returns:
            Dict: created_record, scientific_metadata_record, dataset_mfid, dsid, files
                (files is the per-item result of adding each entry in `files`,
                in the same order). ``dsid`` is retained for compatibility.
        """
        if scientific_metadata is None:
            scientific_metadata = {}

        if keywords is None:
            keywords = []

        if files_to_upload is not None:
            if files is not None:
                raise ValueError("Pass either 'files' or the deprecated 'files_to_upload', not both.")
            warnings.warn(
                "'files_to_upload' is deprecated, use 'files' instead.",
                DeprecationWarning, stacklevel=2,
            )
            files = files_to_upload
        if files is None:
            files = []

        dataset_details = dataset.model_dump(
            exclude={'capabilities', 'instrument', 'project'})

        if dataset_details.get('owner') is not None and dataset_details.get('owner_orcid') is not None:
            raise ValueError("Pass either 'owner' or 'owner_orcid', not both.")
        if dataset_details.get('owner_orcid') is not None:
            warnings.warn(
                "Dataset.owner_orcid is deprecated for creation; use Dataset.owner "
                "with an ORCID, MFID, username, or email instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if dataset_details.get('owner') is not None and not isinstance(dataset_details['owner'], str):
            raise ValueError("Dataset.owner must be a string identifier when creating a dataset.")

        if not dataset_details.get('unique_id'):
            dataset_details['unique_id'] = mfid.mfid()[0]

        logger.debug('Creating new dataset record...')

        clean_dataset = {k: v for k, v in dataset_details.items() if v is not None}
        new_ds_record = self._parse(self._request('post', '/datasets', json=clean_dataset))
        dataset_mfid = new_ds_record['unique_id']

        # add scientific metadata
        scimd = None
        if scientific_metadata:
            logger.debug(f'Adding scientific metadata record for {dataset_mfid}')
            scimd = self.update_scientific_metadata(dataset_mfid, scientific_metadata)


        # add keywords
        if keywords:
            logger.debug(f'Adding keywords to dataset {dataset_mfid}: {keywords}')
            for kw in keywords:
                self.add_keyword(dataset_mfid, kw)

        file_results = []
        for file in files:
            logger.debug(f'Adding {file} to dataset {dataset_mfid}')
            if isinstance(file, AssociatedFile):
                file_results.append(self.add_remote_file(dataset_mfid, file))
            elif upload_files:
                file_results.append(self.add_file(dataset_mfid,
                                                  file,
                                                  ingestion_class=ingestor,
                                                  wait_for_ingestion_response=False,
                                                  skip_ingestion = skip_ingestion))

            else:
                resolved = Path(file).resolve()
                remote = AssociatedFile(
                    filename=os.path.basename(file),
                    storage_path=str(resolved),
                    storage_backend='local',
                    size=resolved.stat().st_size if resolved.exists() else None,
                )
                file_results.append(self.add_remote_file(dataset_mfid, remote))

        if wait_for_ingestion_response and not skip_ingestion:
            pending = [r['ingestion_request']['id'] for r in file_results
                       if isinstance(r, dict) and (r.get('ingestion_request') or {}).get('id')]
            if pending:
                logger.debug(f'Waiting on {len(pending)} ingestion request(s) for {dataset_mfid}')
            for request_id in pending:
                self._client.ingestions.wait(request_id)

        result = {"created_record": new_ds_record,
                  "scientific_metadata_record": scimd,
                  "dataset_mfid": dataset_mfid, "dsid": dataset_mfid,
                  "files": file_results}
        return result

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def update(self, dataset_mfid: str, **updates) -> Dict:
        """Update an existing dataset with new field values.

        'owner_orcid' and 'project_id' are no longer accepted here (422) -
        use transfer_ownership() / reassign_project() instead.
        The deprecated 'public' field delegates to set_public() or set_private().
        Instrument reassignment is not available through generic PATCH. Omit
        'instrument_id' and 'instrument_name' unless resubmitting their current
        values for compatibility.

        Args:
            dataset_mfid (str): Dataset MFID
            **updates (Any): Fields to update (e.g., dataset_name="New Name")

        Returns:
            Dict: Updated dataset object

        Example:
            >>> client.datasets.update("my-dataset-id", dataset_name="Updated Name")
        """
        public_provided = 'public' in updates
        public = updates.pop('public', None)
        if public_provided:
            warnings.warn(
                "The 'public' update field is deprecated; use set_public() or "
                "set_private() instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if public is not None and not isinstance(public, bool):
                raise ValueError("public must be true, false, or None.")
        response_only = {'capabilities', 'instrument', 'project'} & updates.keys()
        if response_only:
            fields = ', '.join(sorted(response_only))
            raise ValueError(f"Dataset fields are response-only: {fields}.")
        updated = None
        if updates:
            updated = self._parse(
                self._request('patch', f'/datasets/{dataset_mfid}', json=updates))
        if public is not None:
            operation = self.set_public if public else self.set_private
            operation(dataset_mfid)
        if updated is None:
            updated = self.get(dataset_mfid)
        if public is not None:
            updated['public'] = public
        return updated

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def list_files(self, dataset_mfid: str) -> List[Dict]:
        """List files attached to a dataset.

        Args:
            dataset_mfid: Dataset MFID

        Returns:
            List[Dict]: File records (mfid, filename, storage_path, storage_backend,
                access_note, size, sha256_hash, dataset_mfid). For a 'gcs' file,
                storage_path is null until it has been ingested.
        """
        raw = self._request('get', f'/datasets/{dataset_mfid}/files')
        return [self._client.files._parse(f) for f in raw]

    def search(self, q: str, project_id: Optional[str] = None,
               limit: int = 20) -> List[Dict]:
        """Fuzzy name search across datasets. Available to all authenticated users.

        Matches against dataset_name. Returns datasets the caller can read.
        For scientific metadata search use search_metadata().

        Args:
            q: Search term (min 3 chars). Typo-tolerant — "pero" finds "perovskite".
            project_id: Optional project to scope results to.
            limit: Max results (default 20, max 50).

        Returns:
            List[Dict]: Matching DatasetResponse records, ranked by relevance.
        """
        params = {'q': q, 'limit': limit}
        if project_id:
            params['project_id'] = project_id
        result = self._request('get', '/datasets/search', params=params)
        raw = result.get('items', result) if isinstance(result, dict) else result
        return [self._parse(dataset) for dataset in raw]

    # Keyword Methods
    @_deprecated_parameter('dsid', 'dataset_mfid')
    def get_keywords(self, dataset_mfid: str,
                     limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """List keywords, optionally filtered by dataset.

        Args:
            dataset_mfid (str): Dataset MFID
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: Keyword objects with keyword text and num_datasets counts
        """
        return self._request('get', f'/datasets/{dataset_mfid}/keywords')

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def add_keyword(self, dataset_mfid: str, keyword: str) -> Dict:
        """Add a keyword to a dataset.

        Args:
            dataset_mfid (str): Dataset MFID
            keyword (str): Keyword/tag to associate with dataset

        Returns:
            Dict: Keyword object with updated usage count
        """
        return self._request(
            'post', f'/datasets/{dataset_mfid}/keywords', params={'keyword': keyword})

    # Dataset Linking Methods
    def link_sample(self, dataset_mfid: str, sample_mfid: str) -> Dict:
        """Link a sample to a dataset.

        Args:
            dataset_mfid (str): Dataset MFID
            sample_mfid (str): Sample MFID

        Returns:
            Dict: Information about the created link
        """
        return self._request('post', f"/datasets/{dataset_mfid}/samples/{sample_mfid}")

    def unlink_sample(self, dataset_mfid: str, sample_mfid: str) -> Dict:
        """Remove the link between a dataset and a sample.

        **Requires admin permissions.**

        Args:
            dataset_mfid (str): Dataset MFID
            sample_mfid (str): Sample MFID

        Returns:
            Dict: Deletion confirmation
        """
        return self._request('delete', f"/datasets/{dataset_mfid}/samples/{sample_mfid}")

    def link(self, parent_mfid: str, child_mfid: str,
             relationship_type: Optional[str] = None) -> Dict:
        """Link two datasets with a parent-child relationship.

        Args:
            parent_mfid (str): Parent dataset MFID
            child_mfid (str): Child dataset MFID
            relationship_type (str, optional): Kind of link, one of
                crucible.constants.RELATIONSHIP_TYPES. Describes the child
                relative to the parent.

        Returns:
            Dict: Information about the created link
        """
        options = ({'params': {'relationship_type': relationship_type}}
                   if relationship_type is not None else {})
        return self._request(
            'post', f"/datasets/{parent_mfid}/children/{child_mfid}", **options)

    def unlink(self, parent_mfid: str, child_mfid: str) -> Dict:
        """Remove the parent-child link between two datasets.

        Args:
            parent_mfid (str): Parent dataset MFID
            child_mfid (str): Child dataset MFID

        Returns:
            Dict: Deletion confirmation
        """
        return self._request(
            'delete', f"/datasets/{parent_mfid}/children/{child_mfid}")

    @_deprecated("client.datasets.link_sample()")
    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    @_deprecated_parameter('sample_id', 'sample_mfid')
    def add_sample(self, dataset_mfid: str, sample_mfid: str) -> Dict:
        """Deprecated: use link_sample(dataset_mfid, sample_mfid) instead."""
        return self.link_sample(dataset_mfid, sample_mfid)

    @_deprecated("client.datasets.unlink_sample()")
    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    @_deprecated_parameter('sample_id', 'sample_mfid')
    def remove_sample(self, dataset_mfid: str, sample_mfid: str) -> Dict:
        """Deprecated: use unlink_sample(dataset_mfid, sample_mfid) instead."""
        return self.unlink_sample(dataset_mfid, sample_mfid)

    @_deprecated("client.datasets.unlink()")
    @_deprecated_parameter('parent_dataset_id', 'parent_mfid')
    @_deprecated_parameter('parent_dataset_mfid', 'parent_mfid')
    @_deprecated_parameter('child_dataset_id', 'child_mfid')
    @_deprecated_parameter('child_dataset_mfid', 'child_mfid')
    def remove_child(self, parent_mfid: str, child_mfid: str) -> Dict:
        """Deprecated: use unlink(parent_mfid, child_mfid) instead."""
        return self.unlink(parent_mfid, child_mfid)

    @_deprecated("client.datasets.link()")
    @_deprecated_parameter('parent_dataset_id', 'parent_mfid')
    @_deprecated_parameter('parent_dataset_mfid', 'parent_mfid')
    @_deprecated_parameter('child_dataset_id', 'child_mfid')
    @_deprecated_parameter('child_dataset_mfid', 'child_mfid')
    def link_parent_child(self, parent_mfid: str, child_mfid: str,
                          relationship_type: Optional[str] = None) -> Dict:
        """Deprecated: use link(parent_mfid, child_mfid) instead."""
        if relationship_type is None:
            return self.link(parent_mfid, child_mfid)
        return self.link(parent_mfid, child_mfid, relationship_type)


    @_deprecated_parameter('parent_dataset_id', 'parent_mfid')
    @_deprecated_parameter('parent_dataset_mfid', 'parent_mfid')
    def list_children(self, parent_mfid: str, limit: int = DEFAULT_LIMIT,
                      offset: int = 0, relationship_type: Optional[str] = None,
                      **kwargs) -> List[Dict]:
        """List the children of a given dataset with optional filtering.

        Args:
            parent_mfid (str): Parent dataset MFID
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)
            relationship_type (str, optional): Only return children linked with
                this kind of link, one of crucible.constants.RELATIONSHIP_TYPES.
            **kwargs (Any): Query parameters for filtering datasets

        Returns:
            List[Dict]: Children datasets
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if relationship_type is not None:
            params['relationship_type'] = relationship_type
        raw = self._paginate(
            f"/datasets/{parent_mfid}/children", params, limit, offset)
        return [self._parse(dataset) for dataset in raw]

    @_deprecated_parameter('child_dataset_id', 'child_mfid')
    @_deprecated_parameter('child_dataset_mfid', 'child_mfid')
    def list_parents(self, child_mfid: str, limit: int = DEFAULT_LIMIT,
                     offset: int = 0, relationship_type: Optional[str] = None,
                     **kwargs) -> List[Dict]:
        """List the parents of a given dataset with optional filtering.

        Args:
            child_mfid (str): Child dataset MFID
            limit (int): Maximum number of results to return
            offset (int): Starting position in the full result set (default: 0)
            relationship_type (str, optional): Only return parents linked with
                this kind of link, one of crucible.constants.RELATIONSHIP_TYPES.
            **kwargs (Any): Query parameters for filtering datasets

        Returns:
            List[Dict]: Parent datasets
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        if relationship_type is not None:
            params['relationship_type'] = relationship_type
        raw = self._paginate(
            f"/datasets/{child_mfid}/parents", params, limit, offset)
        return [self._parse(dataset) for dataset in raw]

    # Special Processing Methods
    @_deprecated_parameter('dsid', 'dataset_mfid')
    def request_carrier_segmentation(self, dataset_mfid: str) -> Dict:
        """Request carrier segmentation for a dataset.

        Args:
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: Carrier segmentation request information
        """
        result = self._request(
            'post', f"/datasets/{dataset_mfid}/carrier_segmentation")
        return result

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def request_insitu_aggregation(self, dataset_mfid: str) -> Dict:
        """Request insitu spectroscopy data aggregation for a dataset.

        Args:
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: Data processing request information
        """
        result = self._request(
            'post', f"/datasets/{dataset_mfid}/insitu_spec_aggregation")
        return result

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def request_rga_analysis(self, dataset_mfid: str) -> Dict:
        """Request RGA analysis for a dataset.

        Args:
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: RGA analysis request information
        """
        result = self._request('post', f"/datasets/{dataset_mfid}/rga_analysis")
        return result

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def request_mosaic_stitch(self, dataset_mfid: str) -> Dict:
        """Request mosaic stitch processing for a dataset.

        Args:
            dataset_mfid (str): Dataset MFID

        Returns:
            Dict: Mosaic stitch request information
        """
        result = self._request('post', f"/datasets/{dataset_mfid}/mosaic_stitch")
        return result

    @_deprecated("client.graphs.get")
    @_deprecated_parameter('dataset_id', 'dataset_mfid')
    def graph(self, dataset_mfid: str, recursive: bool = False,
              as_networkx: bool = False):
        return self._client.graphs.get(
            dataset_mfid, recursive=recursive, as_networkx=as_networkx)

    #%% Upload Methods

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def add_file(self, 
                 dataset_mfid: str,
                 file_path: str,
                 ingestion_class: Optional[str] = None,
                 wait_for_ingestion_response: bool = False,
                 multipart: bool = True,
                 chunk_size_mb: Optional[int] = None,
                 max_workers: Optional[int] = None,
                 skip_ingestion: bool = False) -> Dict:

        """Upload a file to a dataset and request ingestion.

        Args:
            dataset_mfid: Dataset MFID
            file_path: Local path to the file
            ingestion_class: Ingestion class for the worker (e.g. 'lammps', 'nexus').
                Defaults to the server-side default if omitted.
            wait_for_ingestion_response: Block until ingestion completes. Ignored if
                skip_ingestion is True.
            multipart: Use parallel multipart upload (default: True). Set to False to
                use the sequential resumable upload (slower but simpler).
            chunk_size_mb: Override chunk size in MiB (uses config/default if None).
            max_workers: Override number of upload threads (uses config/default if None).
            skip_ingestion: Upload the file without requesting ingestion. Request it
                later with client.files.request_ingestion(mfid). 

        Returns:
            Dict: {'associated_file': AssociatedFileRead, 'ingestion_request': IngestionRequest}
        """
        file_size = os.path.getsize(file_path)
        filename  = os.path.basename(file_path)

        file_record, was_existing = upload_file_gcs(self._client, 
                                                    dataset_mfid, 
                                                    file_path,
                                                    multipart=multipart,
                                                    chunk_size_mb=chunk_size_mb,
                                                    max_workers=max_workers)
        file_record = self._client.files._parse(file_record)

        stored_filename = file_record.get('filename', filename)
        file_id         = file_record.get('mfid')

        if was_existing:
            logger.info(
                f"{stored_filename} already exists in dataset {dataset_mfid}, skipping ingestion")
            return {'associated_file': file_record, 'ingestion_request': None}

        if skip_ingestion:
            ingestion_request = self._client.files._skip_ingestion(file_id)
            logger.info(f"Uploaded {stored_filename} to dataset {dataset_mfid}, ingestion not requested")

        else:
            ingestion_request = self._client.files.request_ingestion(file_id, ingestion_class, wait_for_ingestion_response)

        return {'associated_file': file_record, 'ingestion_request': ingestion_request}


    @_deprecated_parameter('dsid', 'dataset_mfid')
    def add_remote_file(self, dataset_mfid: str, file: AssociatedFile) -> Dict:
        """Register a file that lives outside GCS (Globus, NERSC, a shared
        filesystem path, etc.) without uploading it.

        Crucible only catalogs the pointer here — it never verifies the file
        exists or fetches bytes on your behalf. Internally this is a two-step
        API call (create, then set storage_path) hidden behind one method.

        Args:
            dataset_mfid: Dataset MFID
            file (AssociatedFile): Must have `storage_backend` set to something
                other than 'gcs' (e.g. 'globus', 'local'). `storage_path` is
                optional — omit it to catalog the file now and set its location
                later via client.files.update(mfid, storage_path=...).

        Returns:
            Dict: The created (and, if storage_path was given, updated) file record.
        """
        if not file.storage_backend or file.storage_backend == 'gcs':
            raise ValueError(
                "add_remote_file() requires storage_backend set to something other "
                "than 'gcs' (e.g. 'globus'). Use add_file() to upload a local file to GCS."
            )

        storage_path = file.storage_path
        payload = file.model_dump(exclude={'mfid', 'dataset_mfid', 'storage_path'}, exclude_none=True)
        created = self._client.files._parse(self._request(
            'post', f'/datasets/{dataset_mfid}/files', json=payload))

        if storage_path:
            return self._client.files.update(created['mfid'], storage_path=storage_path)
        return created

    @_deprecated("client.datasets.add_file")
    @_deprecated_parameter('dsid', 'dataset_mfid')
    def add_file_to_dataset(self, dataset_mfid: str, file_path: str,
                            ingestion_class: Optional[str] = None,
                            wait_for_ingestion_response: bool = False,
                            multipart: bool = True,
                            chunk_size_mb: Optional[int] = None,
                            max_workers: Optional[int] = None) -> Dict:
        
        return self.add_file(dataset_mfid=dataset_mfid, file_path=file_path,
                             ingestion_class=ingestion_class,
                             wait_for_ingestion_response=wait_for_ingestion_response,
                             multipart=multipart,
                             chunk_size_mb=chunk_size_mb,
                             max_workers=max_workers,
                             skip_ingestion = False)


    #%% Download Methods

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def get_download_links(self, dataset_mfid: str) -> Dict:
        """Get signed download URLs for all ingested files in a dataset.

        Returns:
            Dict: Mapping of file MFID → signed URL. Empty dict if no ingested files.
        """
        try:
            return self._request('get', f"/datasets/{dataset_mfid}/download_links")
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 404:
                    logger.debug(
                        f"No ingested files in storage for dataset {dataset_mfid}")
                    return {}
                if e.response.status_code in (502, 503, 504):
                    logger.warning(f"Could not retrieve download links for {dataset_mfid}: "
                                   f"{e.response.status_code} {e.response.reason}.")
                    return {}
            raise

    def _fetch_files(self, dataset_mfid: str, output_dir: str,
                     overwrite_existing: bool = True,
                     include: Optional[List[str]] = None,
                     exclude: Optional[List[str]] = None) -> List[str]:
        """Download ingested files for a dataset. Returns list of downloaded paths."""
        from .gcs.download import download_dataset_files
        return download_dataset_files(
            self._client, dataset_mfid, output_dir,
            link_map=self.get_download_links(dataset_mfid),
            all_files=self.list_files(dataset_mfid),
            overwrite_existing=overwrite_existing,
            include=include, exclude=exclude,
        )

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def download(self, dataset_mfid: str, file_name: Optional[str] = None,
                 output_dir: str = 'crucible-downloads',
                 no_files: bool = False,
                 no_record: bool = False,
                 overwrite_existing: bool = True,
                 include: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None) -> List[str]:
        """Download a dataset's files and optionally save its record as JSON.

        Args:
            dataset_mfid: Dataset MFID
            file_name: Deprecated. Use include=['pattern'] with glob syntax.
            output_dir: Directory to save files (default: 'crucible-downloads/')
            no_files: Skip file download, save record.json only.
            no_record: Skip saving record.json, just download files.
            overwrite_existing: Overwrite existing files (default: True)
            include: Glob patterns - only download matching files
            exclude: Glob patterns - skip matching files

        Returns:
            List[str]: Paths of all downloaded items (record.json + data files)
        """
        if file_name is not None:
            import warnings
            warnings.warn(
                "The 'file_name' parameter is deprecated. Use include=['pattern'] instead.",
                DeprecationWarning, stacklevel=2,
            )
            matched = [os.path.basename(f.get('storage_path') or f.get('filename', ''))
                       for f in self.list_files(dataset_mfid)
                       if re.fullmatch(fr"({file_name})",
                                       os.path.basename(f.get('storage_path') or f.get('filename', '')))]
            include = matched

        os.makedirs(output_dir, exist_ok=True)
        downloaded = []

        if not no_record:
            record = self.get(dataset_mfid, include_metadata=True)
            record_dir = os.path.join(output_dir, dataset_mfid)
            os.makedirs(record_dir, exist_ok=True)
            json_path   = os.path.join(record_dir, 'record.json')
            with open(json_path, 'w') as fh:
                import json as _json
                _json.dump(record, fh, indent=2)
            logger.info(f"Saved record to {json_path}")
            downloaded.append(json_path)

        if not no_files:
            dest = os.path.join(output_dir, dataset_mfid)
            os.makedirs(dest, exist_ok=True)
            files = self._fetch_files(dataset_mfid, output_dir=dest,
                                      overwrite_existing=overwrite_existing,
                                      include=include, exclude=exclude)
            downloaded.extend(files)
            if files:
                logger.info(f"Downloaded {len(files)} file(s) to {dest}")

        return downloaded

    #%% Thumbnail Methods

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def get_thumbnails(self, dataset_mfid: str,
                       limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Get all thumbnails for a dataset.

        The ``limit`` parameter is retained for compatibility. The API route
        is not paginated and returns every thumbnail.
        """
        return self._request('get', f'/datasets/{dataset_mfid}/thumbnails')

    @staticmethod
    def _encode_thumbnail(image):
        """Return raw base64 image data and an inferred local filename."""
        import base64
        from ..utils import data2thumbnail, is_base64

        if is_base64(image):
            if isinstance(image, bytes):
                image = image.decode('ascii')
            return image, None

        image_path = data2thumbnail(image)
        with open(image_path, 'rb') as f:
            thumbnail_b64str = base64.b64encode(f.read()).decode('utf-8')
        return thumbnail_b64str, os.path.basename(image_path)

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def add_thumbnail(self, dataset_mfid: str, image,
                      thumbnail_name: Optional[str] = None) -> Dict:
        """Encode and add a thumbnail, returning the API thumbnail record."""
        thumbnail_b64str, inferred_name = self._encode_thumbnail(image)
        thumbnail_data = {
            'thumbnail_name': thumbnail_name or inferred_name or f"{dataset_mfid}_thumbnail",
            'thumbnail_b64str': thumbnail_b64str,
        }
        return self._request(
            'post', f'/datasets/{dataset_mfid}/thumbnails', json=thumbnail_data)

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def update_thumbnail(self, dataset_mfid: str, thumbnail_id: int,
                         image=None, thumbnail_name: Optional[str] = None) -> Dict:
        """Rename or replace a thumbnail and return the updated API record."""
        if image is None and thumbnail_name is None:
            raise ValueError("Provide image, thumbnail_name, or both.")
        if thumbnail_name is not None and (
                not isinstance(thumbnail_name, str) or not thumbnail_name.strip()):
            raise ValueError("thumbnail_name must be a nonblank string.")

        thumbnail_data = {}
        if thumbnail_name is not None:
            thumbnail_data['thumbnail_name'] = thumbnail_name
        if image is not None:
            thumbnail_b64str, _ = self._encode_thumbnail(image)
            thumbnail_data['thumbnail_b64str'] = thumbnail_b64str

        return self._request(
            'patch',
            f'/datasets/{dataset_mfid}/thumbnails/{thumbnail_id}',
            json=thumbnail_data,
        )

    @_deprecated_parameter('dsid', 'dataset_mfid')
    def delete_thumbnail(self, dataset_mfid: str, thumbnail_id: int) -> Dict:
        """Delete a thumbnail from a dataset."""
        return self._request(
            'delete', f'/datasets/{dataset_mfid}/thumbnails/{thumbnail_id}')

    #%% Ingestion Methods — deprecated, use client.ingestions.*

    @_deprecated("client.ingestions.list(dsid=dsid, file_id=file_id)")
    def get_ingestion_requests(self, dsid: Optional[str] = None,
                               file_id: Optional[str] = None,
                               limit: int = DEFAULT_LIMIT) -> List[Dict]:
        """Deprecated: use client.ingestions.list() instead."""
        return self._client.ingestions.list(dsid=dsid, file_id=file_id, limit=limit)

    @_deprecated("client.ingestions.get(reqid)")
    def get_request_status(self, reqid: str) -> Dict:
        """Deprecated: use client.ingestions.get() instead."""
        return self._client.ingestions.get(reqid)

    @_deprecated("client.ingestions.update(reqid, status)")
    def update_ingestion_status(self, reqid: str, status: str,
                                ingestion_githash: str = None,
                                ingestion_class: str = None,
                                timezone: str = "America/Los_Angeles") -> Dict:
        """Deprecated: use client.ingestions.update() instead."""
        return self._client.ingestions.update(reqid, status,
                                             ingestion_githash=ingestion_githash,
                                             ingestion_class=ingestion_class,
                                             timezone=timezone)
