"""The browser sign-in's redirect target: a one-shot listener on the loopback
interface (RFC 8252 7.3 and 8.3)."""

import http.server
import os
import secrets
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .errors import SignInError

CALLBACK_PATH = '/callback'
_PAGE = """<!doctype html><meta charset="utf-8"><title>Crucible sign-in</title>
<body style="font-family: system-ui, sans-serif; margin: 3rem auto; max-width: 32rem">
<h1 style="font-size: 1.25rem">{heading}</h1><p>{message}</p></body>"""


def browser_available() -> bool:
    """Whether a browser on this machine can reach a loopback listener here.

    Remote sessions (SSH, JupyterHub) and Linux without a display cannot,
    even when Python's webbrowser module would launch a terminal browser.
    """
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY') or os.environ.get('SSH_CLIENT'):
        return False
    if os.environ.get('JUPYTERHUB_API_URL') or os.environ.get('JUPYTERHUB_USER'):
        return False
    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return False
    return True


class _Server(http.server.HTTPServer):
    def __init__(self, address, family):
        self.address_family = family
        self.result = None
        super().__init__(address, _Handler)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path != CALLBACK_PATH:
            self.send_error(404)
            return
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        self.server.result = query
        if 'code' in query:
            heading, message = 'Signed in', 'You can close this tab and go back to the terminal.'
        else:
            heading, message = 'Sign-in not completed', 'Nothing was signed in. You can close this tab.'
        body = _PAGE.format(heading=heading, message=message).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class LoopbackListener:
    """Listen on 127.0.0.1 (or [::1]) at a free port for one redirect."""

    def __init__(self):
        try:
            self._server = _Server(('127.0.0.1', 0), socket.AF_INET)
            host = '127.0.0.1'
        except OSError:
            self._server = _Server(('::1', 0), socket.AF_INET6)
            host = '[::1]'
        self._server.timeout = 0.5
        self.redirect_uri = f'http://{host}:{self._server.server_address[1]}{CALLBACK_PATH}'
        self.state = secrets.token_urlsafe(32)

    def wait(self, issuer: str, timeout: float = 300, cancelled: threading.Event | None = None) -> str:
        """The authorization code, once the redirect arrives and checks out."""
        deadline = time.monotonic() + timeout
        try:
            while self._server.result is None:
                if time.monotonic() >= deadline:
                    raise SignInError('Timed out waiting for the browser sign-in.')
                if cancelled is not None and cancelled.is_set():
                    raise SignInError('Sign-in cancelled.')
                self._server.handle_request()
        finally:
            self._server.server_close()
        result = self._server.result
        if not secrets.compare_digest(result.get('state', ''), self.state):
            raise SignInError('The browser returned a sign-in for another request; refusing it.')
        if (result.get('iss') or '').rstrip('/') != issuer.rstrip('/'):
            raise SignInError('The browser returned a sign-in from another server; refusing it.')
        if 'error' in result:
            error = result['error']
            if error == 'access_denied':
                raise SignInError('The sign-in was cancelled.', error)
            if error == 'login_required':
                raise SignInError('That sign-in was for a different account than required.', error)
            raise SignInError(f'The sign-in failed ({error}).', error)
        if not result.get('code'):
            raise SignInError('The browser returned no sign-in code.')
        return result['code']

    def close(self):
        self._server.server_close()
