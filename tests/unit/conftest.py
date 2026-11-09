import pytest


@pytest.fixture(autouse=True)
def _no_real_sign_in(tmp_path_factory, monkeypatch):
    """Keep unit tests away from the developer's stored sign-ins and keyring."""
    directory = tmp_path_factory.mktemp('nano-crucible-config')
    monkeypatch.setattr('crucible.auth.store._config_dir', lambda: directory)
