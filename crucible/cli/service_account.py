#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service account subcommand — create and manage non-human API users.

Accessible as both 'crucible service-account' and 'crucible sa'.
All operations require admin permissions.
"""

import json
import sys
import logging
from . import term

logger = logging.getLogger(__name__)

_EDITABLE = ('username', 'first_name', 'last_name')


def register_subcommand(subparsers):
    for name in ('service-account', 'sa'):
        parser = subparsers.add_parser(
            name,
            help='Manage service accounts (admin only)',
            description='Create and manage non-human API users with API key authentication.',
        )
        sa_subparsers = parser.add_subparsers(dest='sa_command', metavar='COMMAND')
        sa_subparsers.required = True

        _register_create(sa_subparsers)
        _register_rotate_key(sa_subparsers)
        _register_get(sa_subparsers)
        _register_list(sa_subparsers)
        _register_edit(sa_subparsers)
        _register_update(sa_subparsers)
        _register_list_access_groups(sa_subparsers)
        _register_add_access_group(sa_subparsers)
        _register_remove_access_group(sa_subparsers)


def _show_sa(sa, key=None):
    """Display a service account record."""
    _p = term.field_printer(14)
    term.header("Service Account")
    _p("MFID",     sa.get('unique_id'))
    _p("Username", sa.get('username'))
    name = term.fmt_name(sa, fallback_username=False)
    if name:
        _p("Name", name)
    if key:
        print()
        print(f"  {term.yellow('API Key')}  {term.bold(key)}")
        print(f"  {term.dim('Store this now — it will not be shown again.')}")


def _resolve_sa(client, unique_id=None, username=None, ambiguous=False):
    """Resolve a service account by unique_id or username, return the record.

    If ambiguous=True, unique_id was guessed from the identifier's shape (it
    matched the MFID pattern) rather than given explicitly — a username could
    coincidentally match that pattern too. On a miss, retry as a username
    before giving up.
    """
    sa = client.service_accounts.get(service_account_mfid=unique_id, username=username)
    if sa is None and ambiguous and unique_id:
        sa = client.service_accounts.get(username=unique_id)
    if sa is None:
        raise ValueError("Service account not found.")
    return sa


def _resolve_sa_ref(args):
    """Resolve the sa/unique_id/username args into (unique_id, username, ambiguous).

    Warns if the deprecated --unique-id/--username flags were used instead of
    the positional SA argument. Exits with an error if neither was provided.
    """
    import warnings
    from .helpers import parse_sa_ref

    unique_id = getattr(args, 'unique_id', None)
    username  = getattr(args, 'username', None)
    sa_ref    = getattr(args, 'sa', None)

    if unique_id or username:
        warnings.warn(
            "--unique-id/--username are deprecated; pass the identifier "
            "positionally instead: crucible sa get SA",
            DeprecationWarning, stacklevel=3,
        )
        return unique_id, username, False
    if sa_ref:
        ref = parse_sa_ref(sa_ref)
        return ref.get('unique_id'), ref.get('username'), 'unique_id' in ref

    raise ValueError("Provide a service account identifier: crucible sa get SA")


def _register_create(subparsers):
    parser = subparsers.add_parser(
        'create',
        help='Create a new service account',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa create --username nirvana-sa
    crucible sa create --username nirvana-sa --unique-id 0th7...
""",
    )
    parser.add_argument('--username', '-u', default=None, metavar='USERNAME',
                        help='Unique username (3-24 chars, starts with a letter; lowercase letters, digits, hyphens, and underscores). '
                             'Prompted interactively if omitted.')
    parser.add_argument('--unique-id', metavar='MFID',
                        help='Optional MFID — server generates one if omitted')
    parser.set_defaults(func=_execute_create)


def _execute_create(args):
    from crucible.client import CrucibleClient
    from .helpers import prompt_optional, prompt_username
    from ..utils.identifiers import validate_mfid, validate_username

    username = getattr(args, 'username', None)
    unique_id = getattr(args, 'unique_id', None)

    if username is None:
        print()
        print("  Creating a new service account.")
        print()
        username = prompt_username()
        unique_id = prompt_optional("MFID", validator=validate_mfid)
        print()

    try:
        username = validate_username(username)
        if unique_id is not None:
            unique_id = validate_mfid(unique_id)
        client = CrucibleClient()
        result = client.service_accounts.create(username=username, unique_id=unique_id)
        _show_sa(result, key=result.get('api_key'))
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_rotate_key(subparsers):
    parser = subparsers.add_parser(
        'rotate-key',
        help='Generate a new API key, invalidating the old one',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa rotate-key 0th7...
    crucible sa rotate-key nirvana-sa
""",
    )
    parser.add_argument('sa', metavar='SA', nargs='?', default=None,
                        help='MFID or username of the service account')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unique-id', '-o', metavar='MFID',     help='(deprecated, use positional SA)')
    group.add_argument('--username',  '-u', metavar='USERNAME',  help='(deprecated, use positional SA)')
    parser.set_defaults(func=_execute_rotate_key)


def _execute_rotate_key(args):
    from crucible.client import CrucibleClient
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = CrucibleClient()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)
        result = client.service_accounts.rotate_key(sa.get('unique_id'))
        _show_sa(result, key=result.get('api_key'))
    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_get(subparsers):
    parser = subparsers.add_parser(
        'get',
        help='Show a service account',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa get 0th7...
    crucible sa get nirvana-sa
""",
    )
    parser.add_argument('sa', metavar='SA', nargs='?', default=None,
                        help='MFID or username of the service account')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unique-id', '-o', metavar='MFID',    help='(deprecated, use positional SA)')
    group.add_argument('--username',  '-u', metavar='USERNAME', help='(deprecated, use positional SA)')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    from crucible.client import CrucibleClient
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = CrucibleClient()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)
        if getattr(args, 'json', False):
            print(json.dumps(sa, indent=2, default=str))
        else:
            _show_sa(sa)
    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_list(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='List all service accounts',
        formatter_class=term.ColorHelpFormatter,
    )
    parser.add_argument('--limit', type=int, default=100, metavar='N')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_list)


def _execute_list(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        accounts = client.service_accounts.list(limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(accounts, indent=2, default=str))
            return
        term.header(f"Service Accounts ({len(accounts)})")
        if not accounts:
            print(f"  {term.dim('No service accounts found.')}")
            return
        rows = []
        for sa in accounts:
            rows.append((sa.get('username') or '-',
                         term.cyan(sa.get('unique_id')) if sa.get('unique_id') else '-'))
        term.table(rows, ['Username', 'MFID'], max_widths=[30, 30])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_edit(subparsers):
    parser = subparsers.add_parser(
        'edit',
        help='Edit a service account in your editor',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa edit 0th7...
    crucible sa edit nirvana-sa
""",
    )
    parser.add_argument('sa', metavar='SA', nargs='?', default=None,
                        help='MFID or username of the service account')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unique-id', '-o', metavar='MFID',    help='(deprecated, use positional SA)')
    group.add_argument('--username',  '-u', metavar='USERNAME', help='(deprecated, use positional SA)')
    parser.set_defaults(func=_execute_edit)


def _execute_edit(args):
    from crucible.client import CrucibleClient
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = CrucibleClient()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)
        uid = sa.get('unique_id')
        original = {k: sa.get(k) for k in _EDITABLE}

        try:
            edited = term.open_editor_json(original)
        except (RuntimeError, ValueError) as e:
            logger.error(str(e))
            sys.exit(1)

        if edited is None:
            logger.info("No changes.")
            return

        changes = {k: v for k, v in edited.items() if k in _EDITABLE and v != original.get(k)}
        if not changes:
            logger.info("No changes.")
            return

        result = client.service_accounts.update(uid, **changes)
        term.header("Changes")
        term.diff(original, {k: result.get(k) for k in changes})

    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_update(subparsers):
    parser = subparsers.add_parser(
        'update',
        help='Update a service account with named flags',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa update nirvana-sa --new-username nirvana-v2
    crucible sa update 0th7... --first-name Nirvana
""",
    )
    parser.add_argument('sa', metavar='SA', nargs='?', default=None,
                        help='MFID or username of the service account')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unique-id', '-o', metavar='MFID',    help='(deprecated, use positional SA)')
    group.add_argument('--username',  '-u', metavar='USERNAME', help='(deprecated, use positional SA)')
    parser.add_argument('--new-username',  dest='new_username',  metavar='USERNAME', help='New username')
    parser.add_argument('--first-name',    dest='first_name',    metavar='NAME',     help='First name')
    parser.add_argument('--last-name',     dest='last_name',     metavar='NAME',     help='Last name')
    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    from crucible.client import CrucibleClient
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = CrucibleClient()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)
        uid = sa.get('unique_id')

        fields = {k: v for k, v in {
            'username':   getattr(args, 'new_username', None),
            'first_name': getattr(args, 'first_name', None),
            'last_name':  getattr(args, 'last_name', None),
        }.items() if v is not None}

        if not fields:
            logger.error("No fields to update.")
            sys.exit(1)

        result = client.service_accounts.update(uid, **fields)
        _show_sa(result)

    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_list_access_groups(subparsers):
    parser = subparsers.add_parser(
        'list-access-groups',
        help='List access groups for a service account',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa list-access-groups nirvana-sa
    crucible sa list-access-groups 0th7...
""",
    )
    parser.add_argument('sa', metavar='SA', nargs='?', default=None,
                        help='MFID or username of the service account')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unique-id', '-o', metavar='MFID',    help='(deprecated, use positional SA)')
    group.add_argument('--username',  '-u', metavar='USERNAME', help='(deprecated, use positional SA)')
    parser.set_defaults(func=_execute_list_access_groups)


def _execute_list_access_groups(args):
    from crucible.client import CrucibleClient
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = CrucibleClient()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)

        groups = client.service_accounts.list_access_groups(sa.get('unique_id'))
        term.header(f"Access Groups · {sa.get('username') or sa.get('unique_id')} ({len(groups)})")
        if not groups:
            print(f"  {term.dim('No access groups found.')}")
            return
        for g in groups:
            print(f"  {g}")

    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_add_access_group(subparsers):
    parser = subparsers.add_parser(
        'add-access-group',
        help='Deprecated: use project add-user or instrument bind-sa',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa add-access-group nirvana-sa my-group
""",
    )
    parser.add_argument('sa', metavar='SA', help='MFID or username of the service account')
    parser.add_argument('group_name', metavar='GROUP', help='Access group name')
    parser.set_defaults(func=_execute_add_access_group)


def _execute_add_access_group(args):
    from crucible.client import CrucibleClient
    from .helpers import resolve_sa_id
    try:
        client = CrucibleClient()
        unique_id = resolve_sa_id(client, args.sa)
        client.service_accounts.add_to_access_group(unique_id, args.group_name)
        term.success(f"Added {args.sa} to access group '{args.group_name}'", args)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e)


def _register_remove_access_group(subparsers):
    parser = subparsers.add_parser(
        'remove-access-group',
        help='Deprecated: use project remove-user or instrument unbind-sa',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sa remove-access-group nirvana-sa my-group
""",
    )
    parser.add_argument('sa', metavar='SA', help='MFID or username of the service account')
    parser.add_argument('group_name', metavar='GROUP', help='Access group name')
    parser.set_defaults(func=_execute_remove_access_group)


def _execute_remove_access_group(args):
    from crucible.client import CrucibleClient
    from .helpers import resolve_sa_id
    try:
        client = CrucibleClient()
        unique_id = resolve_sa_id(client, args.sa)
        client.service_accounts.remove_from_access_group(unique_id, args.group_name)
        term.success(f"Removed {args.sa} from access group '{args.group_name}'", args)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e)
