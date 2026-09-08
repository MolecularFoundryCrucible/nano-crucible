#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main client for Crucible API.

Provides organized access to API endpoints.
"""

import time
import requests
import json
import logging
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.util.retry import Retry
from typing import Optional, List, Dict, Any, Union
from .models import Dataset, Project
from .constants import DEFAULT_LIMIT
from .utils.deprecation import _deprecated, _deprecated_parameter, _removed
from .utils.identifiers import is_mfid, require_canonical_identifier

logger = logging.getLogger(__name__)

#%%

class CrucibleClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Crucible API client.

        Args:
            api_url: Base URL for the Crucible API (loads from config or the package default if not provided)
            api_key: API key for authentication (loads from config if not provided)

        Raises:
            ValueError: If api_key is not provided and not found in config
        """
        # Load from config if not provided
        from .config import config as _config
        self._config = _config
        if api_url is None:
            api_url = _config.api_url
        if api_key is None:
            api_key = _config.api_key

        if not api_url:
            raise ValueError("api_url is required. Provide it directly or run 'crucible config init'")
        if not api_key:
            raise ValueError("api_key is required. Provide it directly or run 'crucible config init'")

        self.api_url = api_url.rstrip('/')
        self.api_key = api_key

        api_path = urlparse(self.api_url).path.rstrip('/')
        legacy_version = next(
            (version for version in ('v1', 'v2') if api_path.endswith(f'/api/{version}')),
            None,
        )
        if legacy_version:
            import warnings
            from .config.config import Config as _Cfg
            warnings.warn(
                f"You are connected to Crucible API {legacy_version} which is deprecated. "
                f"Use {_Cfg.DEFAULT_API_URL} or remove the configured override with: "
                f"crucible config unset api_url",
                FutureWarning,
                stacklevel=2,
            )

        # Session with automatic retry on transient server/network errors
        retry = Retry(
            total            = 3,
            backoff_factor   = 1,            # waits 1s, 2s, 4s between retries
            status_forcelist = {429, 502, 503, 504},
            allowed_methods  = False,        # retry all HTTP methods, including POST
            raise_on_status  = False,        # let raise_for_status() handle final failure
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Initialize resource operations
        from .resources import FileOperations, DatasetOperations, SampleOperations, \
        ProjectOperations, UserOperations, InstrumentOperations, DeletionOperations, \
        GraphOperations, AccountOperations, IngestionOperations, ServiceAccountOperations, \
        AccessGroupOperations

        self.files = FileOperations(self)
        self.datasets = DatasetOperations(self)
        self.samples = SampleOperations(self)
        self.projects = ProjectOperations(self)
        self.users = UserOperations(self)
        self.instruments = InstrumentOperations(self)
        self.deletions = DeletionOperations(self)
        self.graphs = GraphOperations(self)
        self.account = AccountOperations(self)
        self.ingestions = IngestionOperations(self)
        self.service_accounts = ServiceAccountOperations(self)
        self.access_groups = AccessGroupOperations(self)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            Parsed JSON response

        Raises:
            requests.exceptions.HTTPError: For HTTP errors (4xx, 5xx)
            requests.exceptions.ConnectionError: For connection failures
            requests.exceptions.Timeout: For timeout errors
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        logger.debug(f"{method.upper()} {url}")
        timeout = (self._config.connect_timeout, self._config.read_timeout)
        response = self._session.request(method, url, timeout=timeout, **kwargs)
        logger.debug(f"Status: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        if not response.ok:
            # Try to surface the server's error detail from the response body
            detail = None
            try:
                body = response.json()
                detail = body.get("detail") or body.get("message") or body.get("error")
            except (json.JSONDecodeError, ValueError, AttributeError):
                pass
            if detail:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} {response.reason}: {detail}",
                    response=response,
                )
            response.raise_for_status()
        try:
            if response.content:
                return response.json()
            else:
                return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response from {url}: {e}")
            return response
    
    def _wait_for_request_completion(self, reqid: str, sleep_interval: int = 1) -> Dict:
        """Internal: delegate to client.ingestions.wait()."""
        return self.ingestions.wait(reqid, sleep_interval=sleep_interval)

    
    #%% GENERIC METHODS

    def live(self) -> Dict:
        """Check whether the API process is running (no DB check, no auth).

        Returns:
            Dict: {"status": "ok"}
        """
        import requests as _requests
        url = f"{self.api_url}/health/live"
        timeout = (self._config.connect_timeout, self._config.read_timeout)
        resp = _requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> Dict:
        """Check API and database health without requiring authentication.

        Returns:
            Dict: Readiness status with nested ``build`` and ``database``
                provenance. During API rollout, older servers may return the
                legacy flat ``db``, ``db_ms``, and ``version`` fields.

        Raises:
            requests.exceptions.ConnectionError: If the host is unreachable.
        """
        import requests as _requests
        url = f"{self.api_url}/health/ready"
        timeout = (self._config.connect_timeout, self._config.read_timeout)
        resp = _requests.get(url, timeout=timeout)
        return resp.json()

    def whoami(self) -> Dict:
        """Return full auth context for the current API key.

        Delegates to client.account.whoami(). Kept here for backward compatibility
        and because it spans the account context rather than a specific resource.
        """
        return self.account.whoami()

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def get_resource_type(self, resource_mfid: str) -> str:
        """
        Determine the type of a resource.

        Args:
            resource_mfid (str): Resource MFID

        Returns:
            str: resource_type
        """
        if not is_mfid(resource_mfid):
            raise ValueError("resource_mfid must be an exact 26-character MFID.")
        response = self._request('get', f"/resources/{resource_mfid}")
        return response['resource_type']

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def get(self, resource_mfid: str, resource_type: str = None,
            include_metadata: bool = False, include_links: bool = False,
            include_owner: bool = True, include_datasets: bool = True) -> Dict:
        """
        Get a resource by ID with automatic type detection.

        Args:
            resource_mfid (str): Resource MFID
            resource_type (str, optional): Resource type ('sample', 'dataset',
                                          'project', or 'instrument').
                                          If not provided, will be auto-detected.
            include_metadata (bool): Include scientific metadata
            include_links (bool): Include immediate parent/child/associated links
            include_owner (bool): Resolve owner_orcid into a public-safe user object (default: True)
            include_datasets (bool): For samples, include deprecated embedded dataset records (default: True)

        Returns:
            Dict: Resource data

        Raises:
            ValueError: If resource type is unknown or not supported
        """
        if not is_mfid(resource_mfid):
            raise ValueError("resource_mfid must be an exact 26-character MFID.")
        if resource_type is None:
            params = {}
            if include_links:
                params['include_links'] = True
            if include_metadata:
                params['include_metadata'] = True
            if include_owner:
                params['include_owner'] = True
            if not include_datasets:
                params['include_datasets'] = False
            raw = self._request(
                'get', f"/resources/{resource_mfid}", params=params or None)
            return require_canonical_identifier(raw, 'resource')

        if resource_type == "sample":
            sample_options = {
                'include_links': include_links,
                'include_metadata': include_metadata,
                'include_owner': include_owner,
            }
            if not include_datasets:
                sample_options['include_datasets'] = False
            return self.samples.get(resource_mfid, **sample_options)
        elif resource_type == "dataset":
            return self.datasets.get(resource_mfid, include_metadata=include_metadata,
                                     include_links=include_links,
                                     include_owner=include_owner)
        elif resource_type == "instrument":
            return self.instruments.get(
                instrument_mfid=resource_mfid,
                include_metadata=include_metadata,
                include_owner=include_owner,
            )
        elif resource_type == "project":
            return self.projects.get(
                project_mfid=resource_mfid,
                include_metadata=include_metadata,
            )
        else:
            raise ValueError(f"Unknown or unsupported resource type: {resource_type}")

    @_deprecated_parameter('resource_id', 'resource_mfid')
    def get_links(self, resource_mfid: str) -> list:
        """Return immediate links for any resource (dataset or sample).

        Hits GET /resources/{id}/links and returns a flat list of link dicts:
            [{"unique_id": "...", "resource_type": "dataset|sample",
              "name": "...", "direction": "source|target|undirected",
              "relationship_type": "is_derived_from|is_part_of|null"}, ...]

        `direction` says which end of the stored parent -> child edge this
        resource is, relative to the one you asked about: "source" means it is
        the parent, "target" the child. Dataset/sample associations have no
        hierarchy and are always "undirected". `relationship_type` is the kind
        of link, stored on the link row and oriented child-relative-to-parent;
        it is null on associations and on links created before typing existed.

        Args:
            resource_mfid (str): Dataset or sample MFID

        Returns:
            list: Link objects, or empty list if none
        """
        result = self._request('get', f"/resources/{resource_mfid}/links")
        return result or []

    @_deprecated_parameter('parent_id', 'parent_mfid')
    @_deprecated_parameter('child_id', 'child_mfid')
    def link(self, parent_mfid: str, child_mfid: str,
             relationship_type: Optional[str] = None) -> Dict:
        """
        Link two resources with automatic type detection.

        Automatically determines resource types and creates appropriate link:
        - Both datasets: Creates parent-child dataset relationship
        - Both samples: Creates parent-child sample relationship
        - Dataset + sample: Links sample to dataset

        Args:
            parent_mfid (str): Parent resource MFID
            child_mfid (str): Child resource MFID
            relationship_type (str, optional): Kind of link, one of
                crucible.constants.RELATIONSHIP_TYPES. Only meaningful for
                dataset-to-dataset and sample-to-sample links; a dataset/sample
                association has no hierarchy to describe.

        Returns:
            Dict: Information about the created link

        Raises:
            ValueError: If resource types cannot be determined, the combination
                is invalid, or relationship_type is given for a dataset/sample
                association

        Example:
            >>> # Link two datasets
            >>> client.link(parent_mfid, child_mfid)

            >>> # Link two samples, recording what kind of link it is
            >>> client.link(parent_mfid, child_mfid, relationship_type='is_part_of')

            >>> # Link sample to dataset
            >>> client.link(dataset_mfid, sample_mfid)
        """
        parent_type = self.get_resource_type(parent_mfid)
        child_type = self.get_resource_type(child_mfid)

        # Both are datasets
        if parent_type == "dataset" and child_type == "dataset":
            logger.info(f"Linking datasets: {parent_mfid} (parent) -> {child_mfid} (child)")
            return self.datasets.link(parent_mfid, child_mfid)

        # Both are samples
        elif parent_type == "sample" and child_type == "sample":
            logger.info(f"Linking samples: {parent_mfid} (parent) -> {child_mfid} (child)")
            return self.samples.link(parent_mfid, child_mfid, relationship_type)

        # Mixed: dataset and sample. These associations are undirected, so
        # there is no parent/child relationship for a type to describe.
        elif relationship_type is not None:
            raise ValueError(
                "relationship_type does not apply to a dataset/sample association; "
                "it is only meaningful for dataset-to-dataset or sample-to-sample links."
            )

        elif parent_type == "dataset" and child_type == "sample":
            logger.info(f"Linking sample {child_mfid} to dataset {parent_mfid}")
            return self.datasets.link_sample(parent_mfid, child_mfid)

        elif parent_type == "sample" and child_type == "dataset":
            logger.info(f"Linking sample {parent_mfid} to dataset {child_mfid}")
            return self.datasets.link_sample(child_mfid, parent_mfid)

        else:
            raise ValueError(
                f"Cannot link resources: parent is {parent_type}, child is {child_type}. "
                f"Valid combinations: dataset-dataset, sample-sample, or dataset-sample."
            )

    @_deprecated_parameter('id_a', 'resource_mfid_a')
    @_deprecated_parameter('id_b', 'resource_mfid_b')
    def unlink(self, resource_mfid_a: str, resource_mfid_b: str) -> Dict:
        """Unlink two resources with automatic type detection.

        Automatically determines resource types and removes the appropriate link:
        - Both datasets: Removes parent-child dataset relationship
        - Both samples: Removes parent-child sample relationship
        - Dataset + sample: Removes dataset-sample link

        Args:
            resource_mfid_a (str): First dataset or sample MFID
            resource_mfid_b (str): Second dataset or sample MFID

        Returns:
            Dict: Deletion confirmation

        Raises:
            ValueError: If resource types cannot be determined or combination is invalid.
        """
        type_a = self.get_resource_type(resource_mfid_a)
        type_b = self.get_resource_type(resource_mfid_b)

        if type_a == "dataset" and type_b == "sample":
            logger.info(f"Unlinking sample {resource_mfid_b} from dataset {resource_mfid_a}")
            return self.datasets.unlink_sample(resource_mfid_a, resource_mfid_b)

        elif type_a == "sample" and type_b == "dataset":
            logger.info(f"Unlinking sample {resource_mfid_a} from dataset {resource_mfid_b}")
            return self.datasets.unlink_sample(resource_mfid_b, resource_mfid_a)

        elif type_a == "dataset" and type_b == "dataset":
            logger.info(
                f"Unlinking child dataset {resource_mfid_b} from parent dataset {resource_mfid_a}")
            return self.datasets.unlink(resource_mfid_a, resource_mfid_b)

        elif type_a == "sample" and type_b == "sample":
            logger.info(
                f"Unlinking child sample {resource_mfid_b} from parent sample {resource_mfid_a}")
            return self.samples.unlink(resource_mfid_a, resource_mfid_b)

        else:
            raise ValueError(
                f"Cannot unlink resources: {resource_mfid_a} is {type_a}, "
                f"{resource_mfid_b} is {type_b}."
            )
    
    @_deprecated("client.datasets.download() or client.samples.download()")
    @_deprecated_parameter('resource_id', 'resource_mfid')
    def download(self, resource_mfid: str, output_dir: str = 'crucible-downloads',
                 no_files: bool = False, no_record: bool = False,
                 overwrite_existing: bool = True,
                 include: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None) -> List[str]:
        """Deprecated: use client.datasets.download() or client.samples.download() instead."""
        resource_type = self.get_resource_type(resource_mfid)
        if resource_type == 'dataset':
            return self.datasets.download(resource_mfid, output_dir=output_dir,
                                          no_files=no_files, no_record=no_record,
                                          overwrite_existing=overwrite_existing,
                                          include=include, exclude=exclude)
        elif resource_type == 'sample':
            return self.samples.download(resource_mfid, output_dir=output_dir)
        else:
            raise ValueError(f"Cannot download resource of type: {resource_type}")
