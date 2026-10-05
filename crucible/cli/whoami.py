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
        help='Show all fields, including access group IDs and every capability flag'
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

        _show_authorization(config.client, _p,
                            verbose=getattr(args, 'verbose', False))

        if getattr(args, 'verbose', False):
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


_CAPABILITY_LABELS = {
    'can_create_dataset':          'create datasets',
    'can_create_sample':           'create samples',
    'can_create_project':          'create projects',
    'can_register_instrument':     'register instruments',
    'can_create_for_others':       'create for other users',
    'can_manage_service_accounts': 'manage service accounts',
}


def _show_authorization(client, _p, verbose=False):
    """Print the caller's platform role, privilege mode, and capabilities."""
    auth = client.authorization
    caps = client.capabilities
    if auth.platform_role is None and not caps.model_dump(exclude_none=True):
        return

    term.subheader("Authorization")
    _p = term.field_printer(24) if verbose else _p
    if auth.platform_role and auth.platform_role != 'none':
        _p("Platform role", auth.platform_role)
    mode = 'elevated' if client.is_elevated else 'normal'
    if client.privilege_mode is None and auth.can_elevate:
        mode += term.dim(' (default)')
    _p("Privilege", mode)
    if verbose:
        _p("Can elevate", "yes" if auth.can_elevate else "no")
        for key, label in _CAPABILITY_LABELS.items():
            value = getattr(caps, key)
            if value is not None:
                _p(label.capitalize(), "yes" if value else "no")
    else:
        allowed = [label for key, label in _CAPABILITY_LABELS.items()
                   if getattr(caps, key)]
        _p("Can", ', '.join(allowed) if allowed else term.dim('(none)'))
