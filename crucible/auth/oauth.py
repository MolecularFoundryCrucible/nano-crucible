"""The protocol side of signing in: discovery (RFC 8414), PKCE (RFC 7636), and
the token, revocation and device endpoints (RFC 6749, 7009, 8628)."""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import requests

from .errors import SignInError, SignInRequired
from .tokens import TokenSet

CLIENT_ID = 'nano-crucible'
DEVICE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code'


def _headers() -> dict:
    from ..client import USER_AGENT
    return {'Accept': 'application/json', 'User-Agent': USER_AGENT}


_metadata_cache: dict[str, dict] = {}


def _timeout():
    from ..config import config
    return (config.connect_timeout, config.read_timeout)


def discover(api_url: str, refresh: bool = False) -> dict:
    """The API's authorization server metadata, checked against api_url."""
    api_url = api_url.rstrip('/')
    if not refresh and api_url in _metadata_cache:
        return _metadata_cache[api_url]
    try:
        response = requests.get(f'{api_url}/.well-known/oauth-authorization-server',
                                timeout=_timeout(), headers=_headers())
    except requests.RequestException as exc:
        raise SignInError(f'Could not reach {api_url} to sign in: {exc}') from exc
    if response.status_code == 404:
        raise SignInError(f'Signing in is not available on {api_url}.')
    if not response.ok:
        raise SignInError(f'Sign-in is unavailable on {api_url} (HTTP {response.status_code}).')
    metadata = response.json()
    if (metadata.get('issuer') or '').rstrip('/') != api_url:
        raise SignInError(
            f"The sign-in server says it is {metadata.get('issuer')!r}, not {api_url!r}; refusing to sign in.")
    _metadata_cache[api_url] = metadata
    return metadata


def new_pkce() -> tuple[str, str]:
    """A code verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest())
    return verifier, challenge.rstrip(b'=').decode('ascii')


def authorization_url(metadata: dict, redirect_uri: str, state: str, challenge: str,
                      max_age: int | None = None, required_user: str | None = None,
                      provider: str | None = None) -> str:
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': redirect_uri,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    if max_age is not None:
        params['max_age'] = str(max_age)
    if required_user:
        params['required_user'] = required_user
    if provider:
        params['provider'] = provider
    return f"{metadata['authorization_endpoint']}?{urlencode(params)}"


def _post(url: str, fields: dict) -> requests.Response:
    try:
        return requests.post(url, data=fields, timeout=_timeout(), headers=_headers())
    except requests.RequestException as exc:
        raise SignInError(f'Could not reach the sign-in server: {exc}') from exc


def _oauth_error(response: requests.Response) -> tuple[str | None, str | None]:
    try:
        body = response.json()
    except ValueError:
        return None, None
    return body.get('error'), body.get('error_description')


def exchange_code(api_url: str, metadata: dict, code: str, verifier: str, redirect_uri: str) -> TokenSet:
    response = _post(metadata['token_endpoint'], {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'code': code,
        'code_verifier': verifier,
        'redirect_uri': redirect_uri,
    })
    if not response.ok:
        error, description = _oauth_error(response)
        raise SignInError(f'The sign-in code was not accepted ({error or response.status_code}).', error)
    return TokenSet.from_response(api_url, response.json(), 'authorization_code')


def refresh(tokens: TokenSet) -> TokenSet:
    """A new token pair. Raises SignInRequired when the session has ended."""
    if not tokens.refresh_token:
        raise SignInRequired('Your Crucible sign-in has expired. Run `crucible login`.')
    metadata = discover(tokens.api_url)
    response = _post(metadata['token_endpoint'], {
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'refresh_token': tokens.refresh_token,
    })
    if not response.ok:
        error, _ = _oauth_error(response)
        if error == 'invalid_grant':
            raise SignInRequired('Your Crucible sign-in has ended. Run `crucible login`.', error)
        raise SignInError(f'Could not renew your Crucible sign-in ({error or response.status_code}).', error)
    renewed = TokenSet.from_response(tokens.api_url, response.json(), tokens.grant)
    renewed.user_unique_id = tokens.user_unique_id
    if renewed.auth_time is None:
        renewed.auth_time = tokens.auth_time
    return renewed


def revoke(tokens: TokenSet) -> None:
    """End the session on the server. Unreachable servers are ignored."""
    token = tokens.refresh_token or tokens.access_token
    try:
        metadata = discover(tokens.api_url)
        _post(metadata['revocation_endpoint'], {'client_id': CLIENT_ID, 'token': token})
    except SignInError:
        pass


def start_device(metadata: dict) -> dict:
    endpoint = metadata.get('device_authorization_endpoint')
    if not endpoint:
        raise SignInError('This server does not offer sign-in without a browser.')
    response = _post(endpoint, {'client_id': CLIENT_ID})
    if not response.ok:
        error, _ = _oauth_error(response)
        raise SignInError(f'Could not start a device sign-in ({error or response.status_code}).', error)
    return response.json()


def poll_device(api_url: str, metadata: dict, device: dict, sleep=time.sleep,
                clock=time.monotonic) -> TokenSet:
    """Wait for the person to approve the device code (RFC 8628 3.4-3.5)."""
    interval = int(device.get('interval') or 5)
    deadline = clock() + int(device.get('expires_in') or 600)
    while True:
        sleep(interval)
        if clock() >= deadline:
            raise SignInError('The code expired before it was approved. Run the sign-in again.', 'expired_token')
        response = _post(metadata['token_endpoint'], {
            'grant_type': DEVICE_GRANT,
            'device_code': device['device_code'],
            'client_id': CLIENT_ID,
        })
        if response.ok:
            return TokenSet.from_response(api_url, response.json(), 'device_code')
        error, _ = _oauth_error(response)
        if error == 'authorization_pending':
            continue
        if error == 'slow_down':
            interval += 5
            continue
        if error == 'access_denied':
            raise SignInError('The sign-in was denied.', error)
        if error == 'expired_token':
            raise SignInError('The code expired before it was approved. Run the sign-in again.', error)
        raise SignInError(f'The device sign-in failed ({error or response.status_code}).', error)
