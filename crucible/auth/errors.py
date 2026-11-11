class SignInError(Exception):
    """A sign-in did not complete: refused, cancelled, expired, or misconfigured.

    error is the OAuth error code when the server sent one.
    """

    def __init__(self, message: str, error: str | None = None):
        super().__init__(message)
        self.error = error


class SignInRequired(SignInError):
    """The stored sign-in ended; sign in again with `crucible login`."""


class BrowserSignInRequired(SignInError):
    """The action needs a recent browser sign-in on this machine, which is not available here."""
