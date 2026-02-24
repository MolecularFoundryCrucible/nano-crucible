#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument subcommand for Crucible CLI.

Provides instrument-related operations: list, get.
"""

import sys
import logging
import json

logger = logging.getLogger(__name__)

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
        help='Instrument operations (list, get)',
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
        default=100,
        metavar='N',
        help='Maximum number of results to return (default: 100)'
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


def _execute_list(args):
    """Execute the 'instrument list' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        instruments = client.instruments.list(limit=args.limit)

        logger.info(f"\n=== Instruments ===")
        logger.info(f"Found {len(instruments)} instrument(s)\n")

        if instruments:
            for instrument in instruments:
                logger.info(f"Name: {instrument.get('instrument_name', 'N/A')}")
                if instrument.get('id'):
                    logger.info(f"  ID: {instrument['id']}")
                if instrument.get('unique_id'):
                    logger.info(f"  Unique ID: {instrument['unique_id']}")
                if instrument.get('location'):
                    logger.info(f"  Location: {instrument['location']}")
                if instrument.get('owner'):
                    logger.info(f"  Owner: {instrument['owner']}")
                logger.info("")

    except Exception as e:
        logger.error(f"Error listing instruments: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'instrument get' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()

        if args.by_id:
            instrument = client.instruments.get(instrument_id=args.instrument)
        else:
            instrument = client.instruments.get(instrument_name=args.instrument)

        if instrument is None:
            logger.error(f"Instrument not found: {args.instrument}")
            sys.exit(1)

        logger.info("\n=== Instrument Information ===")
        logger.info(f"Name: {instrument.get('instrument_name', 'N/A')}")
        if instrument.get('id'):
            logger.info(f"ID: {instrument['id']}")
        if instrument.get('unique_id'):
            logger.info(f"Unique ID: {instrument['unique_id']}")
        if instrument.get('location'):
            logger.info(f"Location: {instrument['location']}")
        if instrument.get('owner'):
            logger.info(f"Owner: {instrument['owner']}")

        if args.verbose:
            logger.debug(f"\nFull instrument data: {json.dumps(instrument, indent=2)}")

    except Exception as e:
        logger.error(f"Error retrieving instrument: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
