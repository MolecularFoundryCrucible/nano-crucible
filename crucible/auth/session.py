"""Credentials a client sends, and the sign-in flows that produce a session."""

import logging
import secrets
import threading
import webbrowser
from typing import Any

import requests

from . import oauth
from .errors import BrowserSignInRequired, SignInError, SignInRequired
from .loopback import LoopbackListener, browser_available
from .store import TokenStore, forget, remember, signed_in, store_for
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


class CodePrompt:
    """How a sign-in asks for the code the API's code page shows.

    The CLI's version also lets the person leave a loopback wait (requested())
    when the browser cannot reach this machine.
    """

    def read_code(self) -> str:
        return input('Sign-in code: ')

    def waiting(self) -> None:
        pass

    def requested(self) -> bool:
        return False


def _open(url: str, open_browser: bool) -> bool:
    if not open_browser:
        return False
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def _paste_code(metadata: dict, prompt: CodePrompt, open_browser: bool, notify,
                **request) -> tuple[str, str, str]:
    redirect_uri = oauth.code_page_uri(metadata)
    verifier, challenge = oauth.new_pkce()
    url = oauth.authorization_url(metadata, redirect_uri, secrets.token_urlsafe(32), challenge, **request)
    opened = _open(url, open_browser and browser_available())
    notify(('Sign in in the browser that opened, then copy the code it shows. If it did not open, '
            'open this address:' if opened else
            'Open this address in any browser, sign in, and copy the code it shows:'), url)
    code = prompt.read_code().strip()
    if not code:
        raise SignInError('No sign-in code was entered.')
    return code, verifier, redirect_uri


def sign_in(api_url: str, method: str = 'auto', *, required_user: str | None = None,
            max_age: int | None = None, open_browser: bool = True, provider: str | None = None,
            notify=print, cancelled: threading.Event | None = None,
            code_prompt: CodePrompt | None = None) -> TokenSet:
    """Sign a person in and return the session's tokens, checked against required_user.

    method is 'browser' (loopback redirect, this machine's browser), 'paste'
    (any browser; the person pastes the code the API's page shows), 'device'
    (a code approved in any browser), or 'auto', which picks the browser when
    one can reach this machine (RFC 10027: no cross-device flow on one device).
    With code_prompt, a browser sign-in switches to 'paste' when
    code_prompt.requested() says so.
    """
    api_url = api_url.rstrip('/')
    if method not in ('auto', 'browser', 'paste', 'device'):
        raise ValueError("method must be 'auto', 'browser', 'paste' or 'device'.")
    if method == 'auto':
        method = 'browser' if browser_available() else 'device'
    metadata = oauth.discover(api_url)
    request: dict[str, Any] = {'max_age': max_age, 'required_user': required_user, 'provider': provider}

    if method in ('browser', 'paste'):
        code = None
        if method == 'browser':
            listener = LoopbackListener()
            try:
                verifier, challenge = oauth.new_pkce()
                redirect_uri = listener.redirect_uri
                url = oauth.authorization_url(metadata, redirect_uri, listener.state, challenge, **request)
                notify(('Your browser should open to sign in. If it does not, open this address:'
                        if _open(url, open_browser) else
                        'Open this address in a browser on this computer to sign in:'), url)
                if code_prompt is not None:
                    code_prompt.waiting()
                code = listener.wait(metadata['issuer'], cancelled=cancelled,
                                     switch=code_prompt.requested if code_prompt is not None else None)
            finally:
                listener.close()
        if code is None:
            code, verifier, redirect_uri = _paste_code(metadata, code_prompt or CodePrompt(), open_browser,
                                                       notify, **request)
        try:
            tokens = oauth.exchange_code(api_url, metadata, code, verifier, redirect_uri)
        except SignInError as exc:
            if redirect_uri != oauth.code_page_uri(metadata):
                raise
            raise SignInError(f'{exc} A code works once, within five minutes; sign in again.',
                              exc.error) from exc
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


def carry_sign_in(old_url: str, new_url: str) -> bool:
    """Move old_url's stored sign-in to new_url when the API at old_url now names
    new_url as its address. False when nothing moved."""
    old_url, new_url = old_url.rstrip('/'), new_url.rstrip('/')
    entry = signed_in(old_url)
    if old_url == new_url or entry is None or signed_in(new_url) is not None:
        return False
    try:
        issuer = oauth.discover(old_url, refresh=True, warn=False)['issuer'].rstrip('/')
    except SignInError:
        return False
    if issuer != new_url:
        return False
    store = store_for(entry)
    with store.lock():
        tokens = store.load(old_url)
        if tokens is None:
            return False
        tokens.api_url = new_url
        store.save(tokens)
        store.delete(old_url)
        forget(old_url)
        remember(tokens, store)
    return True


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
