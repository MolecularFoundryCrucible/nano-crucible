"""Where sign-in tokens live between commands.

The OS credential store (keyring) by default, as gh does, with a 0600 file
in the config directory where no keyring is reachable, such as headless
Linux without a D-Bus session. Entries are keyed by API address.
"""

import contextlib
import json
import logging
import os
import sys
from pathlib import Path

from .tokens import TokenSet

logger = logging.getLogger(__name__)

SERVICE = 'nano-crucible'
AUTH_STORES = ('auto', 'keyring', 'file', 'memory')


def _config_dir() -> Path:
    from platformdirs import user_config_dir
    return Path(user_config_dir('nano-crucible'))


@contextlib.contextmanager
def _locked(path: Path):
    """An exclusive inter-process lock on path: POSIX record locks (fcntl.lockf,
    which works over NFS) or msvcrt on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == 'win32':
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.lockf(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.lockf(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class TokenStore:
    name = 'memory'

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def load(self, api_url: str) -> TokenSet | None:
        data = self._entries.get(api_url)
        return TokenSet.from_dict(data) if data else None

    def save(self, tokens: TokenSet) -> None:
        self._entries[tokens.api_url] = tokens.to_dict()

    def delete(self, api_url: str) -> None:
        self._entries.pop(api_url, None)

    @contextlib.contextmanager
    def lock(self):
        yield


class FileStore(TokenStore):
    """credentials.json in the 0700 config directory, written 0600."""

    name = 'file'

    def __init__(self, directory: Path | None = None):
        super().__init__()
        self.directory = directory or _config_dir()
        self.path = self.directory / 'credentials.json'

    def _read(self) -> dict:
        try:
            with open(self.path) as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.warning('Ignoring unreadable %s: %s', self.path, exc)
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.directory, 0o700)
        temporary = self.path.with_name(f'.{self.path.name}.{os.getpid()}.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
        os.replace(temporary, self.path)

    def load(self, api_url):
        data = self._read().get(api_url)
        return TokenSet.from_dict(data) if data else None

    def save(self, tokens):
        data = self._read()
        data[tokens.api_url] = tokens.to_dict()
        self._write(data)

    def delete(self, api_url):
        data = self._read()
        if data.pop(api_url, None) is not None:
            self._write(data)

    @contextlib.contextmanager
    def lock(self):
        with _locked(self.directory / 'credentials.lock'):
            yield


class KeyringStore(TokenStore):
    """The OS credential store: macOS Keychain, Windows Credential Locker, or
    Secret Service on Linux."""

    name = 'keyring'

    def __init__(self, backend=None, directory: Path | None = None):
        super().__init__()
        import keyring
        self._keyring = keyring
        self._backend = backend or keyring.get_keyring()
        self.directory = directory or _config_dir()

    def load(self, api_url):
        value = self._backend.get_password(SERVICE, api_url)
        return TokenSet.from_dict(json.loads(value)) if value else None

    def save(self, tokens):
        self._backend.set_password(SERVICE, tokens.api_url, json.dumps(tokens.to_dict()))

    def delete(self, api_url):
        with contextlib.suppress(self._keyring.errors.PasswordDeleteError):
            self._backend.delete_password(SERVICE, api_url)

    @contextlib.contextmanager
    def lock(self):
        with _locked(self.directory / 'credentials.lock'):
            yield


def _usable_keyring():
    """The active keyring backend, or None when it cannot store secrets here."""
    if sys.platform.startswith('linux') and not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        return None
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        backend = keyring.get_keyring()
    except Exception:
        return None
    if isinstance(backend, fail.Keyring) or 'null' in type(backend).__module__:
        return None
    try:
        if backend.priority <= 0:
            return None
    except Exception:
        return None
    return backend


def _index_path() -> Path:
    return _config_dir() / 'signins.json'


def _read_index() -> dict:
    try:
        with open(_index_path()) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_index(data: dict) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(data, handle, indent=2)
    os.replace(temporary, path)


def remember(tokens: TokenSet, store: TokenStore) -> None:
    """Record, without secrets, that api_url has a sign-in in store."""
    if store.name == 'memory':
        return
    data = _read_index()
    data[tokens.api_url] = {'store': store.name, 'user_unique_id': tokens.user_unique_id}
    _write_index(data)


def forget(api_url: str) -> None:
    data = _read_index()
    if data.pop(api_url, None) is not None:
        _write_index(data)


def signed_in(api_url: str) -> dict | None:
    """The index entry for api_url's sign-in, if one was stored.

    Reading the index never touches the OS keyring, so people who only use
    API keys are never prompted to unlock it.
    """
    return _read_index().get(api_url)


def store_for(entry: dict) -> TokenStore:
    """The store an index entry names."""
    return KeyringStore() if entry.get('store') == 'keyring' else FileStore()


def open_store(kind: str | None = None) -> TokenStore:
    """The token store for the auth_store setting (default auto)."""
    if kind is None:
        from ..config import config
        kind = config.auth_store
    if kind not in AUTH_STORES:
        raise ValueError(f"auth_store must be one of: {', '.join(AUTH_STORES)}.")
    if kind == 'memory':
        return TokenStore()
    if kind == 'file':
        return FileStore()
    backend = _usable_keyring()
    if backend is not None:
        return KeyringStore(backend)
    if kind == 'keyring':
        raise ValueError('auth_store is keyring, but no usable OS keyring is available here.')
    return FileStore()
