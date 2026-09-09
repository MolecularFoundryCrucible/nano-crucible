#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whoami subcommand — show current user info based on the active API key.
"""

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
        help='Show all fields including access group IDs'
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the whoami command."""
    from crucible.config import config
    try:
        info = config.client.whoami()
        user = info.get('user_info', {})

        _p = term.field_printer(16)

        term.header("Whoami")

        uid = user.get('unique_id')
        _p("Username", user.get('username') or term.dim('(not set)'))
        _p("Name",     term.fmt_name(user, fallback_username=False))
        _p(term.user_id_label(uid), term.user_id_link(uid))
        _p("Email",    user.get('email'))
        if user.get('is_service_account'):
            _p("Type", "service account")

        if getattr(args, 'verbose', False):
            _p("ID", user.get('id'))

            # Dump any remaining user_info fields not already shown
            _known = {'first_name', 'last_name', 'unique_id', 'username',
                      'email', 'id', 'is_service_account'}
            extras = {k: v for k, v in user.items() if k not in _known and v not in (None, '')}
            for key, val in extras.items():
                _p(key.replace('_', ' ').title(), val)

            ids = info.get('access_group_ids', [])
            if ids:
                import textwrap
                ids_str = ", ".join(str(x) for x in ids)
                lines = textwrap.wrap(ids_str, width=60)
                term.subheader(f"Access groups ({len(ids)})")
                for line in lines:
                    print(f"  {line}")

    except Exception as e:
        from .helpers import fail
        fail("retrieving account info", e, args)
