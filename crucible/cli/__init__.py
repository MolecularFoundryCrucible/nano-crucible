#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crucible CLI - Unified command-line interface for Crucible operations.

Available subcommands:
    config      Manage crucible configuration
    upload      Parse and upload datasets to Crucible
    open        Open resources in Crucible Graph Explorer
    link        Link resources (datasets, samples)
    completion  Install shell autocomplete
"""

import argparse
import sys
import logging
from crucible import __version__

# Deprecated subcommand aliases: (resource, old_name) -> new_name
_DEPRECATED_SUBCOMMANDS = {
    ('dataset', 'update-metadata'): 'update',
    ('dataset', 'get-keywords'):    'list-keywords',
    ('sample',  'link-dataset'):    'add-dataset',   # note: args changed to: SAMPLE_ID -d DATASET_ID
    ('user',    'get-access-groups'): 'list-access-groups',
    ('user',    'get-projects'):    'list-projects',
    ('project', 'get-users'):       'list-users',
}


def _remap_deprecated(argv):
    """Remap deprecated subcommand names, warning the user."""
    args = list(argv)
    # Find the resource command (first non-flag arg)
    resource_idx = next((i for i, a in enumerate(args) if not a.startswith('-')), None)
    if resource_idx is None:
        return args
    resource = args[resource_idx]
    # Find the subcommand (first non-flag arg after resource)
    sub_idx = next((i for i, a in enumerate(args[resource_idx+1:], resource_idx+1)
                    if not a.startswith('-')), None)
    if sub_idx is None:
        return args
    key = (resource, args[sub_idx])
    if key in _DEPRECATED_SUBCOMMANDS:
        new_name = _DEPRECATED_SUBCOMMANDS[key]
        print(f"Warning: '{resource} {args[sub_idx]}' is deprecated, "
              f"use '{resource} {new_name}' instead.", file=sys.stderr)
        args[sub_idx] = new_name
    return args

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def setup_logging(debug=False):
    """
    Configure logging for CLI usage.

    Args:
        debug (bool): If True (--debug flag), set level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(message)s',  # Clean output for CLI
        handlers=[
            logging.StreamHandler(sys.stderr)  # Standard for CLI tools
        ]
    )
    # The crucible package logger has an explicit INFO level set at import time;
    # override it so --debug reaches crucible.client and other submodules.
    logging.getLogger('crucible').setLevel(level)


def main():
    """Main entry point for the unified Crucible CLI."""
    parser = argparse.ArgumentParser(
        prog='crucible',
        description='Crucible API command-line interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Configuration
    crucible config init

    # Dataset operations
    crucible dataset list -pid my-project
    crucible dataset get <dataset-id>
    crucible dataset create -i data.csv -pid my-project
    crucible dataset update <dataset-id> --set measurement=XRD
    crucible dataset update <dataset-id> --metadata '{"temperature": 300}'

    # Sample operations
    crucible sample list -pid my-project
    crucible sample create -n "My Sample" -pid my-project
    crucible sample update <sample-id> --set sample_type=substrate

    # Project / instrument / user operations
    crucible project list
    crucible instrument list
    crucible user get <orcid>

    # Debug mode (place before subcommand)
    crucible --debug dataset list
"""
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable debug logging (HTTP calls, raw API responses, tracebacks)'
    )

    # Subcommand parsers
    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        help='Available commands'
    )

    # Import subcommands
    from . import (
        dataset, sample, project, instrument, user,  # Resource commands
        upload, completion, config as config_cmd, open as open_cmd, link, unlink, whoami, cache, download, get, edit  # Utility commands
    )

    # Register resource commands (new structure)
    dataset.register_subcommand(subparsers)
    sample.register_subcommand(subparsers)
    project.register_subcommand(subparsers)
    instrument.register_subcommand(subparsers)
    user.register_subcommand(subparsers)

    # Register utility commands (backward compatibility)
    upload.register_subcommand(subparsers)
    completion.register_subcommand(subparsers)
    config_cmd.register_subcommand(subparsers)
    open_cmd.register_subcommand(subparsers)
    link.register_subcommand(subparsers)
    unlink.register_subcommand(subparsers)
    whoami.register_subcommand(subparsers)
    cache.register_subcommand(subparsers)
    download.register_subcommand(subparsers)
    get.register_subcommand(subparsers)
    edit.register_subcommand(subparsers)

    # Enable shell completion if argcomplete is available
    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    # Remap deprecated subcommand names before parsing
    argv = _remap_deprecated(sys.argv[1:])

    # Parse arguments
    args = parser.parse_args(argv)

    # Configure logging once for the entire CLI
    setup_logging(debug=getattr(args, 'debug', False))

    # If no command specified, start interactive shell
    if args.command is None:
        from .shell import run as _run_shell
        _run_shell(parser)
        return

    # Execute the command
    # Each subcommand module should have added a 'func' attribute via set_defaults()
    try:
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)


if __name__ == '__main__':
    main()
