#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrument subcommand for Crucible CLI.

Provides instrument-related operations: list, get.
"""

import sys
import json
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
    _register_search(instrument_subparsers)
    _register_search_metadata(instrument_subparsers)
    _register_get(instrument_subparsers)
    _register_create(instrument_subparsers)
    _register_update(instrument_subparsers)
    _register_set_status(instrument_subparsers)
    _register_edit(instrument_subparsers)
    _register_transfer_ownership(instrument_subparsers)
    _register_list_service_accounts(instrument_subparsers)
    _register_bind_sa(instrument_subparsers)
    _register_unbind_sa(instrument_subparsers)
    from ._access import register_access_commands
    register_access_commands(instrument_subparsers, 'instruments', id_metavar='INSTRUMENT_MFID')


def _register_list(subparsers):
    """Register the 'instrument list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List instruments',
        description='List instruments (active by default)'
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
        '--status',
        choices=['active', 'maintenance', 'decommissioned'],
        help='Filter by lifecycle status (default: active)'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON array'
    )

    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'instrument get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get instrument by MFID or instrument slug',
        description='Retrieve an instrument by canonical MFID or exact instrument_id slug'
    )

    instrument_arg = parser.add_argument(
        'instrument',
        metavar='INSTRUMENT',
        help='Instrument MFID or instrument_id slug'
    )
    # Disable file completion for instrument name/ID
    if ARGCOMPLETE_AVAILABLE:
        instrument_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--by-id',
        action='store_true',
        help='Deprecated: treat the argument explicitly as an MFID'
    )

    parser.add_argument(
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in output'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'instrument create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new instrument',
        description='Register a new instrument as an authenticated human user',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible instrument create

    # Command-line mode
    crucible instrument create -n "titan" --instrument-id titan --location "Building 67"
    crucible instrument create -n "titan" --instrument-id titan --owner roncofaber --location "Building 67" \\
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
        '--instrument-id',
        dest='instrument_id',
        metavar='ID',
        help='Unique instrument slug (required). If not provided, will prompt interactively.'
    )
    parser.add_argument(
        '--owner',
        metavar='OWNER',
        help='ORCID, MFID, username, or email of owner (default: authenticated identity)'
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
    parser.set_defaults(func=_execute_create)


def _execute_create(args):
    """Execute the 'instrument create' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import prompt_optional, prompt_required, validate_user_reference
    from ..utils.identifiers import validate_slug

    instrument_name = args.instrument_name
    instrument_id = args.instrument_id
    owner = args.owner
    location = args.location

    interactive = instrument_name is None or instrument_id is None or location is None
    if interactive:
        term.header("Create Instrument")
        print("")

    if instrument_name is None:
        instrument_name = prompt_required("Instrument name", option='--name')

    if instrument_id is None:
        instrument_id = prompt_required(
            "Instrument ID",
            validator=lambda value: validate_slug(value, 'instrument'),
            option='--instrument-id',
        )

    if location is None:
        location = prompt_required("Location", option='--location')

    manufacturer = args.manufacturer
    model = args.model
    instrument_type = args.instrument_type
    description = args.description

    if interactive:
        if manufacturer is None:
            manufacturer = prompt_optional("Manufacturer")
        if model is None:
            model = prompt_optional("Model")
        if instrument_type is None:
            instrument_type = prompt_optional("Type")
        if description is None:
            description = prompt_optional("Description")

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
        if owner is not None:
            owner = validate_user_reference(owner)
        client = CrucibleClient()

        instrument = Instrument(
            instrument_name=instrument_name,
            instrument_id=instrument_id,
            owner=owner,
            location=location,
            manufacturer=manufacturer,
            model=model,
            instrument_type=instrument_type,
            description=description,
        )

        result = client.instruments.create(instrument, scientific_metadata=metadata_dict)

        term.success("Instrument created", args)
        _show_instrument(result)

    except Exception as e:
        from .helpers import fail
        fail("creating instrument", e, args)


def _execute_list(args):
    """Execute the 'instrument list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        instruments = client.instruments.list(
            limit=args.limit,
            include_metadata=getattr(args, 'include_metadata', False) or _config.include_metadata,
            include_owner=True,
            status=getattr(args, 'status', None),
        )

        if getattr(args, 'json', False):
            print(json.dumps(instruments, indent=2, default=str))
            return

        term.header(f"Instruments ({len(instruments)})")
        if not instruments:
            print(f"  {term.dim('No instruments found.')}")
        else:
            from .helpers import instrument_explorer_url
            def _instrument_row(instrument):
                uid = instrument.get('unique_id')
                instrument_id = instrument.get('instrument_id')
                url = instrument_explorer_url(uid)
                return (
                    term.navigation_link(instrument.get('instrument_name'), url) or '-',
                    instrument_id or '-',
                    term.mfid_link(
                        uid, url if not instrument.get('instrument_name') else None,
                    ) or '-',
                    term.fmt_owner(instrument) or '-',
                    term.status_label(instrument.get('status')),
                )
            rows = [_instrument_row(instrument) for instrument in instruments]
            term.table(rows, ['Name', 'Instrument ID', 'MFID', 'Owner', 'Status'],
                       max_widths=[24, 25, 26, 25, 12],
                       min_widths=[4, 25, 26, 5, 6])

    except Exception as e:
        from .helpers import fail
        fail("listing instruments", e, args)


def _show_instrument(instrument, include_metadata=False):
    """Display instrument fields."""
    _p = term.field_printer(14)

    from .helpers import instrument_explorer_url

    term.header("Instrument")
    uid = instrument.get('unique_id')
    instrument_url = instrument_explorer_url(uid)
    name = instrument.get('instrument_name')
    _p("Name",          term.bold(name) if name else term.dim('-'))
    _p("Instrument ID", instrument.get('instrument_id'))
    _p("MFID",          term.mfid_link(uid, instrument_url))
    _p("Type",         instrument.get('instrument_type'))
    _p("Manufacturer", instrument.get('manufacturer'))
    _p("Model",        instrument.get('model'))
    _p("Location",     instrument.get('location'))
    _p("Description",  instrument.get('description'))
    if instrument.get('other_id'):
        _p("Other ID",     f"{instrument['other_id']}  ({instrument.get('other_id_source', '')})")

    term.subheader("Access")
    _p("Owner",  term.fmt_owner(instrument))
    _p("Status", term.status_label(instrument.get('status')))

    timing = (
        ("Created", instrument.get('creation_time')),
        ("Modified", instrument.get('modification_time')),
    )
    if any(value for _, value in timing):
        term.subheader("Timing")
        for label, value in timing:
            if value:
                _p(label, term.fmt_ts(value))

    if include_metadata:
        from .helpers import show_scientific_metadata
        show_scientific_metadata(instrument.get('scientific_metadata'))


def _execute_get(args):
    """Execute the 'instrument get' subcommand."""
    from crucible.client import CrucibleClient
    include_metadata = getattr(args, 'include_metadata', False) or _config.include_metadata
    try:
        client = CrucibleClient()

        if args.by_id:
            import warnings
            warnings.warn(
                "--by-id is deprecated because MFID/slug dispatch is automatic.",
                DeprecationWarning,
                stacklevel=2,
            )
            instrument = client.instruments.get(
                instrument_mfid=args.instrument,
                include_metadata=include_metadata,
            )
        else:
            instrument = client.instruments.get(
                args.instrument,
                include_metadata=include_metadata,
            )

        if instrument is None:
            logger.error(f"Instrument not found: {args.instrument}")
            sys.exit(1)

        if getattr(args, 'json', False):
            import json
            print(json.dumps(instrument, indent=2, default=str))
        else:
            _show_instrument(instrument, include_metadata=include_metadata)

    except Exception as e:
        from .helpers import fail
        fail("retrieving instrument", e, args)


def _register_update(subparsers):
    """Register the 'instrument update' subcommand."""
    parser = subparsers.add_parser(
        'update',
        help='Update an instrument record or scientific metadata',
        description='Partially update an instrument record (requires editor permission)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument update MFID001 --location "Building 67, Room 101"
    crucible instrument update MFID001 --model "Titan 80-300"
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
        'location':        args.location,
        'manufacturer':    args.manufacturer,
        'model':           args.model,
        'instrument_type': args.instrument_type,
        'description':     args.description,
    }.items() if v is not None}

    has_metadata = bool(getattr(args, 'metadata', None))

    if not fields and not has_metadata:
        logger.error("No fields to update. Provide at least one of: --name, --location, --manufacturer, --model, --type, --description, --metadata")
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
            term.success("Instrument updated", args)
            _show_instrument(result)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.instruments.update_scientific_metadata(args.unique_id, metadata_dict, overwrite=overwrite)
            action = "replaced" if overwrite else "updated"
            term.success(f"Scientific metadata {action} for instrument {args.unique_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("updating instrument", e, args)


def _register_transfer_ownership(subparsers):
    """Register the 'instrument transfer-ownership' subcommand."""
    parser = subparsers.add_parser(
        'transfer-ownership',
        help='Transfer ownership of an instrument',
        description='Preview or execute an ownership transfer (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument transfer-ownership INSTRUMENT_MFID newowner@example.com
    crucible instrument transfer-ownership INSTRUMENT_MFID newowner@example.com --confirm
"""
    )
    parser.add_argument('instrument_mfid', metavar='INSTRUMENT_MFID', help='Instrument MFID')
    parser.add_argument(
        'new_owner', metavar='NEW_OWNER',
        help='ORCID, MFID, username, or email of the new owner',
    )
    parser.add_argument(
        '--confirm', action='store_true',
        help='Execute the transfer (default: preview only)',
    )
    parser.set_defaults(func=_execute_transfer_ownership)


def _execute_transfer_ownership(args):
    """Execute the 'instrument transfer-ownership' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_transfer_ownership

    try:
        client = CrucibleClient()
        result = client.instruments.transfer_ownership(
            args.instrument_mfid, args.new_owner, confirm=args.confirm,
        )
        show_transfer_ownership(result, args.confirm)
    except Exception as e:
        fail("transferring instrument ownership", e, args)


def _register_set_status(subparsers):
    parser = subparsers.add_parser(
        'set-status',
        help='Change an instrument lifecycle status',
        description='Set an instrument to active, maintenance, or decommissioned',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument set-status INSTRUMENT_MFID maintenance
""",
    )
    parser.add_argument('instrument_mfid', metavar='INSTRUMENT_MFID', help='Instrument MFID')
    parser.add_argument(
        'status',
        choices=['active', 'maintenance', 'decommissioned'],
        help='New lifecycle status',
    )
    parser.set_defaults(func=_execute_set_status)


def _execute_set_status(args):
    from crucible.client import CrucibleClient
    from .helpers import fail

    try:
        instrument = CrucibleClient().instruments.set_status(
            args.instrument_mfid, args.status)
        term.success(
            f"Instrument {args.instrument_mfid} status changed to {args.status}", args)
        _show_instrument(instrument)
    except Exception as e:
        fail("changing instrument status", e, args)


def _register_list_service_accounts(subparsers):
    parser = subparsers.add_parser(
        'list-service-accounts',
        help='List service accounts bound to an instrument',
        description='List the instrument operator service accounts',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument list-service-accounts INSTRUMENT_MFID
""",
    )
    parser.add_argument('instrument_mfid', metavar='INSTRUMENT_MFID', help='Instrument MFID')
    parser.set_defaults(func=_execute_list_service_accounts)


def _service_account_rows(members):
    return [
        (
            member.username or '-',
            term.fmt_name(member.model_dump(), default='-', fallback_username=False),
            term.cyan(member.unique_id) if member.unique_id else '-',
            member.role or '-',
        )
        for member in members
    ]


def _execute_list_service_accounts(args):
    from crucible.client import CrucibleClient
    from .helpers import fail, sort_members

    try:
        members = sort_members(
            CrucibleClient().instruments.list_service_accounts(args.instrument_mfid))
        term.header(f"Instrument Service Accounts ({len(members)})")
        if not members:
            print(f"  {term.dim('No service accounts found.')}")
            return
        rows = _service_account_rows(members)
        term.table(
            rows,
            ['Username', 'Name', 'MFID', 'Role'],
            max_widths=[25, 25, 26, 12],
            min_widths=[24, 4, 26, 6],
        )
    except Exception as e:
        fail("listing instrument service accounts", e, args)


def _register_bind_sa(subparsers):
    """Register the 'instrument bind-sa' subcommand."""
    parser = subparsers.add_parser(
        'bind-sa',
        help='Bind a service account as an instrument operator',
        description='Grant a service account operator standing on an instrument',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument bind-sa MFID001 sa-unique-id
"""
    )
    uid_arg = parser.add_argument(
        'instrument_mfid', metavar='MFID', help='Instrument unique ID (MFID)'
    )
    if ARGCOMPLETE_AVAILABLE:
        uid_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('sa_id', metavar='SA_ID', help='Service account unique ID')
    parser.set_defaults(func=_execute_bind_sa)


def _execute_bind_sa(args):
    """Execute the 'instrument bind-sa' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, sort_members

    try:
        client = CrucibleClient()
        members = sort_members(client.instruments.bind_service_account(args.instrument_mfid, args.sa_id))
        term.success(f"Service account {args.sa_id} bound to instrument {args.instrument_mfid}", args)
        rows = _service_account_rows(members)
        term.table(rows, ['Username', 'Name', 'ID', 'Role'], max_widths=[25, 25, 30, 12])
    except Exception as e:
        fail("binding service account", e, args)


def _register_unbind_sa(subparsers):
    """Register the 'instrument unbind-sa' subcommand."""
    parser = subparsers.add_parser(
        'unbind-sa',
        help='Remove a service account as an instrument operator',
        description='Revoke a service account operator standing on an instrument',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument unbind-sa MFID001 sa-unique-id
"""
    )
    uid_arg = parser.add_argument(
        'instrument_mfid', metavar='MFID', help='Instrument unique ID (MFID)'
    )
    if ARGCOMPLETE_AVAILABLE:
        uid_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('sa_id', metavar='SA_ID', help='Service account unique ID')
    parser.set_defaults(func=_execute_unbind_sa)


def _execute_unbind_sa(args):
    """Execute the 'instrument unbind-sa' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, sort_members

    try:
        client = CrucibleClient()
        members = sort_members(client.instruments.unbind_service_account(args.instrument_mfid, args.sa_id))
        term.success(f"Service account {args.sa_id} unbound from instrument {args.instrument_mfid}", args)
        rows = _service_account_rows(members)
        term.table(rows, ['Username', 'Name', 'ID', 'Role'], max_widths=[25, 25, 30, 12])
    except Exception as e:
        fail("unbinding service account", e, args)


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
    parser.set_defaults(func=_execute_edit)


def _edit_instrument(uid, client, debug=False):
    """Core edit logic for an instrument - shared with top-level 'crucible edit' command."""
    instrument = client.instruments.get(instrument_mfid=uid, include_metadata=True)
    if instrument is None:
        logger.error(f"Instrument not found: {uid}")
        sys.exit(1)

    from .schema import INSTRUMENT_FIELDS, ordered_dict
    valid_fields = set(_instrument_updatable_fields())
    original_fields = ordered_dict(INSTRUMENT_FIELDS, instrument, verbose=True, editable_only=True)
    original_meta = instrument.get('scientific_metadata') or {}

    original = dict(original_fields)
    original['scientific_metadata'] = original_meta

    try:
        edited = term.open_editor_json(original)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    field_changes = {k: v for k, v in edited.items() if k in valid_fields and v != original_fields.get(k)}
    edited_meta = edited.get('scientific_metadata')
    meta_changed = isinstance(edited_meta, dict) and edited_meta != original_meta

    if not field_changes and not meta_changed:
        logger.info("No changes.")
        return

    try:
        if field_changes:
            client.instruments.update(uid, **field_changes)
        if meta_changed:
            client.instruments.update_scientific_metadata(uid, edited_meta, overwrite=True)

        diff_updated = dict(field_changes)
        if meta_changed:
            diff_updated['scientific_metadata'] = edited_meta
        term.header("Changes")
        term.diff(original, diff_updated)
    except Exception as e:
        from .helpers import fail
        fail("updating instrument", e, debug)


def _execute_edit(args):
    """Execute the 'instrument edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)
    _edit_instrument(args.unique_id, client, debug=getattr(args, 'debug', False))


def _register_search(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Fuzzy search instruments by name, type, or manufacturer',
        description='Fuzzy search across instruments.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible instrument search titan
    crucible instrument search "electron microscope"
    crucible instrument search XRD --limit 10
""",
    )
    parser.add_argument('query', metavar='QUERY', help='Search term (min 3 chars)')
    parser.add_argument('--limit', '-l', type=int, default=20, metavar='N',
                        help='Maximum results (default: 20, max: 50)')
    parser.add_argument(
        '--status',
        choices=['active', 'maintenance', 'decommissioned'],
        help='Filter by lifecycle status',
    )
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_search)


def _execute_search(args):
    if len(args.query) < 3:
        from .helpers import fail
        fail("searching instruments", ValueError("Search term must be at least 3 characters."), args)
    from crucible.client import CrucibleClient
    try:
        client  = CrucibleClient()
        results = client.instruments.search(
            args.query, limit=args.limit, status=getattr(args, 'status', None))
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Instruments matching '{args.query}' ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        from .helpers import instrument_explorer_url
        def _instrument_row(instrument):
            uid = instrument.get('unique_id')
            name = instrument.get('instrument_name')
            url = instrument_explorer_url(uid)
            return (
                term.navigation_link(name, url) if name else '-',
                instrument.get('instrument_id') or '-',
                instrument.get('instrument_type') or '-',
                term.mfid_link(uid, url if not name else None) or '-',
            )
        rows = [_instrument_row(instrument) for instrument in results]
        term.table(rows, ['Name', 'Instrument ID', 'Type', 'MFID'],
                   max_widths=[25, 25, 20, 26],
                   min_widths=[4, 25, 4, 26])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_search_metadata(subparsers):
    for name in ('search-metadata', 'search-md'):
        parser = subparsers.add_parser(
            name,
            help='Search instruments by scientific metadata' if name == 'search-metadata' else None,
            description='Full-text search across scientific metadata of all accessible instruments.',
            formatter_class=term.ColorHelpFormatter,
        )
        parser.add_argument('query', metavar='QUERY', help='Search query string')
        parser.add_argument('--limit', '-l', type=int, default=50, metavar='N',
                            help='Maximum results (default: 50)')
        parser.add_argument('--json', action='store_true', default=False,
                            help='Output as JSON array')
        parser.set_defaults(func=_execute_search_metadata)


def _execute_search_metadata(args):
    from crucible.client import CrucibleClient
    try:
        client  = CrucibleClient()
        results = client.instruments.search_metadata(args.query, limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Metadata search: {args.query} ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        for r in results:
            print(f"  {term.cyan(r.get('unique_id', '-'))}")
    except Exception as e:
        from .helpers import fail
        fail("", e, args)
