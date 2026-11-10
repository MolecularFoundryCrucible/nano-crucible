import copy
import os
import time

import pytest
import requests


@pytest.fixture(autouse=True)
def _isolated(tmp_path_factory, monkeypatch):
    """Keep unit tests away from the developer's config, environment, keyring, timezone and network."""
    from crucible.auth import stepup
    from crucible import client as client_module
    from crucible.config import config
    import sys
    config_module = sys.modules['crucible.config.config']

    for name in list(os.environ):
        if name.startswith('CRUCIBLE_') or name in ('NO_COLOR', 'FORCE_COLOR'):
            monkeypatch.delenv(name)

    config_dir = tmp_path_factory.mktemp('nano-crucible-config')
    cache_dir = tmp_path_factory.mktemp('nano-crucible-cache')
    monkeypatch.setattr(config_module, 'user_config_dir', lambda *a, **k: str(config_dir))
    monkeypatch.setattr(config_module, 'user_cache_dir', lambda *a, **k: str(cache_dir))
    monkeypatch.setattr('crucible.auth.store._config_dir', lambda: config_dir)
    monkeypatch.setattr('crucible.auth.store._usable_keyring', lambda: None)

    def no_network(self, request, *args, **kwargs):
        raise RuntimeError(f"unit tests must not reach the network: {request.method} {request.url}")
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', no_network)

    saved_tz = os.environ.get('TZ')
    if hasattr(time, 'tzset'):
        os.environ['TZ'] = 'UTC'
        time.tzset()

    for name, value in list(vars(config).items()):
        monkeypatch.setattr(config, name, copy.copy(value))
    config.__init__()
    stepup.install(None)
    client_module._deprecations_seen.clear()
    yield
    stepup.install(None)
    client_module._deprecations_seen.clear()
    if hasattr(time, 'tzset'):
        if saved_tz is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = saved_tz
        time.tzset()
