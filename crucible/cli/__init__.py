#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crucible CLI - Unified command-line interface for Crucible operations.

Available subcommands:
    config      Manage pycrucible configuration
    upload      Parse and upload datasets to Crucible
    open        Open resources in Crucible Graph Explorer
    link        Link resources (datasets, samples)
    completion  Install shell autocomplete
"""

import argparse
import sys
import logging
from crucible import __version__

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def setup_logging(verbose=False):
    """
    Configure logging for CLI usage.

    Args:
        verbose (bool): If True, set level to DEBUG; otherwise INFO
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(message)s',  # Clean output for CLI
        handlers=[
            logging.StreamHandler(sys.stderr)  # Standard for CLI tools
        ]
    )


def main():
    """Main entry point for the unified Crucible CLI."""
    parser = argparse.ArgumentParser(
        prog='crucible',
        description='Crucible API command-line interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Resource commands:
    dataset     Dataset operations (list, get, create, update-metadata, link)
    sample      Sample operations (list, get, create, link, link-dataset)
    project     Project operations (list, get, create)
    instrument  Instrument operations (list, get)
    user        User operations (get, create) - requires admin permissions

Utility commands:
    config      Manage configuration
    upload      [Legacy] Parse and upload datasets (use 'dataset create' instead)
    open        Open a resource in Crucible Graph Explorer
    link        Link resources directly
    completion  Install shell autocomplete

Examples:
    # Configuration
    crucible config init

    # Dataset operations
    crucible dataset list -pid my-project
    crucible dataset get <dataset-id>
    crucible dataset create -i input.lmp -t lammps -pid my-project

    # Sample operations
    crucible sample list -pid my-project
    crucible sample create -n "My Sample" -pid my-project

    # Project operations
    crucible project list
    crucible project get <project-id>

    # Other operations
    crucible open <mfid>
    crucible link -p parent_id -c child_id
"""
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
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
        upload, completion, config as config_cmd, open as open_cmd, link  # Utility commands
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

    # Enable shell completion if argcomplete is available
    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Execute the command
    # Each subcommand module should have added a 'func' attribute via set_defaults()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
