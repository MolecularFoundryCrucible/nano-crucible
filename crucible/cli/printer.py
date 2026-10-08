#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Print subcommand — publish label-printer jobs.
"""

import sys
import logging

from . import term

logger = logging.getLogger(__name__)

_STATUS_MARKERS = {'ok': 'success', 'error': 'error', 'timeout': 'warning'}


def register_subcommand(subparsers):
    """Register the top-level 'print' subcommand."""
    parser = subparsers.add_parser(
        'print',
        help='Publish label-printer jobs',
        description='Publish and confirm label-printer jobs.',
    )
    sub = parser.add_subparsers(dest='print_command', metavar='COMMAND')
    sub.required = True

    _register_barcode(sub)


def _register_barcode(subparsers):
    parser = subparsers.add_parser(
        'barcode',
        help='Print a barcode label for an MFID',
        description=(
            'Publish a barcode print job to a label printer and wait for '
            'confirmation that it printed.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible print barcode lab3-zebra 0td7evvtg5wb90005k1j97ak94 "Sample A"
""",
    )
    parser.add_argument('printer_id', metavar='PRINTER_ID',
                        help='Target printer identifier, e.g. "lab3-zebra"')
    parser.add_argument('mfid', metavar='MFID',
                        help='MFID of the sample or tray to print')
    parser.add_argument('name', metavar='NAME',
                        help='Human-readable label text (may be empty)')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON')
    parser.set_defaults(func=_execute_barcode)


def _execute_barcode(args):
    """Execute 'crucible print barcode'."""
    from crucible.client import CrucibleClient
    from .helpers import fail
    try:
        client = CrucibleClient()
        result = client.print.barcode(args.printer_id, args.mfid, args.name)
    except Exception as e:
        fail("print barcode", e, args)
        return

    if getattr(args, 'json', False):
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        status = result.get('status')
        marker = _STATUS_MARKERS.get(status, 'info')
        term.header("Print Job")
        _p = term.field_printer(12)
        _p("Job ID",   result.get('job_id'))
        _p("Printer",  result.get('printer_id'))
        _p("Status",   f'{term.status_marker(marker)} {status}')
        if result.get('detail'):
            _p("Detail", result.get('detail'))

    if result.get('status') != 'ok':
        sys.exit(1)
