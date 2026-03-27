#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config subcommand for managing crucible configuration.

Manages API keys, URLs, cache directories, and ORCID IDs.
"""

import sys
import os
import logging
import subprocess
from pathlib import Path

from . import term

logger = logging.getLogger(__name__)

#%%

def get_default_editor():
    """Get the best available editor for the current platform."""
    import shutil
    from crucible.config import config as _cfg

    # Priority: crucible config > $VISUAL > $EDITOR > platform defaults
    editor = _cfg.editor or os.environ.get('VISUAL') or os.environ.get('EDITOR')
    if editor:
        return editor

    if sys.platform == 'win32':
        # Try common Windows editors in order of preference
        candidates = ['code', 'notepad++', 'notepad']
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        return 'notepad'  # notepad is always available on Windows

    elif sys.platform == 'darwin':
        candidates = ['code', 'nano', 'vim', 'vi']
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        return 'nano'

    else:  # Linux and other Unix-like
        candidates = ['code', 'nano', 'vim', 'vi', 'gedit', 'kate']
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        return 'vi'  # vi is POSIX-guaranteed

def register_subcommand(subparsers):
    """Register the config subcommand."""
    parser = subparsers.add_parser(
        'config',
        help='Manage crucible configuration',
        description='View and modify crucible configuration settings',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Interactive setup wizard
    crucible config init

    # Show all configuration
    crucible config show

    # Get a specific value
    crucible config get api_url

    # Set a value
    crucible config set api_key YOUR_API_KEY
    crucible config set read_timeout 120

    # Show config file location
    crucible config path

    # Edit config file directly
    crucible config edit

Configuration keys (by section):
  [crucible]  -- API connection
    api_key             Crucible API authentication key (required)
    api_url             Crucible API endpoint URL
    graph_explorer_url  Crucible Graph Explorer URL (optional)
    current_project     Default project ID (optional)

  [cache]
    cache_dir           Directory for caching downloaded data

  [display]  -- UI preferences
    editor              Preferred editor for interactive edit commands
    sample_group_by     Default group-by for 'sample list' (type, project)
    dataset_group_by    Default group-by for 'dataset list' (measurement, session, format, instrument)

  [network]  -- timeouts and pagination
    connect_timeout     TCP connect timeout in seconds (default 5)
    read_timeout        HTTP read timeout per request in seconds (default 30)
    default_limit       Maximum results for list/search commands (default 100)

Priority order (highest to lowest):
    1. Environment variables (CRUCIBLE_API_KEY, CRUCIBLE_READ_TIMEOUT, etc.)
    2. Config file (~/.config/nano-crucible/config.ini)
    3. Defaults
"""
    )

    subparsers_config = parser.add_subparsers(
        title='config commands',
        dest='config_command',
        help='Configuration operations'
    )

    # init - Interactive setup
    init_parser = subparsers_config.add_parser(
        'init',
        help='Interactive configuration setup'
    )
    init_parser.set_defaults(func=cmd_init)

    # show - Display all config
    show_parser = subparsers_config.add_parser(
        'show',
        help='Show current configuration'
    )
    show_parser.add_argument(
        '--secrets',
        action='store_true',
        help='Show API key (hidden by default)'
    )
    show_parser.set_defaults(func=cmd_show)

    # get - Get specific value
    get_parser = subparsers_config.add_parser(
        'get',
        help='Get a configuration value'
    )
    get_parser.add_argument(
        'key',
        choices=['api_key', 'api_url', 'graph_explorer_url', 'current_project',
                 'cache_dir',
                 'editor', 'sample_group_by', 'dataset_group_by',
                 'connect_timeout', 'read_timeout', 'default_limit'],
        help='Configuration key to retrieve'
    )
    get_parser.set_defaults(func=cmd_get)

    # set - Set a value
    set_parser = subparsers_config.add_parser(
        'set',
        help='Set a configuration value'
    )
    set_parser.add_argument(
        'key',
        choices=['api_key', 'api_url', 'graph_explorer_url', 'current_project',
                 'cache_dir',
                 'editor', 'sample_group_by', 'dataset_group_by',
                 'connect_timeout', 'read_timeout', 'default_limit'],
        help='Configuration key to set'
    )
    set_parser.add_argument(
        'value',
        help='Value to set'
    )
    set_parser.set_defaults(func=cmd_set)

    # path - Show config file location
    path_parser = subparsers_config.add_parser(
        'path',
        help='Show configuration file path'
    )
    path_parser.set_defaults(func=cmd_path)

    # edit - Open config file in editor
    edit_parser = subparsers_config.add_parser(
        'edit',
        help='Edit configuration file'
    )
    edit_parser.set_defaults(func=cmd_edit)

    # If no subcommand provided, show help
    parser.set_defaults(func=lambda args: parser.print_help())


def cmd_init(args):
    """Interactive configuration wizard."""
    from crucible.config import create_config_file, config

    term.header("Crucible Configuration Setup")
    print("")
    print("  This wizard will help you configure nano-crucible.\n")

    # Check if config exists
    config_file = config.config_file_path
    if config_file.exists():
        print(f"Configuration file already exists: {config_file}")
        response = input("Overwrite it? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("Cancelled.")
            return

    # Get API key
    print("\n1. Crucible API Key (required)")
    print("   Get your key from: https://crucible.lbl.gov/api/v1/user_apikey")
    api_key = input("   API Key: ").strip()
    if not api_key:
        print("Error: API key is required")
        sys.exit(1)

    # Get API URL
    print("\n2. Crucible API URL (optional)")
    print("   Press Enter to use default: https://crucible.lbl.gov/api/v1")
    api_url = input("   API URL: ").strip()
    if not api_url:
        api_url = None

    # Get cache directory
    print("\n3. Cache Directory (optional)")
    print(f"   Press Enter to use default: {config.cache_dir}")
    cache_dir = input("   Cache Dir: ").strip()
    if not cache_dir:
        cache_dir = None

    # Get Graph Explorer URL
    print("\n4. Graph Explorer URL (optional)")
    print("   Press Enter to use default: https://crucible-graph-explorer-776258882599.us-central1.run.app")
    graph_explorer_url = input("   Graph Explorer URL: ").strip()
    if not graph_explorer_url:
        graph_explorer_url = None

    # Get current project
    print("\n5. Default Project ID (optional)")
    print("   Project ID to use when -pid is not specified")
    current_project = input("   Project ID: ").strip()
    if not current_project:
        current_project = None

    # Create config file
    try:
        created_path = create_config_file(
            api_key=api_key,
            api_url=api_url,
            cache_dir=cache_dir,
            graph_explorer_url=graph_explorer_url,
            current_project=current_project
        )
        print(f"\n✓ Configuration saved to: {created_path}")
        print("\nYou can now use crucible commands!")
        print("Example: crucible upload -i input.lmp -t lammps -pid my-project")
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        sys.exit(1)


def cmd_show(args):
    """Show current configuration."""
    from crucible.config import config

    W = 22
    def _p(label, value):
        print(f"  {label:<{W}}{value if value not in (None, '') else '—'}")

    term.header("Configuration")

    cfg_path = config.config_file_path
    exists = cfg_path.exists()
    _p("Config file", cfg_path)
    _p("Exists",      "Yes" if exists else "No")

    # [crucible] — API connection
    term.subheader("[crucible]  API connection")
    try:
        api_key = config.api_key
        masked = f"{'*' * 8}…{api_key[-4:]}" if not args.secrets else api_key
        _p("api_key",           masked)
    except ValueError:
        _p("api_key",           None)
    _p("api_url",              config.api_url)
    _p("graph_explorer_url",   config.graph_explorer_url)
    _p("current_project",      config.current_project)

    # [cache]
    term.subheader("[cache]")
    _p("cache_dir",            config.cache_dir)

    # [display] — UI preferences
    term.subheader("[display]  UI preferences")
    _p("editor",               config.editor)
    _p("sample_group_by",      config.sample_group_by)
    _p("dataset_group_by",     config.dataset_group_by)

    # [network] — timeouts and pagination
    term.subheader("[network]  timeouts / pagination")
    _p("connect_timeout",      config.connect_timeout)
    _p("read_timeout",         config.read_timeout)
    _p("default_limit",        config.default_limit)

    from crucible.config.config import Config
    env_overrides = {
        mapping['env']: os.environ.get(mapping['env'])
        for mapping in Config._CONFIG_MAP.values()
    }
    active = {k: v for k, v in env_overrides.items() if v is not None}
    if active:
        term.subheader("Environment overrides")
        for env_key, value in active.items():
            display = f"{'*' * 8}…{value[-4:]}" if 'API_KEY' in env_key and not args.secrets else value
            print(f"  {env_key}  {display}")


def cmd_get(args):
    """Get a specific configuration value."""
    from crucible.config import config

    key = args.key

    try:
        if key == 'api_key':
            value = config.api_key
        elif key == 'api_url':
            value = config.api_url
        elif key == 'cache_dir':
            value = config.cache_dir
        elif key == 'graph_explorer_url':
            value = config.graph_explorer_url
        elif key == 'current_project':
            value = config.current_project
        elif key == 'editor':
            value = config.editor
        elif key == 'sample_group_by':
            value = config.sample_group_by
        elif key == 'dataset_group_by':
            value = config.dataset_group_by
        elif key == 'connect_timeout':
            value = config.connect_timeout
        elif key == 'read_timeout':
            value = config.read_timeout
        elif key == 'default_limit':
            value = config.default_limit
        else:
            logger.error(f"Unknown config key: {key}")
            sys.exit(1)

        if value is None:
            print(f"{key}: <not set>")
        else:
            print(value)

    except ValueError as e:
        logger.error(f"{e}")
        sys.exit(1)


def cmd_set(args):
    """Set a configuration value, preserving comments."""
    import configparser
    from crucible.config import config
    from crucible.config.config import Config

    key = args.key
    value = args.value

    # Determine the correct INI section for this key
    mapping = Config._CONFIG_MAP[key]
    section  = mapping['section']
    ini_key  = mapping['ini']

    # Load or create config file
    config_file = config.config_file_path
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Trick: Set comment_prefixes to something extremely unlikely (like '~~~')
    # This makes # and ; lines be treated as keys without values instead of comments
    # Combined with allow_no_value=True, comments are preserved when writing!
    parser = configparser.ConfigParser(comment_prefixes=('~~~',), allow_no_value=True)

    if config_file.exists():
        parser.read(config_file)

    # Ensure the target section exists (and also [crucible] for legacy compat)
    if 'crucible' not in parser:
        parser['crucible'] = {}
    if section not in parser:
        parser[section] = {}

    # If this key exists in the legacy [crucible] section under a different
    # section now, remove it there to avoid duplicate resolution confusion.
    if section != 'crucible' and 'crucible' in parser and ini_key in parser['crucible']:
        del parser['crucible'][ini_key]

    parser[section][ini_key] = value

    # Write back (comments preserved!)
    with open(config_file, 'w') as f:
        parser.write(f)

    # Reload config
    config.reload()

    print(f"✓ Set {key} = {value}  (in [{section}])")
    print(f"✓ Saved to {config_file}")


def cmd_path(args):
    """Show configuration file path."""
    from crucible.config import config

    config_file = config.config_file_path
    print(config_file)

    if config_file.exists():
        print(f"(exists, {config_file.stat().st_size} bytes)")
    else:
        print("(does not exist yet)")
        print(f"\nCreate it with: crucible config init")


def cmd_edit(args):
    """Open config file in editor."""
    from crucible.config import config

    config_file = config.config_file_path

    if not config_file.exists():
        print(f"Config file does not exist: {config_file}")
        print("Create it first with: crucible config init")
        sys.exit(1)

    editor = get_default_editor()
    parts = editor.split()
    editor_bin = os.path.basename(parts[0])
    extra = [f for f in term._GUI_EDITOR_WAIT_FLAGS.get(editor_bin, []) if f not in parts]
    cmd = parts + extra

    print(f"Opening {config_file} with {' '.join(cmd)}...")

    try:
        subprocess.run(cmd + [str(config_file)], check=True)
        print("\n✓ Config file updated")
        config.reload()
        print("✓ Configuration reloaded")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error editing file: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error(f"Editor not found: {editor}")
        logger.error("Set your editor with: crucible config set editor vim")
        sys.exit(1)