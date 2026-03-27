#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument subcommand for Crucible CLI.

Provides instrument-related operations: list, get.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term
from ..config import config as _config

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def register_subcommand(subparsers):
    """
    Register the instrument subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'instrument',
        help='Instrument operations (list, get, create)',
        description='Manage Crucible instruments',
    )

    # Instrument subcommands
    instrument_subparsers = parser.add_subparsers(
        title='instrument commands',
        dest='instrument_command',
        help='Available instrument operations'
    )

    # Register individual instrument commands
    _register_list(instrument_subparsers)
    _register_get(instrument_subparsers)
    _register_create(instrument_subparsers)


def _register_list(subparsers):
    """Register the 'instrument list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List instruments',
        description='List all available instruments'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=_config.default_limit,
        metavar='N',
        help=f'Maximum number of results to return (default: {_config.default_limit})'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'instrument get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get instrument by name or ID',
        description='Retrieve instrument information'
    )

    instrument_arg = parser.add_argument(
        'instrument',
        metavar='NAME_OR_ID',
        help='Instrument name or unique ID'
    )
    # Disable file completion for instrument name/ID
    if ARGCOMPLETE_AVAILABLE:
        instrument_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--by-id',
        action='store_true',
        help='Treat argument as instrument ID instead of name'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'instrument create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new instrument',
        description='Register a new instrument in Crucible (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible instrument create

    # Command-line mode
    crucible instrument create -n "titan" --owner "mf" --location "Building 67"
    crucible instrument create -n "titan" --owner "mf" --location "Building 67" \\
        --manufacturer "FEI" --model "Titan 80-300" --type "TEM"
"""
    )

    parser.add_argument(
        '-n', '--name',
        dest='instrument_name',
        metavar='NAME',
        help='Instrument name. If not provided, will prompt interactively.'
    )
    parser.add_argument(
        '--owner',
        metavar='OWNER',
        help='Instrument owner. If not provided, will prompt interactively.'
    )
    parser.add_argument(
        '--location',
        metavar='LOCATION',
        help='Instrument location. If not provided, will prompt interactively.'
    )
    parser.add_argument(
        '--manufacturer',
        metavar='MANUFACTURER',
        help='Instrument manufacturer (optional)'
    )
    parser.add_argument(
        '--model',
        metavar='MODEL',
        help='Instrument model (optional)'
    )
    parser.add_argument(
        '--type',
        dest='instrument_type',
        metavar='TYPE',
        help='Instrument type (optional)'
    )
    parser.add_argument(
        '--description',
        metavar='TEXT',
        help='Instrument description (optional)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_create)


def _execute_create(args):
    """Execute the 'instrument create' subcommand."""
    from crucible.client import CrucibleClient

    instrument_name = args.instrument_name
    owner = args.owner
    location = args.location

    interactive = instrument_name is None or owner is None or location is None
    if interactive:
        term.header("Create Instrument")
        print("")

    if instrument_name is None:
        while True:
            instrument_name = input("Instrument name: ").strip()
            if instrument_name:
                break
            logger.error("Instrument name is required.")

    if owner is None:
        while True:
            owner = input("Owner: ").strip()
            if owner:
                break
            logger.error("Owner is required.")

    if location is None:
        while True:
            location = input("Location: ").strip()
            if location:
                break
            logger.error("Location is required.")

    manufacturer = args.manufacturer
    model = args.model
    instrument_type = args.instrument_type
    description = args.description

    if interactive:
        if manufacturer is None:
            val = input("Manufacturer (optional, press Enter to skip): ").strip()
            manufacturer = val or None
        if model is None:
            val = input("Model (optional, press Enter to skip): ").strip()
            model = val or None
        if instrument_type is None:
            val = input("Type (optional, press Enter to skip): ").strip()
            instrument_type = val or None
        if description is None:
            val = input("Description (optional, press Enter to skip): ").strip()
            description = val or None

    try:
        from crucible.models import Instrument
        client = CrucibleClient()

        instrument = Instrument(
            instrument_name=instrument_name,
            owner=owner,
            location=location,
            manufacturer=manufacturer,
            model=model,
            instrument_type=instrument_type,
            description=description,
        )

        result = client.instruments.create(instrument)

        logger.info("✓ Instrument created")
        _show_instrument(result)

    except Exception as e:
        logger.error(f"Error creating instrument: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list(args):
    """Execute the 'instrument list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        instruments = client.instruments.list(limit=args.limit)

        term.header(f"Instruments ({len(instruments)})")
        if not instruments:
            print(f"  {term.dim('No instruments found.')}")
        else:
            rows = [
                (
                    i.get('instrument_name') or '—',
                    i.get('unique_id') or '—',
                    i.get('owner') or '—',
                    i.get('location') or '—',
                )
                for i in instruments
            ]
            term.table(rows, ['Name', 'MFID', 'Owner', 'Location'],
                       max_widths=[20, 26, 15, 25])

    except Exception as e:
        logger.error(f"Error listing instruments: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _show_instrument(instrument):
    """Display instrument fields."""
    W = 14

    def _p(label, value):
        print(f"  {label:<{W}}{value if value not in (None, '') else '—'}")

    term.header("Instrument")
    uid = instrument.get('unique_id')
    _p("Name",         instrument.get('instrument_name'))
    _p("MFID",         term.cyan(uid) if uid else None)
    _p("ID",           instrument.get('id'))
    _p("Type",         instrument.get('instrument_type'))
    _p("Manufacturer", instrument.get('manufacturer'))
    _p("Model",        instrument.get('model'))
    _p("Owner",        instrument.get('owner'))
    _p("Location",     instrument.get('location'))
    _p("Description",  instrument.get('description'))
    if instrument.get('other_id'):
        _p("Other ID",     f"{instrument['other_id']}  ({instrument.get('other_id_source', '')})")


def _execute_get(args):
    """Execute the 'instrument get' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()

        if args.by_id:
            instrument = client.instruments.get(instrument_id=args.instrument)
        else:
            instrument = client.instruments.get(instrument_name=args.instrument)

        if instrument is None:
            logger.error(f"Instrument not found: {args.instrument}")
            sys.exit(1)

        _show_instrument(instrument)

    except Exception as e:
        logger.error(f"Error retrieving instrument: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
