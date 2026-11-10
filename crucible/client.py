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
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from .constants import DEFAULT_PRIVILEGE_MODE, PRIVILEGE_MODES
from .utils.deprecation import _removed, _removed_parameter
from .utils.identifiers import is_mfid, require_canonical_identifier

if TYPE_CHECKING:
    from .models import AccountAuthorization, AccountCapabilities

logger = logging.getLogger(__name__)


def _user_agent() -> str:
    import platform
    from . import __version__
    return (f"nano-crucible/{__version__} (Python {platform.python_version()}; "
            f"{platform.system() or 'unknown'})")


USER_AGENT = _user_agent()
_REPEATABLE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'})
_deprecations_seen: set = set()


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

        Without api_key, the client uses CRUCIBLE_API_KEY, then the sign-in
        stored by `crucible login` for api_url, then api_key from the config
        file.

        Raises:
            ValueError: If there is no API key and no stored sign-in
        """
        # Load from config if not provided
        from .config import config as _config
        self._config = _config
        if api_url is None:
            api_url = _config.api_url
        if privilege_mode is None:
            privilege_mode = _config.privilege_mode or DEFAULT_PRIVILEGE_MODE
        elif privilege_mode not in PRIVILEGE_MODES:
            raise ValueError(
                f"privilege_mode must be one of: {', '.join(PRIVILEGE_MODES)}.")
        self.privilege_mode = privilege_mode

        if not api_url:
            raise ValueError("api_url is required. Provide it directly or run 'crucible config init'")

        self.api_url = api_url.rstrip('/')
        self._credential = _resolve_credential(_config, self.api_url, api_key)
        self.api_key = self._credential.key if self._credential.kind == 'api_key' else None
        self._step_up_credential = None

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
            allowed_methods  = False,        # only repeatable requests use this session
            raise_on_status  = False,        # let raise_for_status() handle final failure
        )
        adapter = HTTPAdapter(max_retries=retry)
        from .auth.session import BearerAuth
        self._session = requests.Session()
        self._session.auth = BearerAuth(self)
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Requests that may not be repeated (POST and PATCH without an
        # Idempotency-Key, printing) are retried only when nothing reached the
        # server: a failed connection or 429. Keep-alive is off because a stale
        # pooled connection would fail in a way that cannot be told apart from
        # a request the server already acted on.
        self._no_retry_session = requests.Session()
        self._no_retry_session.auth = BearerAuth(self)
        self._no_retry_session.headers.update({"Connection": "close", "User-Agent": USER_AGENT})
        unprocessed_only = HTTPAdapter(max_retries=Retry(
            total=3, connect=3, read=0, other=0, status=3, backoff_factor=1,
            status_forcelist={429}, allowed_methods=False, raise_on_status=False))
        self._no_retry_session.mount("https://", unprocessed_only)
        self._no_retry_session.mount("http://", unprocessed_only)

        # Signed storage URLs carry their own authorization; the API key must
        # never reach the storage host.
        self._storage_session = requests.Session()
        self._storage_session.mount("https://", adapter)
        self._storage_session.mount("http://", adapter)

        # Initialize resource operations
        from .resources import FileOperations, DatasetOperations, SampleOperations, \
        ProjectOperations, UserOperations, InstrumentOperations, DeletionOperations, \
        GraphOperations, AccountOperations, IngestionOperations, ServiceAccountOperations, \
        AccessGroupOperations, PostprocessingOperations, PrintOperations

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
        self.postprocessing = PostprocessingOperations(self)
        self.print = PrintOperations(self)
        self._authorization = None
        self._capabilities = None
        self._profile_stale = False
        self.upload_progress = None

        self.request_ingestion = True
        self.replace_existing = False

    def _load_profile(self, refresh: bool = False) -> None:
        """Populate the cached authorization and capability blocks."""
        from .models import AccountAuthorization, AccountCapabilities

        if self._authorization is not None and not self._profile_stale and not refresh:
            return
        self._profile_stale = False
        try:
            profile = self.account.profile()
        except Exception as exc:
            response = getattr(exc, 'response', None)
            status = getattr(response, 'status_code', None)
            # Re-read next time after a transient failure instead of caching
            # "no authority" for the client's lifetime.
            from .auth.errors import SignInError
            self._profile_stale = (
                isinstance(exc, (requests.ConnectionError, requests.Timeout, SignInError))
                or status in (401, 429) or (status is not None and status >= 500))
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

    @property
    def credential_source(self) -> str:
        """What this client authenticates with: 'argument', 'CRUCIBLE_API_KEY',
        'config file' (API keys), 'sign-in' (stored by login), or 'this session'."""
        return self._credential.source

    def login(self, method: str = 'auto', store: Optional[str] = None,
              open_browser: bool = True, notify: Callable[[str, str], None] = print) -> Dict:
        """Sign in with a browser and use that session from now on.

        Args:
            method: 'browser' (this computer's browser), 'device' (a code
                approved in any browser, for SSH or headless machines), or
                'auto', which picks the browser when one is available here.
            store: Where to keep the tokens: 'auto' (the OS keyring, else a
                0600 file), 'keyring', 'file', or 'memory' (this client only).
                Defaults to the auth_store setting.
            open_browser: Open the browser automatically for the browser method.
            notify: Called with (message, url) to show the person where to go.

        Returns:
            Dict: {'user_unique_id', 'store', 'grant'}
        """
        from .auth.session import SessionCredential, save_sign_in, sign_in
        from .auth.store import open_store
        tokens = sign_in(self.api_url, method, open_browser=open_browser, notify=notify)
        token_store = open_store(store)
        save_sign_in(tokens, token_store)
        self._credential = SessionCredential(tokens, token_store)
        self.api_key = None
        self._step_up_credential = None
        self.refresh_profile()
        return {'user_unique_id': tokens.user_unique_id, 'store': token_store.name,
                'grant': tokens.grant}

    def logout(self) -> bool:
        """End and forget the sign-in stored for this API address.

        Returns:
            bool: False when there was no stored sign-in.
        """
        from .auth.session import sign_out
        from .auth.store import signed_in, store_for
        entry = signed_in(self.api_url)
        if entry is None:
            return False
        return sign_out(self.api_url, store_for(entry))

    def _step_up(self, response):
        """Auth for one retry after a recent-sign-in refusal, or None.

        Only when the CLI installed a handler (crucible.auth.stepup) and on
        the main thread: a library or worker thread never prompts.
        """
        import threading
        from .auth import stepup
        code = _error_code(response) if response.status_code in (401, 403) else None
        if code not in stepup.STEP_UP_CODES or stepup.handler() is None:
            return None
        if threading.current_thread() is not threading.main_thread():
            return None
        current = self._step_up_credential
        if current is None or not current.tokens.signed_in_within(stepup.RECENT_SECONDS):
            current = stepup.handler()(self, code)
            if current is None:
                return None
            self._step_up_credential = current
        from .auth.session import StaticBearer
        return StaticBearer(current.bearer())

    def _request(self, method: str, endpoint: str,
                 privilege_mode: Optional[str] = None,
                 retry: bool = True, log_body: bool = True, **kwargs) -> Any:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            privilege_mode: Per-call override of the client's privilege mode.
            retry: Whether transient 502/503/504 responses and lost
                responses may be retried. Only GET, HEAD, OPTIONS, PUT and
                DELETE, and requests carrying an Idempotency-Key, are ever
                retried that way, since a POST or PATCH whose response was
                lost may already have taken effect. 429 and connection
                failures, where nothing was processed, are retried for every
                request, including with retry=False.
            log_body: Whether the response body may be written to the debug
                log. Set False when it carries credentials such as signed URLs.
            **kwargs: Additional arguments to pass to requests, including a
                timeout that replaces the configured one.

        Returns:
            Parsed JSON response

        Raises:
            crucible.errors.CrucibleAPIError: For HTTP errors (4xx, 5xx); a
                requests HTTPError with status, code, detail and request_id
            requests.exceptions.ConnectionError: For connection failures
            requests.exceptions.Timeout: For timeout errors
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        logger.debug(f"{method.upper()} {url}")
        timeout = kwargs.pop('timeout', None) or (self._config.connect_timeout,
                                                  self._config.read_timeout)
        mode = privilege_mode if privilege_mode is not None else self.privilege_mode
        if mode is not None:
            if mode not in PRIVILEGE_MODES:
                raise ValueError(
                    f"privilege_mode must be one of: {', '.join(PRIVILEGE_MODES)}.")
            headers = dict(kwargs.pop('headers', None) or {})
            headers.setdefault('Crucible-Privilege-Mode', mode)
            kwargs['headers'] = headers
        headers_sent = kwargs.get('headers') or {}
        repeatable = (method.upper() in _REPEATABLE_METHODS
                      or any(name.lower() == 'idempotency-key' for name in headers_sent))
        session = self._session if retry and repeatable else self._no_retry_session
        response = session.request(method, url, timeout=timeout, **kwargs)
        if response.status_code == 401 and self._credential.kind == 'session' \
                and _error_code(response) is None and self._credential.renew():
            response = session.request(method, url, timeout=timeout, **kwargs)
        stepped_up = self._step_up(response)
        if stepped_up is not None:
            response = session.request(method, url, timeout=timeout, auth=stepped_up, **kwargs)
        logger.debug(f"Status: {response.status_code}")
        if log_body:
            logger.debug(f"Response: {response.text}")
        _warn_if_deprecated(method, endpoint, response)
        if not response.ok:
            from .errors import CrucibleAPIError
            raise CrucibleAPIError.from_response(response)
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

    @_removed_parameter('resource_id', 'resource_mfid')
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

    @_removed_parameter('resource_id', 'resource_mfid')
    def get(self, resource_mfid: str, resource_type: str = None,
            include_metadata: bool = False, include_links: bool = False,
            include_owner: bool = True, include_datasets: bool = False) -> Dict:
        """
        Get a resource by ID with automatic type detection.

        Args:
            resource_mfid (str): Resource MFID
            resource_type (str, optional): Resource type ('sample', 'dataset',
                                          'project', or 'instrument').
                                          If not provided, will be auto-detected.
            include_metadata (bool): Include scientific metadata
            include_links (bool): Include immediate parent/child/associated links
            include_owner (bool): Resolve the owner into a public-safe user object (default: True)
            include_datasets (bool): For samples, also embed the linked dataset records
                (default: False). Deprecated by the API: use include_links.

        Returns:
            Dict: Resource data

        Raises:
            ValueError: If resource type is unknown or not supported
        """
        if include_datasets:
            import warnings
            warnings.warn(
                "include_datasets is deprecated by the Crucible API; use include_links=True, "
                "or client.datasets.list(sample_mfid=...) for the linked datasets.",
                DeprecationWarning, stacklevel=2)
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
            params['include_datasets'] = include_datasets
            raw = self._request('get', f"/resources/{resource_mfid}", params=params)
            return require_canonical_identifier(raw, 'resource')

        if resource_type == "sample":
            sample_options = {
                'include_links': include_links,
                'include_metadata': include_metadata,
                'include_owner': include_owner,
            }
            return self.samples._get_by_mfid(
                resource_mfid, include_datasets=include_datasets, **sample_options)
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

    @_removed_parameter('resource_id', 'resource_mfid')
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
        return self._request('get', f"/resources/{resource_mfid}/links") or []

    @_removed_parameter('parent_id', 'parent_mfid')
    @_removed_parameter('child_id', 'child_mfid')
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

    @_removed_parameter('id_a', 'resource_mfid_a')
    @_removed_parameter('id_b', 'resource_mfid_b')
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

    @_removed("use client.datasets.download() or client.samples.download() instead.")
    def download(self, *args, **kwargs):
        """Removed in 4.0.0: use client.datasets.download() or client.samples.download() instead."""


def _error_code(response) -> Optional[str]:
    """detail.code (or a step-up challenge's error) from an API error response."""
    challenge = response.headers.get('WWW-Authenticate', '')
    if 'insufficient_user_authentication' in challenge:
        return 'insufficient_user_authentication'
    try:
        detail = response.json().get('detail')
    except (ValueError, AttributeError):
        return None
    return detail.get('code') if isinstance(detail, dict) else None


def _resolve_credential(config, api_url: str, api_key: Optional[str]):
    """The credential a new client uses, in precedence order."""
    from .auth.session import ApiKeyCredential, SessionCredential
    from .auth.store import signed_in, store_for
    if api_key:
        return ApiKeyCredential(api_key, 'argument')
    configured = config._data.get('api_key')
    if configured and config.source('api_key') == 'environment':
        return ApiKeyCredential(configured, 'CRUCIBLE_API_KEY')
    entry = signed_in(api_url)
    if entry:
        try:
            store = store_for(entry)
            tokens = store.load(api_url)
        except Exception as exc:
            logger.warning("Could not read the stored sign-in for %s: %s", api_url, exc)
            tokens = None
        if tokens is not None:
            return SessionCredential(tokens, store)
    if configured:
        return ApiKeyCredential(configured, 'config file')
    raise ValueError(
        "Not signed in to Crucible. Run 'crucible login', or set an API key with "
        "'crucible config init'.")


def _warn_if_deprecated(method: str, endpoint: str, response) -> None:
    """Warn once per route when the API marks it deprecated (RFC 9745, 8594)."""
    deprecation = response.headers.get('Deprecation')
    if not isinstance(deprecation, str) or not deprecation:
        return
    import re
    route = re.sub(r'/[0-9a-z]{26}(?=/|$)|/\d+(?=/|$)|/0000-\d{4}-\d{4}-\d{3}[\dX](?=/|$)', '/{id}',
                   endpoint.split('?')[0])
    key = (method.upper(), route)
    if key in _deprecations_seen:
        return
    _deprecations_seen.add(key)
    message = f"The Crucible API marks {method.upper()} {route} as deprecated"
    since = _http_date(deprecation)
    if since:
        message += f" (since {since})"
    sunset = response.headers.get('Sunset')
    if sunset:
        message += f"; it will be removed after {sunset}"
    link = _deprecation_link(response.headers.get('Link', ''))
    if link:
        message += f"; see {link}"
    import warnings
    warnings.warn(message + ". Upgrading nano-crucible may remove this call.",
                  DeprecationWarning, stacklevel=_caller_stacklevel())
    logger.debug(message)


def _caller_stacklevel() -> int:
    """Stack level of the first frame outside this package, so warnings are attributed to the caller."""
    import os
    import sys
    package = os.path.dirname(os.path.abspath(__file__)) + os.sep
    frame, level = sys._getframe(2), 2
    while frame is not None and os.path.abspath(frame.f_code.co_filename).startswith(package):
        frame, level = frame.f_back, level + 1
    return level


def _http_date(value: str) -> Optional[str]:
    """An RFC 9745 '@epoch' date as YYYY-MM-DD, or the value as sent."""
    if value.startswith('@') and value[1:].isdigit():
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(value[1:]), timezone.utc).strftime('%Y-%m-%d')
    return None if value.strip().lower() == 'true' else value


def _deprecation_link(header: str) -> Optional[str]:
    import re
    for target, params in re.findall(r'<([^>]+)>\s*((?:;[^,]*)*)', header):
        if re.search(r'rel="?deprecation"?', params):
            return target
    return None
