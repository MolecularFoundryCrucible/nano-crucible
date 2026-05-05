#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QR subcommand — print a QR code for an MFID to the terminal.
"""

import sys
import logging
from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the top-level 'qr' subcommand."""
    parser = subparsers.add_parser(
        'qr',
        help='Print a QR code for an MFID',
        description='Print a terminal QR code encoding the given MFID.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible qr 0td7evvtg5wb90005k1j97ak94
"""
    )
    parser.add_argument(
        'mfid',
        metavar='MFID',
        help='Resource MFID'
    )
    parser.set_defaults(func=execute)


def print_qr(mfid):
    """Print a QR code for mfid to the terminal. Returns False on error."""
    try:
        import qrcode
    except ImportError:
        logger.error("qrcode package not installed. Run: pip install qrcode")
        return False
    qr = qrcode.QRCode(border=1)
    qr.add_data(mfid)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    return True


def execute(args):
    """Execute the qr command."""
    if not print_qr(args.mfid):
        sys.exit(1)
