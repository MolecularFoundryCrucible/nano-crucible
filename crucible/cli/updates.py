"""Tell the shell user when a newer nano-crucible release is on PyPI."""

import json
import os
import re
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Optional, Tuple

PYPI_URL = 'https://pypi.org/pypi/nano-crucible/json'
CHECK_INTERVAL = 24 * 3600
_STABLE = re.compile(r'^\d+(\.\d+)*$')


def _version_tuple(version: str) -> Optional[Tuple[int, ...]]:
    return tuple(int(part) for part in version.split('.')) if _STABLE.match(version) else None


def _editable_install() -> bool:
    if (Path(__file__).resolve().parents[2] / 'pyproject.toml').exists():
        return True
    try:
        direct_url = metadata.distribution('nano-crucible').read_text('direct_url.json')
    except metadata.PackageNotFoundError:
        return True
    if not direct_url:
        return False
    try:
        return bool(json.loads(direct_url).get('dir_info', {}).get('editable'))
    except ValueError:
        return False


def _cache_file() -> Path:
    from platformdirs import user_cache_dir
    return Path(user_cache_dir('nano-crucible')) / 'update_check.json'


def _latest_from_pypi(current: str, timeout: float) -> Optional[str]:
    import requests
    response = requests.get(PYPI_URL, timeout=timeout,
                            headers={'User-Agent': f'nano-crucible/{current}'})
    response.raise_for_status()
    releases = response.json().get('releases') or {}
    stable = [version for version, files in releases.items()
              if _version_tuple(version) and files
              and not all(item.get('yanked') for item in files)]
    return max(stable, key=_version_tuple) if stable else None  # type: ignore[arg-type]


def available_update(current: str, enabled: bool = True, timeout: float = 2.0) -> Optional[str]:
    """The newest stable release when it is newer than current, else None.

    PyPI is asked at most once a day; the answer is cached. Editable and
    pre-release installs are never checked, and every failure is silent.
    """
    if not enabled or _version_tuple(current) is None or _editable_install():
        return None
    cache = _cache_file()
    latest = None
    try:
        cached = json.loads(cache.read_text())
        if time.time() - cached.get('checked_at', 0) < CHECK_INTERVAL:
            latest = cached.get('latest')
        else:
            raise ValueError('stale')
    except (OSError, ValueError, AttributeError):
        try:
            latest = _latest_from_pypi(current, timeout)
        except Exception:
            return None
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({'checked_at': time.time(), 'latest': latest}))
        except OSError:
            pass
    newer, now = _version_tuple(latest or ''), _version_tuple(current)
    return latest if newer and now and newer > now else None


def upgrade_command() -> str:
    """How to upgrade, matched to the tool that installed this copy."""
    prefix = sys.prefix.replace(os.sep, '/')
    if '/uv/tools/' in prefix:
        return 'uv tool upgrade nano-crucible'
    if '/pipx/venvs/' in prefix:
        return 'pipx upgrade nano-crucible'
    return 'pip install -U nano-crucible'
