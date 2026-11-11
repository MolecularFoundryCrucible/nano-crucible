"""The hook a client uses when an action needs a recent sign-in.

Only the CLI installs a handler; library users get the API error and can
sign in with client.login(). A handler takes (client, code) and returns a
SessionCredential for one retry, or None.
"""

STEP_UP_CODES = ('hub_session_required', 'insufficient_user_authentication', 'browser_sign_in_required')
RECENT_SECONDS = 540

_handler = None


def install(handler) -> None:
    global _handler
    _handler = handler


def handler():
    return _handler
