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
    _register_update(instrument_subparsers)
    _register_edit(instrument_subparsers)


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
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in results'
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
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in output'
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
        formatter_class=term.ColorHelpFormatter,
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
        '--metadata',
        dest='metadata',
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
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

    metadata_dict = None
    if getattr(args, 'metadata', None):
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

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

        result = client.instruments.create(instrument, scientific_metadata=metadata_dict)

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
        instruments = client.instruments.list(limit=args.limit,
                                              include_metadata=getattr(args, 'include_metadata', False))

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


def _show_instrument(instrument, include_metadata=False):
    """Display instrument fields."""
    _p = term.field_printer(14)

    verbose = include_metadata  # reuse flag for verbose fields
    term.header("Instrument")
    uid = instrument.get('unique_id')
    _p("Name",         instrument.get('instrument_name'))
    _p("MFID",         term.cyan(uid) if uid else None)
    _p("Type",         instrument.get('instrument_type'))
    _p("Manufacturer", instrument.get('manufacturer'))
    _p("Model",        instrument.get('model'))
    _p("Owner",        instrument.get('owner'))
    _p("Location",     instrument.get('location'))
    _p("Description",  instrument.get('description'))
    if instrument.get('other_id'):
        _p("Other ID",     f"{instrument['other_id']}  ({instrument.get('other_id_source', '')})")
    if verbose:
        _p("Created",      instrument.get('creation_time'))
        _p("Modified",     instrument.get('modification_time'))
        from .helpers import show_scientific_metadata
        show_scientific_metadata(instrument.get('scientific_metadata'))


def _execute_get(args):
    """Execute the 'instrument get' subcommand."""
    from crucible.client import CrucibleClient
    include_metadata = getattr(args, 'include_metadata', False)
    try:
        client = CrucibleClient()

        if args.by_id:
            instrument = client.instruments.get(instrument_id=args.instrument,
                                                include_metadata=include_metadata)
        else:
            instrument = client.instruments.get(instrument_name=args.instrument,
                                                include_metadata=include_metadata)

        if instrument is None:
            logger.error(f"Instrument not found: {args.instrument}")
            sys.exit(1)

        _show_instrument(instrument, include_metadata=include_metadata)

    except Exception as e:
        logger.error(f"Error retrieving instrument: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_update(subparsers):
    """Register the 'instrument update' subcommand."""
    parser = subparsers.add_parser(
        'update',
        help='Update an instrument record or scientific metadata',
        description='Partially update an instrument record (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument update MFID001 --location "Building 67, Room 101"
    crucible instrument update MFID001 --owner "mf" --model "Titan 80-300"
    crucible instrument update MFID001 --metadata '{"voltage_kv": 300, "cs_mm": 1.2}'
    crucible instrument update MFID001 --metadata metadata.json
    crucible instrument update MFID001 --metadata metadata.json --overwrite
"""
    )
    uid_arg = parser.add_argument(
        'unique_id', metavar='MFID', help='Instrument unique ID (MFID)'
    )
    if ARGCOMPLETE_AVAILABLE:
        uid_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('--name',         dest='instrument_name',  metavar='NAME',  help='Instrument name')
    parser.add_argument('--owner',        dest='owner',            metavar='OWNER', help='Instrument owner')
    parser.add_argument('--location',     dest='location',         metavar='LOC',   help='Instrument location')
    parser.add_argument('--manufacturer', dest='manufacturer',     metavar='MFR',   help='Manufacturer')
    parser.add_argument('--model',        dest='model',            metavar='MODEL', help='Model')
    parser.add_argument('--type',         dest='instrument_type',  metavar='TYPE',  help='Instrument type')
    parser.add_argument('--description',  dest='description',      metavar='TEXT',  help='Description')
    parser.add_argument('--metadata',     dest='metadata',         metavar='JSON',
                        help='Scientific metadata as JSON string or path to JSON file')
    parser.add_argument('--overwrite',    action='store_true',
                        help='Replace all existing scientific metadata instead of merging (only with --metadata)')
    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'instrument update' subcommand."""
    from crucible.client import CrucibleClient

    fields = {k: v for k, v in {
        'instrument_name': args.instrument_name,
        'owner':           args.owner,
        'location':        args.location,
        'manufacturer':    args.manufacturer,
        'model':           args.model,
        'instrument_type': args.instrument_type,
        'description':     args.description,
    }.items() if v is not None}

    has_metadata = bool(getattr(args, 'metadata', None))

    if not fields and not has_metadata:
        logger.error("No fields to update. Provide at least one of: --name, --owner, --location, --manufacturer, --model, --type, --description, --metadata")
        sys.exit(1)

    metadata_dict = None
    if has_metadata:
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

    try:
        client = CrucibleClient()

        if fields:
            result = client.instruments.update(args.unique_id, **fields)
            logger.info("✓ Instrument updated")
            _show_instrument(result)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.instruments.update_scientific_metadata(args.unique_id, metadata_dict, overwrite=overwrite)
            action = "replaced" if overwrite else "updated"
            logger.info(f"✓ Scientific metadata {action} for instrument {args.unique_id}")

    except Exception as e:
        logger.error(f"Error updating instrument: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _instrument_updatable_fields():
    """Return ordered list of fields that can be updated on an instrument."""
    from .schema import INSTRUMENT_FIELDS, editable_keys
    return editable_keys(INSTRUMENT_FIELDS)


def _register_edit(subparsers):
    """Register the 'instrument edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit instrument fields interactively',
        description='Open instrument fields in $EDITOR and update on save',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument edit MFID001
    EDITOR=vim crucible instrument edit MFID001
"""
    )
    uid_arg = parser.add_argument(
        'unique_id',
        metavar='MFID',
        help='Instrument unique ID (MFID)'
    )
    if ARGCOMPLETE_AVAILABLE:
        uid_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_edit)


def _edit_instrument(uid, client, debug=False):
    """Core edit logic for an instrument - shared with top-level 'crucible edit' command."""
    instrument = client.instruments.get(instrument_id=uid)
    if instrument is None:
        logger.error(f"Instrument not found: {uid}")
        sys.exit(1)

    from .schema import INSTRUMENT_FIELDS, ordered_dict
    valid_fields = set(_instrument_updatable_fields())
    original = ordered_dict(INSTRUMENT_FIELDS, instrument, verbose=True, editable_only=True)

    try:
        edited = term.open_editor_json(original)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    changes = {k: v for k, v in edited.items() if k in valid_fields and v != original.get(k)}

    if not changes:
        logger.info("No changes.")
        return

    try:
        client.instruments.update(uid, **changes)
        term.header("Changes")
        term.diff(original, changes)
    except Exception as e:
        logger.error(f"Error updating instrument: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_edit(args):
    """Execute the 'instrument edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        logger.error(f"Error connecting: {e}")
        sys.exit(1)
    _edit_instrument(args.unique_id, client, debug=getattr(args, 'debug', False))
