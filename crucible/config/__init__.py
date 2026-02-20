"""
Crucible Configuration Module

Provides configuration management for pycrucible API access.
"""

from .config import (
    config,
    Config,
    get_crucible_api_key,
    get_api_url,
    get_cache_dir,
    get_orcid_id,
    get_client,
    create_config_file,
    get_config_file_path,
    get_graph_explorer_url,
    get_current_project,
)

__all__ = [
    "config",
    "Config",
    "get_crucible_api_key",
    "get_api_url",
    "get_cache_dir",
    "get_orcid_id",
    "get_client",
    "create_config_file",
    "get_config_file_path",
    "get_graph_explorer_url",
    "get_current_project",
]
