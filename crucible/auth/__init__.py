"""Signing people in to Crucible through the API's OAuth 2.0 server.

The CLI is the public client ``nano-crucible``: a browser sign-in with a
loopback redirect (RFC 8252) where a browser runs on this machine, and the
device authorization grant (RFC 8628) where none does.
"""

from .errors import BrowserSignInRequired, SignInError, SignInRequired
from .tokens import TokenSet

__all__ = ['BrowserSignInRequired', 'SignInError', 'SignInRequired', 'TokenSet']
