#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument subcommand for Crucible CLI.

Provides instrument-related operations: list, get.
"""

import sys
import logging

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
        logger.info("\n=== Interactive Instrument Creation ===")
        logger.info("Please provide the following information:\n")

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

        logger.info("\n=== Creating Instrument ===")
        result = client.instruments.create(instrument)

        logger.info(f"\n✓ Instrument created successfully!")
        logger.info(f"Name:     {result.get('instrument_name', 'N/A')}")
        if result.get('unique_id'):
            logger.info(f"ID:       {result['unique_id']}")
        logger.info(f"Owner:    {result.get('owner', 'N/A')}")
        logger.info(f"Location: {result.get('location', 'N/A')}")
        if result.get('manufacturer'):
            logger.info(f"Manufacturer: {result['manufacturer']}")
        if result.get('model'):
            logger.info(f"Model:    {result['model']}")
        if result.get('instrument_type'):
            logger.info(f"Type:     {result['instrument_type']}")

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
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


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

    except Exception as e:
        logger.error(f"Error retrieving instrument: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
