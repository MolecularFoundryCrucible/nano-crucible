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
    """Print a centered, labelled QR code for mfid. Returns False on error."""
    try:
        import qrcode
    except ImportError:
        logger.error("qrcode package not installed. Run: pip install qrcode")
        return False

    import io, os
    qr = qrcode.QRCode(border=1)
    qr.add_data(mfid)
    qr.make(fit=True)

    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    lines = buf.getvalue().splitlines()

    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    qr_width = max(len(l) for l in lines) if lines else 0
    pad = ' ' * max(0, (term_width - qr_width) // 2)

    term.subheader("QR Code")
    print()
    for line in lines:
        print(pad + line)
    print(pad + term.dim(mfid))
    return True


def execute(args):
    """Execute the qr command."""
    if not print_qr(args.mfid):
        sys.exit(1)
