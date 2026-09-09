import warnings
from types import SimpleNamespace

import pytest

from crucible.cli.config import unset_config_value
from crucible.cli.whoami import execute as execute_whoami
from crucible.client import CrucibleClient
from crucible.config import config as global_config
from crucible.config.config import Config


def test_config_defaults_to_v3_api(monkeypatch):
    monkeypatch.setattr(Config, "_load", lambda self: None)

    config = Config()

    assert config.api_url == "https://crucible.lbl.gov/api/v3"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_client_warns_for_legacy_api_path(version):
    with pytest.warns(FutureWarning, match=f"API {version}"):
        CrucibleClient(
            api_url=f"https://crucible.lbl.gov/api/{version}",
            api_key="test",
        )


def test_client_accepts_custom_url_without_legacy_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        CrucibleClient(
            api_url="https://crucible.lbl.gov/testapi-staging",
            api_key="test",
        )

    assert not caught


def test_cli_surfaces_legacy_api_warning(monkeypatch, capsys):
    original_data = global_config._data.copy()
    original_client = global_config._client
    global_config._data = {
        "api_key": "test",
        "api_url": "https://crucible.lbl.gov/api/v2",
    }
    global_config._client = None
    monkeypatch.setattr(
        CrucibleClient,
        "whoami",
        lambda self: {
            "user_info": {
                "unique_id": "0000-0001-6402-3752",
                "username": "test-user",
                "first_name": "Test",
                "last_name": "User",
            }
        },
    )

    try:
        with pytest.warns(FutureWarning, match="API v2"):
            execute_whoami(SimpleNamespace(verbose=False, debug=False))
    finally:
        global_config._data = original_data
        global_config._client = original_client

    capsys.readouterr()


def test_unset_api_url_restores_package_default(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        "[crucible]\n"
        "api_key = test\n"
        "api_url = https://crucible.lbl.gov/api/v2\n"
    )
    original_data = global_config._data.copy()
    original_sources = global_config._sources.copy()

    monkeypatch.delenv("CRUCIBLE_API_URL", raising=False)
    monkeypatch.setattr(
        Config,
        "config_file_path",
        property(lambda self: config_file),
    )

    try:
        removed, path, env_key = unset_config_value("api_url")

        assert removed is True
        assert path == config_file
        assert env_key == "CRUCIBLE_API_URL"
        assert "api_url" not in config_file.read_text()
        assert global_config.api_url == Config.DEFAULT_API_URL
    finally:
        global_config._data = original_data
        global_config._sources = original_sources


def test_current_session_is_retained_with_deprecation_warning(monkeypatch):
    monkeypatch.setattr(global_config, '_data', {'current_session': 'legacy-session'})

    with pytest.warns(DeprecationWarning, match='current_session'):
        assert global_config.current_session == 'legacy-session'


def test_config_tracks_environment_and_file_sources(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        "[crucible]\n"
        "api_key = test\n"
        "current_project = saved-project\n"
    )
    monkeypatch.setattr(
        Config,
        "config_file_path",
        property(lambda self: config_file),
    )
    monkeypatch.delenv("CRUCIBLE_CURRENT_PROJECT", raising=False)

    config = Config()

    assert config.current_project == "saved-project"
    assert config.source("current_project") == "config file"

    monkeypatch.setenv("CRUCIBLE_CURRENT_PROJECT", "environment-project")
    config.reload()

    assert config.current_project == "environment-project"
    assert config.source("current_project") == "environment"
