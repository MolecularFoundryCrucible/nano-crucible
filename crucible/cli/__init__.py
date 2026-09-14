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
    ('dataset', 'publish'):         'set-public',
    ('dataset', 'unpublish'):       'set-private',
    ('sample', 'publish'):          'set-public',
    ('sample', 'unpublish'):        'set-private',
    ('project', 'publish'):         'set-public',
    ('project', 'unpublish'):       'set-private',
    ('instrument', 'publish'):      'set-public',
    ('instrument', 'unpublish'):    'set-private',
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
        warning = term.yellow('Warning:', stream=sys.stderr)
        print(f"{warning} '{resource} {args[sub_idx]}' is deprecated, "
              f"use '{resource} {new_name}' instead.", file=sys.stderr)
        args[sub_idx] = new_name
    return args

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


import re as _re
from . import term

_RETRY_TOTAL_RE  = _re.compile(r'Retry\(total=(\d+)')
_RETRY_REASON_RE = _re.compile(r"'(\w*Error)[:(]")

class _CleanRetryFilter(logging.Filter):
    """Reformat urllib3 retry warnings into a single readable line."""

    _REASONS = {
        'ReadTimeoutError':    'timed out',
        'ConnectTimeoutError': 'connection timed out',
        'NewConnectionError':  'could not connect',
        'ConnectionError':     'connection error',
        'ProtocolError':       'protocol error',
    }

    def filter(self, record):
        msg = record.getMessage()
        if 'Retrying' not in msg:
            return True
        m_total  = _RETRY_TOTAL_RE.search(msg)
        m_reason = _RETRY_REASON_RE.search(msg)
        remaining = m_total.group(1)  if m_total  else '?'
        reason    = self._REASONS.get(m_reason.group(1) if m_reason else '', 'error')
        record.msg  = f'  ↻  {reason.capitalize()} — retrying ({remaining} left)'
        record.args = ()
        return True


class _CliFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        if record.levelno >= logging.ERROR:
            if message.startswith('Error:'):
                message = message[6:].lstrip()
            return f"{term.red('Error:', stream=sys.stderr)} {message}"
        if record.levelno >= logging.WARNING:
            if message.startswith('Warning:'):
                message = message[8:].lstrip()
            return f"{term.yellow('Warning:', stream=sys.stderr)} {message}"
        return message


def setup_logging(debug=False):
    """
    Configure logging for CLI usage.

    Args:
        debug (bool): If True (--debug flag), set level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()

    if not root.handlers:
        # First call — set up the handler from scratch.
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_CliFormatter('%(message)s'))
        handler.addFilter(_CleanRetryFilter())
        root.addHandler(handler)

    # Root logger stays at INFO so third-party libraries (asyncio, urllib3, …)
    # don't flood output with their own DEBUG messages.
    # The handler is set to DEBUG so it doesn't filter crucible's debug records.
    root.setLevel(logging.INFO)
    for h in root.handlers:
        h.setLevel(logging.DEBUG)
        if not any(isinstance(f, _CleanRetryFilter) for f in h.filters):
            h.addFilter(_CleanRetryFilter())

    # Only the crucible logger switches between INFO and DEBUG.
    logging.getLogger('crucible').setLevel(level)


def main():
    """Main entry point for the unified Crucible CLI."""
    parser = argparse.ArgumentParser(
        prog='crucible',
        description='Crucible API command-line interface',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Configuration
    crucible config init

    # Dataset operations
    crucible dataset list --project-id my-project
    crucible dataset get <dataset-id>
    crucible dataset create -i data.csv --project-id my-project
    crucible dataset update <dataset-id> --set measurement=XRD
    crucible dataset update <dataset-id> --metadata '{"temperature": 300}'

    # Sample operations
    crucible sample list --project-id my-project
    crucible sample create -n "My Sample" --project-id my-project
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

    parser.add_argument(
        '--no-color',
        action='store_true',
        default=False,
        help='Disable ANSI colors while retaining interactive terminal hyperlinks'
    )

    # Subcommand parsers
    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        help='Available commands'
    )

    # Import subcommands
    from . import (
        dataset, sample, project, instrument, user, file as file_cmd, ingestion,  # Resource commands
        service_account, access_group,
        upload, completion, config as config_cmd, open as open_cmd, link, unlink, whoami, account, cache, download, get, edit, status, deletion, tree, cast, qr  # Utility commands
    )

    # Register resource commands (new structure)
    dataset.register_subcommand(subparsers)
    sample.register_subcommand(subparsers)
    project.register_subcommand(subparsers)
    instrument.register_subcommand(subparsers)
    user.register_subcommand(subparsers)
    file_cmd.register_subcommand(subparsers)
    ingestion.register_subcommand(subparsers)
    service_account.register_subcommand(subparsers)
    access_group.register_subcommand(subparsers)

    # Register utility commands (backward compatibility)
    upload.register_subcommand(subparsers)
    completion.register_subcommand(subparsers)
    config_cmd.register_subcommand(subparsers)
    open_cmd.register_subcommand(subparsers)
    link.register_subcommand(subparsers)
    unlink.register_subcommand(subparsers)
    whoami.register_subcommand(subparsers)
    account.register_subcommand(subparsers)
    cache.register_subcommand(subparsers)
    download.register_subcommand(subparsers)
    get.register_subcommand(subparsers)
    edit.register_subcommand(subparsers)
    status.register_subcommand(subparsers)
    deletion.register_subcommand(subparsers)
    tree.register_subcommand(subparsers)
    cast.register_subcommand(subparsers)
    qr.register_subcommand(subparsers)

    # Enable shell completion if argcomplete is available
    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    # Remap deprecated subcommand names before parsing
    raw_argv = sys.argv[1:]
    term.configure_color('--no-color' not in raw_argv)
    from .helpers import install_warning_formatter
    install_warning_formatter()
    argv = _remap_deprecated(raw_argv)

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
