"""Sign in again in the browser when an action needs a recent sign-in."""

import sys


def install_for(args) -> None:
    """Enable the step-up prompt for an interactive, non-JSON command."""
    from ..auth import stepup
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()
                   and not getattr(args, 'json', False))
    stepup.install(_handle if interactive else None)


def _notify(message, url):
    print(f"  {message}\n  {url}\n", file=sys.stderr)


def _handle(client, code):
    """Sign the same account in again with this computer's browser.

    Device-code sessions cannot satisfy these checks (the API refuses them),
    so without a local browser this returns None and the refusal stands.
    """
    from ..auth.loopback import browser_available
    from ..auth.session import SessionCredential, save_sign_in, sign_in
    from ..auth.store import TokenStore
    from .helpers import prompt_confirm
    if not browser_available():
        return None
    credential = client._credential
    if credential.kind == 'session':
        required = credential.tokens.user_unique_id
    else:
        required = client.whoami().get('user_unique_id')
    if not prompt_confirm("This needs a fresh sign-in in your browser. Sign in now?", default=True):
        return None
    tokens = sign_in(client.api_url, 'browser', required_user=required, max_age=0, notify=_notify)
    if credential.kind == 'session' and credential.store.name != 'memory':
        save_sign_in(tokens, credential.store)
        client._credential = SessionCredential(tokens, credential.store)
        return client._credential
    return SessionCredential(tokens, TokenStore())
