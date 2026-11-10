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
        help='Manage your own account (show, edit, update, keys, verify)',
        description='Self-service account management. No admin required.',
    )
    sub = parser.add_subparsers(dest='account_command', metavar='COMMAND')
    sub.required = True

    _register_show(sub)
    _register_edit(sub)
    _register_update(sub)
    _register_keys(sub)
    from .helpers import add_removed_command
    add_removed_command(sub, 'api-key', "'crucible account keys create NAME'")
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


def _register_keys(subparsers):
    from .helpers import add_limit_arguments
    parser = subparsers.add_parser(
        'keys',
        help='List, create, rename, or revoke your API keys',
        description='Manage your API keys. A key is shown only once, when it is created.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible account keys list
    crucible account keys list --inactive
    crucible account keys create laptop --expires 2027-06-30
    crucible account keys rename 12 "cluster jobs"
    crucible account keys revoke 12
""",
    )
    sub = parser.add_subparsers(dest='keys_command', metavar='COMMAND')
    sub.required = True

    list_parser = sub.add_parser('list', help='List your API keys',
                                 formatter_class=term.ColorHelpFormatter)
    list_parser.add_argument('--inactive', action='store_true', default=False,
                             help='List expired and revoked keys instead of active ones')
    add_limit_arguments(list_parser, 'keys')
    list_parser.add_argument('--json', action='store_true', default=False, help='Output as JSON')
    list_parser.set_defaults(func=_execute_keys_list)

    create = sub.add_parser(
        'create', help='Create an API key (needs a recent sign-in, not an API key)',
        description='Create an API key and show it once. Creating a key needs a recent '
                    'sign-in to the Crucible Hub; an API key is refused.',
        formatter_class=term.ColorHelpFormatter)
    create.add_argument('name', metavar='NAME', help='What the key is for, such as a machine or script')
    create.add_argument('--expires', metavar='DATE', default=None,
                        help='Expiry date or time, at most a year away (default: a year); '
                             'UTC unless a zone is given')
    create.add_argument('--json', action='store_true', default=False, help='Output as JSON')
    create.set_defaults(func=_execute_keys_create)

    rename = sub.add_parser('rename', help='Rename an API key',
                            formatter_class=term.ColorHelpFormatter)
    rename.add_argument('key_id', metavar='ID', type=int, help='Key ID from `crucible account keys list`')
    rename.add_argument('name', metavar='NAME', help='New name')
    rename.set_defaults(func=_execute_keys_rename)

    revoke = sub.add_parser('revoke', help='Revoke an API key',
                            formatter_class=term.ColorHelpFormatter)
    revoke.add_argument('key_id', metavar='ID', type=int, help='Key ID from `crucible account keys list`')
    revoke.add_argument('-y', '--yes', action='store_true', default=False,
                        help='Skip the confirmation prompt')
    revoke.set_defaults(func=_execute_keys_revoke)


def print_key_list(keys, title: str, args) -> None:
    """Print API key records as a table, or as JSON with --json."""
    import json
    from .helpers import count_label, print_more_hint, resolve_limit
    if getattr(args, 'json', False):
        print_more_hint(keys, resolve_limit(args), args)
        print(json.dumps(keys, indent=2, default=str))
        return
    term.header(f"{title} ({count_label(keys)})")
    if not keys:
        print(f"  {term.dim('No keys found.')}")
        return
    rows = [(
        str(key.get('id')),
        key.get('name') or '-',
        f"...{key['last4']}" if key.get('last4') else '-',
        key.get('status') or '-',
        term.fmt_ts(key.get('created_at')) or '-',
        term.fmt_ts(key.get('last_used_at')) or '-',
        term.fmt_ts(key.get('revoked_at') or key.get('expires_at')) or '-',
    ) for key in keys]
    ends = 'Ended' if getattr(args, 'inactive', False) else 'Expires'
    term.table(rows, ['ID', 'Name', 'Key', 'Status', 'Created', 'Last used', ends],
               max_widths=[8, 30, 8, 8, 20, 20, 20])
    print_more_hint(keys, resolve_limit(args), args)


def _parse_expiry(text):
    from datetime import timezone
    from dateutil import parser as dateparser
    try:
        when = dateparser.isoparse(text)
    except ValueError:
        raise ValueError(f"--expires {text!r} is not an ISO date or time, such as 2027-06-30.")
    return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)


def _execute_keys_list(args):
    from crucible.config import get_client
    from .helpers import page_kwargs, resolve_limit
    try:
        state = 'inactive' if args.inactive else 'active'
        keys = get_client().account.list_api_keys(
            state=state, limit=resolve_limit(args), **page_kwargs(args))
        print_key_list(keys, 'Inactive API Keys' if args.inactive else 'API Keys', args)
    except Exception as e:
        from .helpers import fail
        fail("listing your API keys", e, args)


def _execute_keys_create(args):
    import json
    from crucible.config import get_client
    try:
        expires = _parse_expiry(args.expires) if args.expires else None
        key = get_client().account.create_api_key(args.name, expires_at=expires)
        if getattr(args, 'json', False):
            print(json.dumps(key, indent=2, default=str))
            return
        _p = term.field_printer(9)
        term.header("New API Key")
        _p("ID", str(key.get('id')))
        _p("Name", key.get('name'))
        _p("Expires", term.fmt_ts(key.get('expires_at')))
        _p("Key", key.get('api_key'))
        print(f"  {term.dim('Store it now: it is not shown again. `crucible config set api_key` saves it.')}")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("creating an API key", e, args)


def _execute_keys_rename(args):
    from crucible.config import get_client
    try:
        key = get_client().account.rename_api_key(args.key_id, args.name)
        term.success(f"Renamed key {key.get('id')} to {key.get('name')!r}", args)
    except Exception as e:
        from .helpers import fail
        fail("renaming the API key", e, args)


def _execute_keys_revoke(args):
    from crucible.config import get_client
    from .helpers import prompt_confirm
    try:
        confirmed = args.yes or prompt_confirm(
            f"Revoke API key {args.key_id}? Anything using it stops working.",
            option='--yes')
        if not confirmed:
            logger.info("Aborted.")
            return
        get_client().account.revoke_api_key(args.key_id)
        term.success(f"Revoked API key {args.key_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("revoking the API key", e, args)




def _register_verify(subparsers):
    parser = subparsers.add_parser(
        'verify',
        help='Check your API key validity and expiry',
        description='Show whether your API key is valid and when it expires.',
    )
    parser.set_defaults(func=_execute_verify)


def _execute_verify(args):
    import requests as _req
    from crucible.config import get_client
    try:
        info = get_client().account.verify()
        _p = term.field_printer(11)
        term.header("API Key")
        valid = info.get('valid', False)
        _p("Valid",   term.green("yes") if valid else term.red("no"))
        _p("Created", term.fmt_ts(info.get('created_at')))
        _p("Expires", term.fmt_ts(info.get('expires_at')))
        if info.get('last_used_at'):
            _p("Last used", term.fmt_ts(info.get('last_used_at')))
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
    _p("Name",  term.fmt_name(user, fallback_username=False))
    term.print_user_ids(_p, user)
    _p("Email",  user.get('email'))
    if user.get('is_service_account'):
        _p("Type", "service account")


def _execute_show(args):
    from crucible.config import get_client
    try:
        user = get_client().account.profile()
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
    from crucible.config import get_client
    try:
        client = get_client()
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
    from crucible.config import get_client

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
        result = get_client().account.update_profile(**fields)
        _show_profile(result)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


