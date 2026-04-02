#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crucible Configuration Management

Loads Crucible API keys and configuration from:
1. Environment variables (highest priority)
2. INI config file in user config directory
"""

import os
import logging
import configparser
from pathlib import Path
from platformdirs import user_config_dir, user_cache_dir

# Set up logger for this module
logger = logging.getLogger(__name__)

class Config:
    """
    Configuration manager for nano-crucible.

    Loads configuration from environment variables and config file,
    providing a clean interface for accessing settings.
    """

    # Mapping of config keys to their environment variable names, INI keys, and INI section.
    # Keys are read from their designated section first; if not found there, the legacy
    # flat [crucible] section is checked so that old config files keep working.
    _CONFIG_MAP = {
        # [crucible] – API connection
        'api_key':            {'env': 'CRUCIBLE_API_KEY',            'ini': 'api_key',            'section': 'crucible'},
        'api_url':            {'env': 'CRUCIBLE_API_URL',            'ini': 'api_url',            'section': 'crucible'},
        'graph_explorer_url': {'env': 'CRUCIBLE_GRAPH_EXPLORER_URL', 'ini': 'graph_explorer_url', 'section': 'crucible'},
        'current_project':    {'env': 'CRUCIBLE_CURRENT_PROJECT',    'ini': 'current_project',    'section': 'crucible'},
        'current_session':    {'env': 'CRUCIBLE_CURRENT_SESSION',    'ini': 'current_session',    'section': 'crucible'},
        # [cache]
        'cache_dir':          {'env': 'CRUCIBLE_CACHE_DIR',          'ini': 'cache_dir',          'section': 'cache'},
        # [display] – UI preferences
        'editor':             {'env': 'CRUCIBLE_EDITOR',             'ini': 'editor',             'section': 'display'},
        'sample_group_by':    {'env': 'CRUCIBLE_SAMPLE_GROUP_BY',    'ini': 'sample_group_by',    'section': 'display'},
        'dataset_group_by':   {'env': 'CRUCIBLE_DATASET_GROUP_BY',   'ini': 'dataset_group_by',   'section': 'display'},
        # [network] – timeouts and pagination
        'connect_timeout':    {'env': 'CRUCIBLE_CONNECT_TIMEOUT',    'ini': 'connect_timeout',    'section': 'network'},
        'read_timeout':       {'env': 'CRUCIBLE_READ_TIMEOUT',       'ini': 'read_timeout',       'section': 'network'},
        'default_limit':      {'env': 'CRUCIBLE_DEFAULT_LIMIT',      'ini': 'default_limit',      'section': 'network'},
    }

    def __init__(self):
        """Initialize and load configuration."""
        self._data = {}
        self._client = None
        self._load()

    def _load(self):
        """Load configuration from all available sources."""
        # 1. Load from environment variables (highest priority)
        for key, mapping in self._CONFIG_MAP.items():
            env_value = os.environ.get(mapping['env'])
            if env_value is not None:
                self._data[key] = env_value

        # 2. Load from INI config file
        config_file = self.config_file_path
        if config_file.exists():
            parser = configparser.ConfigParser()
            parser.read(config_file)

            for key, mapping in self._CONFIG_MAP.items():
                if key in self._data:
                    continue  # already set by env var

                ini_key = mapping['ini']
                section  = mapping['section']

                # Try the designated section first, then fall back to the legacy
                # flat [crucible] section so old config files keep working.
                value = None
                for sec in (section, 'crucible'):
                    if sec in parser and ini_key in parser[sec]:
                        value = parser[sec][ini_key].strip('"').strip("'")
                        break

                if value is not None:
                    self._data[key] = value

        return

    @property
    def config_file_path(self):
        """Get the path to the configuration file."""
        return Path(user_config_dir("nano-crucible")) / "config.ini"

    @property
    def api_key(self):
        """
        Get the Crucible API key.

        Returns:
            str: The API key

        Raises:
            ValueError: If no API key is found
        """
        key = self._data.get('api_key')
        if key is None:
            raise ValueError(
                f"Crucible API key not found. Please set it using one of these methods:\n"
                f"1. Environment variable: export CRUCIBLE_API_KEY='your_key_here'\n"
                f"2. Config file: Create {self.config_file_path} with:\n"
                f"   [crucible]\n"
                f"   api_key = your_key_here\n"
                f"\nUse create_config_file() to create the config file automatically:\n"
                f"from crucible.config import create_config_file\n"
                f"create_config_file('your_key_here')"
            )
        return key

    @property
    def api_url(self):
        """
        Get the Crucible API URL.

        Returns:
            str: The API URL (defaults to https://crucible.lbl.gov/api/v1)
        """
        return self._data.get('api_url', 'https://crucible.lbl.gov/api/v1')

    @property
    def cache_dir(self):
        """
        Get the cache directory path.

        Returns:
            Path: The cache directory path
        """
        cache_dir_str = self._data.get('cache_dir')

        if cache_dir_str is None:
            # Use default platform-specific cache directory
            cache_path = Path(user_cache_dir("nano-crucible"))
        else:
            # Expand ~ and convert to Path
            cache_path = Path(os.path.expanduser(cache_dir_str))

        # Ensure the cache directory exists
        cache_path.mkdir(parents=True, exist_ok=True)

        return cache_path

    @property
    def graph_explorer_url(self):
        """
        Get the Crucible Graph Explorer URL.

        Returns:
            str: The graph explorer URL
        """
        default_url = 'https://crucible-graph-explorer-776258882599.us-central1.run.app'
        return self._data.get('graph_explorer_url', default_url)

    @property
    def current_project(self):
        """
        Get the current/default project ID.

        Returns:
            str or None: The current project ID if configured, None otherwise
        """
        return self._data.get('current_project')

    @property
    def current_session(self):
        """
        Get the current/default session name.

        Returns:
            str or None: The current session name if configured, None otherwise
        """
        return self._data.get('current_session') or None

    @property
    def editor(self):
        """
        Get the preferred editor for interactive editing commands.

        Priority: CRUCIBLE_EDITOR env var > config file > None.
        When None, open_editor_json falls back to $VISUAL, $EDITOR, then nano.

        Returns:
            str or None: Editor command (e.g. "code --wait", "gvim -f") or None
        """
        return self._data.get('editor')

    @property
    def sample_group_by(self):
        """Default group-by field for 'crucible sample list' (e.g. 'type', 'project')."""
        return self._data.get('sample_group_by')

    @property
    def dataset_group_by(self):
        """Default group-by field for 'crucible dataset list' (e.g. 'measurement', 'session')."""
        return self._data.get('dataset_group_by')

    @property
    def connect_timeout(self) -> int:
        """TCP connect timeout in seconds (default 5)."""
        raw = self._data.get('connect_timeout')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 5

    @property
    def read_timeout(self) -> int:
        """HTTP read timeout in seconds (default 30)."""
        raw = self._data.get('read_timeout')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 30

    @property
    def default_limit(self) -> int:
        """Default maximum results per list/search request (default 100)."""
        raw = self._data.get('default_limit')
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 100

    @property
    def client(self):
        """
        Get a configured CrucibleClient instance.

        Returns:
            CrucibleClient: Configured client instance
        """
        if self._client is None:
            # Import here to avoid circular imports
            from crucible import CrucibleClient
            self._client = CrucibleClient(self.api_url, self.api_key)
        return self._client

    def reload(self):
        """Reload configuration from all sources."""
        self._data.clear()
        self._client = None
        self._load()


# Global singleton config instance
config = Config()


# Helper functions
def get_crucible_api_key():
    """
    Get the Crucible API key from configuration.

    Priority order:
    1. CRUCIBLE_API_KEY environment variable
    2. api_key from ~/.config/nano-crucible/config.ini

    Returns:
        str: The API key

    Raises:
        ValueError: If no API key is found anywhere
    """
    return config.api_key


def get_api_url():
    """
    Get the Crucible API URL from configuration.

    Priority order:
    1. CRUCIBLE_API_URL environment variable
    2. api_url from ~/.config/nano-crucible/config.ini
    3. Default: https://crucible.lbl.gov/api/v1

    Returns:
        str: The API URL
    """
    return config.api_url


def get_cache_dir():
    """
    Get the cache directory for storing downloaded data.

    Priority order:
    1. CRUCIBLE_CACHE_DIR environment variable
    2. cache_dir from ~/.config/nano-crucible/config.ini
    3. Default: ~/.cache/nano-crucible/ (platform-specific)

    Returns:
        Path: The cache directory path
    """
    return config.cache_dir


def get_graph_explorer_url():
    """
    Get the Crucible Graph Explorer URL from configuration.

    Priority order:
    1. CRUCIBLE_GRAPH_EXPLORER_URL environment variable
    2. graph_explorer_url from ~/.config/nano-crucible/config.ini
    3. Default: https://crucible-graph-explorer-776258882599.us-central1.run.app

    Returns:
        str: The graph explorer URL
    """
    return config.graph_explorer_url


def get_current_project():
    """
    Get the current/default project ID from configuration.

    Priority order:
    1. CRUCIBLE_CURRENT_PROJECT environment variable
    2. current_project from ~/.config/nano-crucible/config.ini
    3. None if not configured

    Returns:
        str or None: The current project ID if configured, None otherwise
    """
    return config.current_project


def get_client():
    """
    Get a configured CrucibleClient instance.

    Returns:
        CrucibleClient: Configured client instance

    Raises:
        ValueError: If API key is not configured
    """
    return config.client


def create_config_file(api_key, api_url=None, cache_dir=None,
                       graph_explorer_url=None, current_project=None,
                       editor=None, connect_timeout=None, read_timeout=None,
                       default_limit=None, **kwargs):
    """
    Create a configuration file with the given API key and optional settings.

    The file uses four INI sections:
      [crucible]  – API connection settings
      [cache]     – cache directory
      [display]   – UI preferences (editor, group-by defaults)
      [network]   – request timeouts

    Old single-section [crucible] files are still read correctly — the loader
    falls back to [crucible] for any key not found in its designated section.

    Args:
        api_key (str): The API key to store
        api_url (str, optional): Custom API URL
        cache_dir (str, optional): Custom cache directory path
        graph_explorer_url (str, optional): Graph Explorer URL
        current_project (str, optional): Default project ID
        editor (str, optional): Preferred editor command
        connect_timeout (int, optional): TCP connect timeout in seconds
        read_timeout (int, optional): HTTP read timeout in seconds
        **kwargs: Additional key=value pairs written to [crucible]

    Returns:
        Path: Path to the created config file
    """
    config_dir = Path(user_config_dir("nano-crucible"))
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.ini"

    default_api_url             = 'https://crucible.lbl.gov/api/v1'
    default_cache_dir           = str(user_cache_dir("nano-crucible"))
    default_graph_explorer_url  = 'https://crucible-graph-explorer-776258882599.us-central1.run.app'

    with open(config_file, 'w') as f:

        # ── [crucible] ───────────────────────────────────────────────────────
        f.write("[crucible]\n")
        f.write("# Crucible API authentication key (required)\n")
        f.write(f"api_key = {api_key}\n\n")

        f.write("# Crucible API endpoint URL\n")
        f.write(f"api_url = {api_url or default_api_url}\n\n")

        f.write("# Crucible Graph Explorer URL\n")
        f.write(f"graph_explorer_url = {graph_explorer_url or default_graph_explorer_url}\n\n")

        f.write("# Default project ID (leave commented out to prompt each time)\n")
        if current_project is not None:
            f.write(f"current_project = {current_project}\n")
        else:
            f.write("# current_project =\n")

        for key, value in kwargs.items():
            f.write(f"{key} = {value}\n")

        # ── [cache] ──────────────────────────────────────────────────────────
        f.write("\n[cache]\n")
        f.write("# Directory for caching downloaded data\n")
        f.write(f"cache_dir = {cache_dir or default_cache_dir}\n")

        # ── [display] ────────────────────────────────────────────────────────
        f.write("\n[display]\n")
        f.write("# Preferred editor for 'crucible dataset edit' / 'crucible sample edit'\n")
        f.write("# GUI editors receive their wait/foreground flag automatically (gvim, code, subl, …)\n")
        f.write("# but you can be explicit:  editor = gvim -f\n")
        if editor is not None:
            f.write(f"editor = {editor}\n")
        else:
            f.write("# editor =\n")
        f.write("\n")

        f.write("# Default group-by for 'crucible sample list'  (type, project)\n")
        f.write("# sample_group_by = type\n\n")

        f.write("# Default group-by for 'crucible dataset list'  (measurement, session, format, instrument)\n")
        f.write("# dataset_group_by = measurement\n")

        # ── [network] ────────────────────────────────────────────────────────
        f.write("\n[network]\n")
        f.write("# TCP connect timeout in seconds\n")
        if connect_timeout is not None:
            f.write(f"connect_timeout = {connect_timeout}\n")
        else:
            f.write("# connect_timeout = 5\n")
        f.write("\n")
        f.write("# HTTP read timeout per request in seconds\n")
        f.write("# Increase this when uploading large files over slow connections\n")
        if read_timeout is not None:
            f.write(f"read_timeout = {read_timeout}\n")
        else:
            f.write("# read_timeout = 30\n")
        f.write("\n")
        f.write("# Maximum number of results returned by list/search commands\n")
        if default_limit is not None:
            f.write(f"default_limit = {default_limit}\n")
        else:
            f.write("# default_limit = 100\n")

    logger.info(f"Created config file: {config_file}")

    # Reload the global config
    config.reload()

    return config_file


def get_config_file_path():
    """Get the path where the config file should be located."""
    return config.config_file_path
