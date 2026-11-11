"""Credentials a client sends, and the sign-in flows that produce a session."""

import logging
import threading
import webbrowser

import requests

from . import oauth
from .errors import BrowserSignInRequired, SignInError, SignInRequired
from .loopback import LoopbackListener, browser_available
from .store import TokenStore, forget, remember
from .tokens import TokenSet

logger = logging.getLogger(__name__)


class ApiKeyCredential:
    """An API key, from an argument, CRUCIBLE_API_KEY, or the config file."""

    kind = 'api_key'

    def __init__(self, key: str, source: str):
        self.key = key
        self.source = source

    def bearer(self) -> str:
        return self.key

    def renew(self) -> bool:
        return False


class SessionCredential:
    """A sign-in session whose access token is renewed before it expires.

    Renewal re-reads the store under an inter-process lock, so concurrent
    commands share one rotation instead of replaying a spent refresh token,
    which would end the session.
    """

    kind = 'session'

    def __init__(self, tokens: TokenSet, store: TokenStore):
        self.tokens = tokens
        self.store = store
        self.source = 'sign-in' if store.name != 'memory' else 'this session'
        self._lock = threading.Lock()
        if store.name == 'memory':
            store.save(tokens)

    def bearer(self) -> str:
        with self._lock:
            if not self.tokens.fresh():
                self._renew(self.tokens.access_token)
            return self.tokens.access_token

    def renew(self) -> bool:
        """Renew after the API refused the access token. False if nothing changed."""
        with self._lock:
            before = self.tokens.access_token
            self._renew(before, force=True)
            return self.tokens.access_token != before

    def _renew(self, stale: str, force: bool = False) -> None:
        api_url = self.tokens.api_url
        with self.store.lock():
            current = self.store.load(api_url)
            if current is None:
                raise SignInRequired('You are signed out of Crucible. Run `crucible login`.')
            if current.access_token != stale and current.fresh():
                self.tokens = current
                return
            if not force and current.fresh():
                self.tokens = current
                return
            try:
                renewed = oauth.refresh(current)
            except SignInRequired:
                self.store.delete(api_url)
                forget(api_url)
                raise
            self.store.save(renewed)
            self.tokens = renewed


class BearerAuth(requests.auth.AuthBase):
    """Sets the Authorization header per request from the client's credential."""

    def __init__(self, client):
        self._client = client

    def __call__(self, request):
        request.headers['Authorization'] = f'Bearer {self._client._credential.bearer()}'
        return request


def _account_of(api_url: str, tokens: TokenSet) -> str:
    from ..config import config
    try:
        response = requests.get(f'{api_url}/account', timeout=(config.connect_timeout, config.read_timeout),
                                headers={'Authorization': f'Bearer {tokens.access_token}',
                                         'User-Agent': oauth._headers()['User-Agent']})
    except requests.RequestException as exc:
        raise SignInError(f'Signed in, but could not read the account: {exc}') from exc
    if not response.ok:
        raise SignInError(f'Signed in, but could not read the account (HTTP {response.status_code}).')
    unique_id = response.json().get('user_unique_id')
    if not unique_id:
        raise SignInError('Signed in, but the API did not say which account.')
    return unique_id


def sign_in(api_url: str, method: str = 'auto', *, required_user: str | None = None,
            max_age: int | None = None, open_browser: bool = True, provider: str | None = None,
            notify=print, cancelled: threading.Event | None = None) -> TokenSet:
    """Sign a person in and return the session's tokens, checked against required_user.

    method is 'browser' (loopback redirect, this machine's browser), 'device'
    (a code approved in any browser), or 'auto', which picks the browser when
    one can reach this machine (RFC 10027: no cross-device flow on one device).
    """
    api_url = api_url.rstrip('/')
    if method not in ('auto', 'browser', 'device'):
        raise ValueError("method must be 'auto', 'browser' or 'device'.")
    if method == 'auto':
        method = 'browser' if browser_available() else 'device'
    metadata = oauth.discover(api_url)

    if method == 'browser':
        listener = LoopbackListener()
        try:
            verifier, challenge = oauth.new_pkce()
            url = oauth.authorization_url(metadata, listener.redirect_uri, listener.state, challenge,
                                          max_age=max_age, required_user=required_user, provider=provider)
            opened = False
            if open_browser:
                try:
                    opened = webbrowser.open(url)
                except Exception:
                    opened = False
            notify(('Your browser should open to sign in. If it does not, open this address:'
                    if opened else 'Open this address in a browser on this computer to sign in:'), url)
            code = listener.wait(metadata['issuer'], cancelled=cancelled)
        finally:
            listener.close()
        tokens = oauth.exchange_code(api_url, metadata, code, verifier, listener.redirect_uri)
    else:
        device = oauth.start_device(metadata)
        notify('On any device, open the address below and enter the code '
               f"{device['user_code']}:", device['verification_uri'])
        if device.get('verification_uri_complete'):
            notify('Or open this address, which fills in the code:', device['verification_uri_complete'])
        tokens = oauth.poll_device(api_url, metadata, device)

    unique_id = _account_of(api_url, tokens)
    if required_user and unique_id != required_user:
        oauth.revoke(tokens)
        raise SignInError(
            f'You signed in as {unique_id}, but this needs {required_user}. '
            'Sign in with that account instead.', 'login_required')
    tokens.user_unique_id = unique_id
    return tokens


def save_sign_in(tokens: TokenSet, store: TokenStore) -> None:
    """Store tokens as api_url's sign-in, replacing (and ending) any earlier one."""
    with store.lock():
        previous = store.load(tokens.api_url)
        store.save(tokens)
        remember(tokens, store)
    if previous is not None and previous.refresh_token != tokens.refresh_token:
        oauth.revoke(previous)


def sign_out(api_url: str, store: TokenStore) -> bool:
    """End and delete api_url's stored sign-in. False when there was none."""
    with store.lock():
        tokens = store.load(api_url)
        store.delete(api_url)
        forget(api_url)
    if tokens is None:
        return False
    oauth.revoke(tokens)
    return True


def require_local_browser() -> None:
    if not browser_available():
        raise BrowserSignInRequired(
            'This needs a browser sign-in on this computer, and none is available here '
            '(remote or headless session).')


class StaticBearer(requests.auth.AuthBase):
    """A fixed bearer token for one request."""

    def __init__(self, token: str):
        self._token = token

    def __call__(self, request):
        request.headers['Authorization'] = f'Bearer {self._token}'
        return request
