#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Account subcommand — self-service profile management for the authenticated user.

These commands operate on the caller's own account (no admin required).
For admin operations on other users, see 'crucible user'.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    parser = subparsers.add_parser(
        'account',
        help='Manage your own account (show, edit, update, api-key, verify)',
        description='Self-service account management. No admin required.',
    )
    sub = parser.add_subparsers(dest='account_command', metavar='COMMAND')
    sub.required = True

    _register_show(sub)
    _register_edit(sub)
    _register_update(sub)
    _register_api_key(sub)
    _register_verify(sub)


def _register_show(subparsers):
    parser = subparsers.add_parser(
        'show',
        help='Show your profile',
        description='Display your account profile.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible account show
    crucible account show --json
""",
    )
    parser.add_argument('--json', action='store_true', default=False, help='Output as JSON')
    parser.set_defaults(func=_execute_show)


def _register_edit(subparsers):
    parser = subparsers.add_parser(
        'edit',
        help='Edit your profile in $EDITOR',
        description='Open your profile in $EDITOR and update on save. '
                    'Editable fields: username, first_name, last_name, email.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible account edit
    EDITOR=vim crucible account edit
""",
    )
    parser.set_defaults(func=_execute_edit)


def _register_update(subparsers):
    parser = subparsers.add_parser(
        'update',
        help='Update your profile fields',
        description='Update one or more profile fields without opening an editor.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible account update -u fabrice
    crucible account update --email new@lbl.gov
    crucible account update -f Jane -l Doe -u janedoe
""",
    )
    parser.add_argument('-u', '--username',   metavar='USERNAME', default=None, help='Set username')
    parser.add_argument('-f', '--first-name', metavar='NAME',     default=None, dest='first_name', help='First name')
    parser.add_argument('-l', '--last-name',  metavar='NAME',     default=None, dest='last_name',  help='Last name')
    parser.add_argument('--email',            metavar='EMAIL',    default=None, help='Email address')
    parser.set_defaults(func=_execute_update)


def _register_api_key(subparsers):
    parser = subparsers.add_parser(
        'api-key',
        help='Show your API key',
        description='Display the API key associated with your account.',
    )
    parser.set_defaults(func=_execute_api_key)


def _register_verify(subparsers):
    parser = subparsers.add_parser(
        'verify',
        help='Check your API key validity and expiry',
        description='Show whether your API key is valid and when it expires.',
    )
    parser.set_defaults(func=_execute_verify)


def _execute_verify(args):
    import requests as _req
    from crucible.client import CrucibleClient
    try:
        info = CrucibleClient().account.verify()
        _p = term.field_printer(10)
        term.header("API Key")
        valid = info.get('valid', False)
        _p("Valid",   term.green("yes") if valid else term.red("no"))
        _p("Created", term.fmt_ts(info.get('created_at')))
        _p("Expires", term.fmt_ts(info.get('expires_at')))
    except _req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.error("No API key found for this account.")
        else:
            logger.error(f"Error: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _show_profile(user):
    _p = term.field_printer(12)
    term.header("Account")
    _p("Username", user.get('username') or term.dim('(not set)'))
    uid = user.get('unique_id')
    _p("Name",  term.fmt_name(user, fallback_username=False))
    _p(term.user_id_label(uid), term.user_id_link(uid))
    _p("Email",  user.get('email'))
    if user.get('is_service_account'):
        _p("Type", "service account")


def _execute_show(args):
    from crucible.client import CrucibleClient
    try:
        user = CrucibleClient().account.profile()
        if user is None:
            logger.error("No user record found for the current API key - "
                         "the account may not be fully set up yet")
            sys.exit(1)
        if getattr(args, 'json', False):
            import json
            print(json.dumps(user, indent=2, default=str))
        else:
            _show_profile(user)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _execute_edit(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        user = client.account.profile()
        if user is None:
            logger.error("No user record found for the current API key")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        sys.exit(1)

    editable = {
        'username':   user.get('username'),
        'first_name': user.get('first_name'),
        'last_name':  user.get('last_name'),
        'email':      user.get('email'),
    }

    try:
        edited = term.open_editor_json(editable)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    changes = {k: v for k, v in edited.items() if v != editable.get(k)}
    if not changes:
        logger.info("No changes.")
        return

    try:
        result = client.account.update_profile(**changes)
        term.header("Changes")
        term.diff(editable, {k: edited[k] for k in changes})
        _show_profile(result)
    except Exception as e:
        from .helpers import fail
        fail("updating profile", e, args)


def _execute_update(args):
    from crucible.client import CrucibleClient

    fields = {k: v for k, v in {
        'first_name': args.first_name,
        'last_name':  args.last_name,
        'email':      args.email,
        'username':   args.username,
    }.items() if v is not None}

    if not fields:
        logger.error("No fields to update. Provide at least one of: "
                     "-u/--username, -f/--first-name, -l/--last-name, --email")
        sys.exit(1)

    try:
        result = CrucibleClient().account.update_profile(**fields)
        _show_profile(result)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _execute_api_key(args):
    import requests as _req
    from crucible.client import CrucibleClient
    try:
        key = CrucibleClient().account.api_key()
        _p = term.field_printer(8)
        term.header("API Key")
        _p("Key", key)
    except _req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.error("No API key found for this account. "
                         "Use the web interface to generate one.")
        else:
            logger.error(f"Error: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)
