#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whoami subcommand — show current user info based on the active API key.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    """Register the whoami subcommand."""
    parser = subparsers.add_parser(
        'whoami',
        help='Show current user info for the active API key',
        description='Display account information associated with the configured API key',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show access group IDs'
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the whoami command."""
    from crucible.config import config
    try:
        info = config.client.whoami()
        user = info.get('user_info', {})

        W = 14
        def _p(label, value):
            print(f"  {label:<{W}}{value if value not in (None, '') else '—'}")

        term.header("Whoami")

        first = user.get('first_name', '')
        last  = user.get('last_name', '')
        name  = f"{first} {last}".strip() or None
        _p("Name",         name)
        _p("ORCID",        term.orcid_link(user.get('orcid')))
        _p("Access Group", info.get('access_group_name'))
        _p("Email",        user.get('email'))
        lbl = user.get('lbl_email')
        if lbl and lbl != user.get('email'):
            _p("LBL Email",    lbl)
        _p("ID",           user.get('id'))

        if getattr(args, 'verbose', False):
            ids = info.get('access_group_ids', [])
            term.subheader(f"Access Group IDs ({len(ids)})")
            for gid in ids:
                print(f"  {gid}")

    except Exception as e:
        logger.error(f"Error retrieving account info: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
