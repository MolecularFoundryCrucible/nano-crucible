#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main client for Crucible API.

Provides organized access to API endpoints.
"""

import requests
import json
import logging
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.util.retry import Retry
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from .constants import DEFAULT_PRIVILEGE_MODE, PRIVILEGE_MODES
from .utils.deprecation import _deprecated, _deprecated_parameter
from .utils.identifiers import is_mfid, require_canonical_identifier

if TYPE_CHECKING:
    from .models import AccountAuthorization, AccountCapabilities

logger = logging.getLogger(__name__)

class CrucibleClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None,
                 privilege_mode: Optional[str] = None):
        """
        Initialize the Crucible API client.

        Args:
            api_url: Base URL for the Crucible API (loads from config or the package default if not provided)
            api_key: API key for authentication (loads from config if not provided)
            privilege_mode: "normal" or "elevated". Sent as the
                Crucible-Privilege-Mode header on every request. Elevated mode
                is what lets a platform administrator see beyond their own
                ACL-derived access. Loads from config if not provided. When
                unset, no header is sent and the server applies its legacy
                behavior: elevated for a platform administrator, normal for
                everyone else. Admin-only operations request elevation per
                call regardless of this setting.

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
        if privilege_mode is None:
            privilege_mode = _config.privilege_mode or DEFAULT_PRIVILEGE_MODE
        elif privilege_mode not in PRIVILEGE_MODES:
            raise ValueError(
                f"privilege_mode must be one of: {', '.join(PRIVILEGE_MODES)}.")
        self.privilege_mode = privilege_mode

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

        # Session for calls that must not be retried on 429/502/503/504.
        # The default HTTPAdapter retries nothing, which is correct here:
        # a response lost or delayed after a non-idempotent server-side
        # effect already happened (e.g. a physical print job published to
        # MQTT) must not be retried, since that would repeat the effect.
        #
        # Connection: close disables keep-alive so no connection from this
        # session is ever reused across calls. Without it, an infrequently
        # used pooled connection can go idle long enough for the server (or
        # an intermediary) to close it; the next call then reuses the dead
        # connection and fails with a connection-reset error on send, before
        # any request bytes reached the server. That failure is safe to
        # retry (nothing was sent), but urllib3 cannot distinguish it from a
        # connection that died mid-request after the server received and
        # possibly acted on it -- both surface the same way. Rather than
        # retry either case, avoid connection reuse here so the safe case
        # cannot occur in the first place.
        self._no_retry_session = requests.Session()
        self._no_retry_session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Connection": "close",
        })

        # Initialize resource operations
        from .resources import FileOperations, DatasetOperations, SampleOperations, \
        ProjectOperations, UserOperations, InstrumentOperations, DeletionOperations, \
        GraphOperations, AccountOperations, IngestionOperations, ServiceAccountOperations, \
        AccessGroupOperations, PrintOperations

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
        self.print = PrintOperations(self)
        self._authorization = None
        self._capabilities = None

    def _load_profile(self, refresh: bool = False) -> None:
        """Populate the cached authorization and capability blocks."""
        from .models import AccountAuthorization, AccountCapabilities

        if self._authorization is not None and not refresh:
            return
        try:
            profile = self.account.profile()
        except Exception:
            profile = {}
        self._authorization = AccountAuthorization.model_validate(
            profile.get('authorization') or {})
        self._capabilities = AccountCapabilities.model_validate(
            profile.get('capabilities') or {})

    def refresh_profile(self) -> None:
        """Re-read authorization and capabilities from /account/profile."""
        self._load_profile(refresh=True)

    @property
    def authorization(self) -> 'AccountAuthorization':
        """The caller's platform_role and whether they can elevate.

        Fetched once from /account/profile and cached; call refresh_profile()
        to re-read it. An unreadable profile yields empty values, so callers
        degrade to "no extra authority" rather than failing.
        """
        self._load_profile()
        return self._authorization

    @property
    def capabilities(self) -> 'AccountCapabilities':
        """The caller's account-level capability flags, cached like authorization.

        They describe the authority of the privilege mode the client was in
        when the profile was read; call refresh_profile() after changing
        privilege_mode.
        """
        self._load_profile()
        return self._capabilities

    @property
    def can_elevate(self) -> bool:
        """Whether this caller may request elevated privilege mode at all."""
        return self.authorization.can_elevate

    @property
    def is_elevated(self) -> bool:
        """Whether ordinary requests from this client run elevated."""
        if self.privilege_mode is None:
            return self.can_elevate
        return self.privilege_mode == 'elevated'

    def _admin_mode(self) -> Optional[str]:
        """Privilege mode for calls that need elevation but are not admin-only.

        The server rejects an elevation request from an ineligible caller with a
        hard 403, so an ordinary user keeps their normal-mode access instead.
        """
        return 'elevated' if self.can_elevate else None

    def _request(self, method: str, endpoint: str,
                 privilege_mode: Optional[str] = None,
                 retry: bool = True, **kwargs) -> Any:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            privilege_mode: Per-call override of the client's privilege mode.
            retry: Whether transient 429/502/503/504 responses may be
                retried. Set False for a non-idempotent endpoint where a
                lost response after a server-side side effect must not
                trigger a second attempt.
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
        mode = privilege_mode if privilege_mode is not None else self.privilege_mode
        if mode is not None:
            if mode not in PRIVILEGE_MODES:
                raise ValueError(
                    f"privilege_mode must be one of: {', '.join(PRIVILEGE_MODES)}.")
            headers = dict(kwargs.pop('headers', None) or {})
            headers.setdefault('Crucible-Privilege-Mode', mode)
            kwargs['headers'] = headers
        session = self._session if retry else self._no_retry_session
        response = session.request(method, url, timeout=timeout, **kwargs)
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
              "relationship": "parent|child|associated",
              "relationship_type": "is_derived_from|is_part_of|null"}, ...]

        `direction` says which end of the stored parent -> child edge this
        resource is, relative to the one you asked about: "source" means it is
        the parent, "target" the child. Dataset/sample associations have no
        hierarchy and are always "undirected". `relationship_type` is the kind
        of link, stored on the link row and oriented child-relative-to-parent;
        it is null on associations and on links created before typing existed.
        `relationship` remains as a compatibility alias for `direction`.

        Args:
            resource_mfid (str): Dataset or sample MFID

        Returns:
            list: Link objects, or empty list if none
        """
        result = self._request('get', f"/resources/{resource_mfid}/links") or []
        direction_to_relationship = {
            'source': 'parent',
            'target': 'child',
            'undirected': 'associated',
        }
        relationship_to_direction = {
            value: key for key, value in direction_to_relationship.items()
        }
        links = []
        for raw_link in result:
            link = dict(raw_link)
            if link.get('direction') in direction_to_relationship:
                link.setdefault(
                    'relationship',
                    direction_to_relationship[link['direction']],
                )
            elif link.get('relationship') in relationship_to_direction:
                link['direction'] = relationship_to_direction[link['relationship']]
            links.append(link)
        return links

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
            return self.datasets.link(parent_mfid, child_mfid, relationship_type)

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
