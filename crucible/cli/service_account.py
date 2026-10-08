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
        _register_show(sa_subparsers)
        _register_set_role(sa_subparsers)
        _register_list_access_groups(sa_subparsers)
        _register_add_access_group(sa_subparsers)
        _register_remove_access_group(sa_subparsers)


def _show_sa(sa, key=None, groups=None):
    """Display a service account record.

    Shows the platform role and API key status when the record carries them
    (the administrator view), and the groups it belongs to when given.
    """
    _p = term.field_printer(14)
    term.header("Service Account")
    _p("Username", term.bold(sa.get('username')) if sa.get('username') else None)
    _p("MFID",     term.cyan(sa.get('unique_id')) if sa.get('unique_id') else None)
    name = ' '.join(p for p in (sa.get('first_name'), sa.get('last_name')) if p)
    if name and name != sa.get('username'):
        _p("Name", name)
    if sa.get('email'):
        _p("Email", sa.get('email'))

    if 'platform_role' in sa or 'api_key_status' in sa:
        term.subheader("Authorization")
        _p("Platform role", term.platform_role_label(sa.get('platform_role')))
        status = sa.get('api_key_status') or {}
        if status:
            valid = status.get('valid')
            _p("API key", term.green('valid') if valid else term.red('invalid'))
            _p("Issued", term.fmt_date(status.get('created_at')))
            _p("Expires", term.fmt_date(status.get('expires_at')))
        else:
            _p("API key", term.dim('none issued'))

    if groups is not None:
        term.subheader(f"Member of ({len(groups)})")
        _group_table(groups)

    if key:
        print()
        print(f"  {term.yellow('API Key')}  {term.bold(key)}")
        print(f"  {term.dim('Store this now; it will not be shown again.')}")


def _describe_groups(client, group_ids, own_id=None):
    """Name a service account's access groups by the project or instrument behind them.

    Access groups are named by the MFID of what they grant: a project group
    by the project, an instrument operator group by the instrument. The
    account's personal group is named by its own MFID.
    """
    described = []
    for group_id in group_ids:
        if group_id == own_id:
            described.append({'group': group_id, 'kind': 'personal', 'label': '(own group)'})
            continue
        kind, label = 'group', None
        try:
            resource = client.get(group_id, include_owner=False, include_datasets=False)
        except Exception:
            resource = None
        if resource:
            kind = resource.get('resource_type') or 'group'
            label = (resource.get('project_id') or resource.get('instrument_id')
                     or resource.get('title') or resource.get('instrument_name'))
        described.append({'group': group_id, 'kind': kind, 'label': label})
    return described


def _group_table(groups):
    if not groups:
        print(f"  {term.dim('No access groups.')}")
        return
    rows = [(g['label'] or term.dim('-'), g['kind'], term.cyan(g['group'])) for g in groups]
    term.table(rows, ['Name', 'Kind', 'Group'], max_widths=[30, 12, 26])


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
    from crucible.config import get_client
    from .helpers import prompt_optional, prompt_username, require_capability
    from ..utils.identifiers import validate_mfid, validate_username

    # These calls always request elevation, so an administrator is permitted
    # even without the standing capability.
    gate = get_client()
    if not gate.can_elevate:
        require_capability(gate, 'can_manage_service_accounts',
                           'manage service accounts')

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
        client = get_client()
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
    from crucible.config import get_client
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = get_client()
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
    parser.add_argument('--groups', '-g', action='store_true', default=False,
                        help='Also list the projects and instruments it belongs to')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    from crucible.config import get_client
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = get_client()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)
        capabilities = getattr(client, 'capabilities', None)
        if (getattr(client, 'can_elevate', False)
                or getattr(capabilities, 'can_manage_service_accounts', False)):
            try:
                sa = client.service_accounts.get_admin(sa['unique_id'])
            except Exception as e:
                logger.debug(f"Administrator record unavailable: {e}")
        groups = None
        if getattr(args, 'groups', False):
            group_ids = client.service_accounts.list_access_groups(sa['unique_id'])
            groups = _describe_groups(client, group_ids, sa['unique_id'])
        if getattr(args, 'json', False):
            payload = dict(sa)
            if groups is not None:
                payload['access_groups'] = groups
            print(json.dumps(payload, indent=2, default=str))
        else:
            _show_sa(sa, groups=groups)
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
    parser.add_argument('--search', '-q', dest='q', default=None, metavar='TEXT',
                        help='Filter by username or name (at least 3 characters)')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_list)


def _execute_list(args):
    from crucible.config import get_client
    try:
        client = get_client()
        accounts = client.service_accounts.list_admin(q=getattr(args, 'q', None),
                                                      limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(accounts, indent=2, default=str))
            return
        term.header(f"Service Accounts ({len(accounts)})")
        if not accounts:
            print(f"  {term.dim('No service accounts found.')}")
            return
        def _name(sa):
            full = ' '.join(p for p in (sa.get('first_name'), sa.get('last_name')) if p)
            return full if full and full != sa.get('username') else None

        show_names = any(_name(sa) for sa in accounts)
        rows = []
        for sa in accounts:
            row = (sa.get('username') or '-',)
            if show_names:
                row += (_name(sa) or '-',)
            rows.append(row + (
                term.cyan(sa.get('unique_id')) if sa.get('unique_id') else '-',
                term.platform_role_label(sa.get('platform_role'))))
        headers = ['Username'] + (['Name'] if show_names else []) + ['MFID', 'Platform role']
        max_widths = [30] + ([25] if show_names else []) + [26, 13]
        term.table(rows, headers, max_widths=max_widths)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_show(subparsers):
    parser = subparsers.add_parser(
        'show',
        help='Alias for get',
        description='Alias for "get": show a service account with its platform role, '
                    'API key status (administrators), and optionally its groups.',
    )
    parser.add_argument('sa', metavar='SA', help='MFID or username of the service account')
    parser.add_argument('--groups', '-g', action='store_true', default=False,
                        help='Also list the projects and instruments it belongs to')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=_execute_get)


def _register_set_role(subparsers):
    from crucible.constants import PLATFORM_ROLES

    parser = subparsers.add_parser(
        'set-role',
        help='Set a service account platform role (admin only)',
        description='Set the platform-wide role granted to a service account.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible service-account set-role SA_MFID contributor
    crucible service-account set-role SA_MFID none
"""
    )
    parser.add_argument('sa', metavar='SA_MFID', help='Service account MFID')
    parser.add_argument('platform_role', metavar='ROLE', choices=PLATFORM_ROLES,
                        help=f"Platform role: {', '.join(PLATFORM_ROLES)}")
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=_execute_set_role)


def _execute_set_role(args):
    from crucible.config import get_client
    try:
        client = get_client()
        sa = client.service_accounts.set_platform_role(
            args.sa, args.platform_role)
        if getattr(args, 'json', False):
            print(json.dumps(sa, indent=2, default=str))
            return
        term.success(
            f"Set {sa.get('username') or args.sa} role to {args.platform_role}",
            args)
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
    from crucible.config import get_client
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = get_client()
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
    from crucible.config import get_client
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = get_client()
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
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_list_access_groups)


def _execute_list_access_groups(args):
    from crucible.config import get_client
    try:
        unique_id, username, ambiguous = _resolve_sa_ref(args)
        client = get_client()
        sa = _resolve_sa(client, unique_id=unique_id, username=username, ambiguous=ambiguous)

        group_ids = client.service_accounts.list_access_groups(sa.get('unique_id'))
        groups = _describe_groups(client, group_ids, sa.get('unique_id'))
        if getattr(args, 'json', False):
            print(json.dumps(groups, indent=2, default=str))
            return
        term.header(f"Access Groups · {sa.get('username') or sa.get('unique_id')} ({len(groups)})")
        _group_table(groups)

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
    from crucible.config import get_client
    from .helpers import resolve_sa_id
    try:
        client = get_client()
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
    from crucible.config import get_client
    from .helpers import resolve_sa_id
    try:
        client = get_client()
        unique_id = resolve_sa_id(client, args.sa)
        client.service_accounts.remove_from_access_group(unique_id, args.group_name)
        term.success(f"Removed {args.sa} from access group '{args.group_name}'", args)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e)
