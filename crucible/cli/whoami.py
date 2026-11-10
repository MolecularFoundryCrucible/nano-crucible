#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whoami subcommand — show current user info based on the active API key.
"""

import json
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
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=execute)


def credential_label(client) -> str | None:
    """How the client authenticates, for display, or None if unknown."""
    source = getattr(client, 'credential_source', None)
    if source is None:
        return None
    if source in ('sign-in', 'this session'):
        store = client._credential.store.name
        where = {'keyring': 'OS keyring', 'file': 'credentials file'}.get(store, 'memory only')
        how = 'device code' if client._credential.tokens.grant == 'device_code' else 'browser'
        return f"Crucible sign-in ({how}, {where})"
    return {'argument': 'API key (passed to the client)',
            'CRUCIBLE_API_KEY': 'API key (CRUCIBLE_API_KEY)',
            'config file': 'API key (config file)'}.get(source, source)


def execute(args):
    """Execute the whoami command."""
    from crucible.config import config
    try:
        info = config.client.whoami()
        user = info.get('user_info', {})

        if getattr(args, 'json', False):
            print(json.dumps(_whoami_payload(info, config.client), indent=2, default=str))
            return

        _p = term.field_printer(16)

        term.header("Whoami")

        _p("Username", user.get('username') or term.dim('(not set)'))
        _p("Name",     term.fmt_name(user, fallback_username=False))
        term.print_user_ids(_p, user)
        _p("Email",    user.get('email'))
        if user.get('is_service_account'):
            _p("Type", "service account")
        _p("Signed in with", credential_label(config.client))

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
    'can_manage_users':            'manage users',
}


def _whoami_payload(info, client):
    """The whoami response plus how the client signed in and its authorization."""
    auth = client.authorization
    payload = dict(info)
    payload['signed_in_with'] = credential_label(client)
    payload['authorization'] = {
        'platform_role': auth.platform_role,
        'privilege_mode': 'elevated' if client.is_elevated else 'normal',
        'privilege_mode_is_default': client.privilege_mode is None,
        'can_elevate': auth.can_elevate,
    }
    payload['capabilities'] = client.capabilities.model_dump()
    return payload


def _show_authorization(client, _p, verbose=False):
    """Print the caller's platform role, privilege mode, and capabilities."""
    auth = client.authorization
    caps = client.capabilities
    if auth.platform_role is None and not caps.model_dump(exclude_none=True):
        return

    term.subheader("Authorization")
    if auth.platform_role and auth.platform_role != 'none':
        _p("Platform role", auth.platform_role)
    mode = 'elevated' if client.is_elevated else 'normal'
    if client.privilege_mode is None and auth.can_elevate:
        mode += term.dim(' (default)')
    _p("Privilege", mode)
    if verbose:
        _p("Can elevate", term.fmt_bool(auth.can_elevate))

    term.subheader("Capabilities")
    term.grid([f"{term.check_marker(getattr(caps, key))} {label}"
               for key, label in _CAPABILITY_LABELS.items()])
