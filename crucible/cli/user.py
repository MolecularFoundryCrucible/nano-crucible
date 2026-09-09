#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User subcommand for Crucible CLI.

Provides user-related operations: get, create.
"""

import sys
import logging
import json

logger = logging.getLogger(__name__)

from . import term
from ..config import config as _config


def register_subcommand(subparsers):
    """
    Register the user subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'user',
        help='User operations (get, create, list)',
        description='Manage Crucible users (requires admin permissions)',
    )

    # User subcommands
    user_subparsers = parser.add_subparsers(
        title='user commands',
        dest='user_command',
        help='Available user operations'
    )

    # Register individual user commands
    _register_get(user_subparsers)
    _register_search(user_subparsers)
    _register_create(user_subparsers)
    _register_update(user_subparsers)
    _register_edit(user_subparsers)
    _register_list(user_subparsers)
    _register_list_datasets(user_subparsers)
    _register_check_access(user_subparsers)
    _register_list_access_groups(user_subparsers)
    _register_add_access_group(user_subparsers)
    _register_remove_access_group(user_subparsers)
    _register_list_projects(user_subparsers)


def _register_get(subparsers):
    """Register the 'user get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get user by ORCID, MFID, username, or email',
        description=(
            'Retrieve the caller-authorized user profile. Email is disclosed '
            'only for self and platform-administrator lookups.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user get 0000-0002-1825-0097
    crucible user get 0tkvpezyz1zzf00076nahf85j4
    crucible user get fabrice
    crucible user get user@example.com
"""
    )

    parser.add_argument('user', metavar='USER', nargs='?', default=None,
                        help='ORCID, MFID, username, or email of the user')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--orcid',    metavar='ORCID',    help='(deprecated, use positional USER)')
    group.add_argument('-u', '--username', metavar='USERNAME',  help='(deprecated, use positional USER)')
    group.add_argument('--email',    metavar='EMAIL',     help='(deprecated, use positional USER)')

    parser.add_argument('--json', action='store_true', default=False, help='Output as JSON')

    parser.set_defaults(func=_execute_get)


def _register_search(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Search for users by name or username',
        description='Search users by name or username. Available to all authenticated users — '
                    'no admin required. Returns up to 50 results.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user search fabrice
    crucible user search ron
""",
    )
    parser.add_argument('query', metavar='TERM', help='Search term')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_search)


def _execute_search(args):
    """Execute 'user search'."""
    if len(args.query) < 3:
        from .helpers import fail
        fail("searching users", ValueError("Search term must be at least 3 characters."), args)
    from crucible.client import CrucibleClient
    try:
        users = CrucibleClient().users.search(args.query)

        if getattr(args, 'json', False):
            print(json.dumps(users, indent=2, default=str))
            return

        term.header(f"Users matching '{args.query}' ({len(users)})")
        if not users:
            print(f"  {term.dim('No users found.')}")
            return

        rows = []
        for u in users:
            username = u.get('username') or '-'
            name = term.user_link(
                term.fmt_name(u, default='-', fallback_username=False),
                u.get('unique_id'),
            )
            user_id = term.cyan(u.get('unique_id')) if u.get('unique_id') else '-'
            rows.append((username, name, user_id))
        term.table(
            rows,
            ['Username', 'Name', 'ID'],
            max_widths=[24, 25, 26],
            min_widths=[24, 4, 26],
        )

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_create(subparsers):
    """Register the 'user create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new user',
        description='Add a new user to Crucible (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible user create

    # Command-line mode (all arguments provided)
    crucible user create --orcid 0000-0002-1825-0097 \\
        --username jane-doe --first-name "Jane" --last-name "Doe" \\
        --email "jane@example.com" \\
        --projects project1,project2

    # Create a human user without an ORCID; the API assigns an MFID
    crucible user create --username test-user-one \\
        --first-name "Test" --last-name "User One"
"""
    )

    parser.add_argument('--orcid',                 metavar='ORCID',    help='Optional human ORCID; omit to let the API assign an MFID')
    parser.add_argument('-f', '--first-name',  dest='first_name', metavar='NAME',     help='First name. If not provided, will prompt interactively.')
    parser.add_argument('-l', '--last-name',   dest='last_name',  metavar='NAME',     help='Last name. If not provided, will prompt interactively.')
    parser.add_argument('--email',                 metavar='EMAIL',    help='Email address (optional)')
    parser.add_argument('-u', '--username', metavar='USERNAME', help='Username (required, 3-24 chars, starts with a letter; lowercase letters, digits, hyphens, and underscores)')
    parser.add_argument('-p', '--projects',         metavar='IDS',      help='Comma-separated project IDs (optional)')

    parser.set_defaults(func=_execute_create)


def _register_list(subparsers):
    """Register the 'user list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List visible users',
        description='List public-safe users visible to the authenticated caller',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user list
    crucible user list --limit 50
"""
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=_config.default_limit,
        metavar='N',
        help=f'Maximum number of users to return (default: {_config.default_limit})'
    )

    parser.add_argument('-u', '--username', metavar='USERNAME', default=None,
                        help='Filter by exact username')

    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')

    parser.set_defaults(func=_execute_list)


def _show_user(user):
    """Display user fields."""
    _p = term.field_printer(16)

    full_name = term.fmt_name(user, fallback_username=False)
    uid = user.get('unique_id')

    term.header("User")
    _p("Username", user.get('username') or term.dim('(not set)'))
    _p("Name",     full_name)
    _p(term.user_id_label(uid), term.user_id_link(uid))
    if 'email' in user:
        email = term.dim('(not set)') if user['email'] is None else user['email']
        _p("Email", email)
    if user.get('is_service_account'):
        _p("Type", "service account")


def _execute_get(args):
    """Execute the 'user get' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import parse_user_ref
    import warnings

    orcid    = getattr(args, 'orcid', None)
    username = getattr(args, 'username', None)
    email    = getattr(args, 'email', None)
    user_ref = getattr(args, 'user', None)

    if orcid or username or email:
        warnings.warn(
            "--orcid/--username/--email are deprecated; pass the identifier "
            "positionally instead: crucible user get USER",
            DeprecationWarning, stacklevel=2,
        )
        ref_kwargs = {'orcid': orcid, 'username': username, 'email': email}
        identifier = orcid or username or email
    elif user_ref:
        ref_kwargs = parse_user_ref(user_ref)
        identifier = user_ref
    else:
        logger.error("Provide a user identifier: crucible user get USER")
        sys.exit(1)

    try:
        client = CrucibleClient()
        user = client.users.get(**ref_kwargs)

        if user is None:
            logger.error(f"User not found: {identifier}")
            sys.exit(1)

        if getattr(args, 'json', False):
            import json
            print(json.dumps(user, indent=2, default=str))
        else:
            _show_user(user)

    except Exception as e:
        from .helpers import fail
        fail("retrieving user", e, args)


def _execute_create(args):
    """Execute the 'user create' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import (
        prompt_optional,
        prompt_required,
        prompt_username,
        validate_email,
        validate_orcid,
        validate_project_ids,
    )
    # Interactive mode if required arguments are missing
    orcid = args.orcid
    first_name = args.first_name
    last_name = args.last_name
    username = args.username
    email = args.email
    projects = args.projects

    interactive = first_name is None or last_name is None or username is None
    if interactive:
        term.header("Create User")
        print("")

    if first_name is None:
        first_name = prompt_required("First name", option='--first-name')

    if last_name is None:
        last_name = prompt_required("Last name", option='--last-name')

    if username is None:
        username = prompt_username()

    if interactive:
        if orcid is None:
            orcid = prompt_optional(
                "ORCID",
                validator=validate_orcid,
                hint="Enter to generate an MFID",
            )

        if email is None:
            email = prompt_optional("Email", validator=validate_email)

        if projects is None:
            projects = prompt_optional(
                "Project IDs",
                validator=validate_project_ids,
                hint="comma-separated",
            )

    try:
        from crucible.models import User
        from ..utils.identifiers import validate_username

        username = validate_username(username)
        if email is not None:
            email = validate_email(email)
        if projects is not None:
            projects = validate_project_ids(projects)
        client = CrucibleClient()

        user = User(
            unique_id=orcid,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email or None,
        )
        project_ids = [p.strip() for p in projects.split(',')] if projects else []
        result = client.users.create(user, project_ids=project_ids)

        term.success("User created", args)
        _show_user(result)

    except Exception as e:
        from .helpers import fail
        fail("creating user", e, args)


def _register_update(subparsers):
    """Register the 'user update' subcommand."""
    parser = subparsers.add_parser(
        'update',
        help='Update a user record',
        description='Partially update a user record (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user update 0000-0002-1825-0097 --first-name Jane
    crucible user update fabrice --email jane@example.com --last-name Smith
"""
    )
    parser.add_argument('user', metavar='USER', help='ORCID, MFID, username, or email of the user to update')
    parser.add_argument('-f', '--first-name',  dest='first_name',    metavar='NAME',     help='First name')
    parser.add_argument('-l', '--last-name',   dest='last_name',     metavar='NAME',     help='Last name')
    parser.add_argument('--email',             dest='email',          metavar='EMAIL',    help='Email address')
    parser.add_argument('-u', '--username',    dest='username',       metavar='USERNAME', help='Username')
    parser.add_argument('--clear-username',    dest='clear_username', action='store_true',
                        help='Remove the username (set to null)')
    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'user update' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import resolve_user_id

    fields = {k: v for k, v in {
        'first_name':         args.first_name,
        'last_name':          args.last_name,
        'email':              args.email,
        'username':           args.username,
    }.items() if v is not None}

    if getattr(args, 'clear_username', False):
        fields['username'] = None

    if not fields:
        logger.error("No fields to update. Provide at least one of: --first-name, --last-name, --email, --username, --clear-username")
        sys.exit(1)

    try:
        client = CrucibleClient()
        user_id = resolve_user_id(client, args.user)
        result = client.users.update(user_id, **fields)
        term.success("User updated", args)
        _show_user(result)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        sys.exit(1)




def _register_edit(subparsers):
    parser = subparsers.add_parser(
        'edit',
        help='Edit a user record in your editor',
        description='Open a user record in your editor and apply changes on save (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user edit 0000-0002-1825-0097
    crucible user edit fabrice
    crucible user edit user@lbl.gov
""",
    )
    parser.add_argument('user', metavar='USER', nargs='?', default=None,
                        help='ORCID, MFID, username, or email of the user')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--orcid',    '-o', metavar='ORCID',    help='(deprecated, use positional USER)')
    group.add_argument('--username', '-u', metavar='USERNAME', help='(deprecated, use positional USER)')
    group.add_argument('--email',    '-e', metavar='EMAIL',    help='(deprecated, use positional USER)')
    parser.set_defaults(func=_execute_edit)


def _execute_edit(args):
    """Execute the 'user edit' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import parse_user_ref
    import warnings

    orcid    = getattr(args, 'orcid', None)
    username = getattr(args, 'username', None)
    email    = getattr(args, 'email', None)
    user_ref = getattr(args, 'user', None)

    if orcid or username or email:
        warnings.warn(
            "--orcid/--username/--email are deprecated; pass the identifier "
            "positionally instead: crucible user edit USER",
            DeprecationWarning, stacklevel=2,
        )
        ref_kwargs = {'orcid': orcid, 'username': username, 'email': email}
    elif user_ref:
        ref_kwargs = parse_user_ref(user_ref)
    else:
        logger.error("Provide a user identifier: crucible user edit USER")
        sys.exit(1)

    try:
        client = CrucibleClient()
        user = client.users.get(**ref_kwargs)
        if user is None:
            logger.error("User not found")
            sys.exit(1)

        user_id = user.get('unique_id')
        if not user_id:
            logger.error("Could not determine canonical user ID")
            sys.exit(1)

        _EDITABLE = ('first_name', 'last_name', 'email', 'username')
        original = {k: user.get(k) for k in _EDITABLE}

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

        result = client.users.update(user_id, **changes)
        term.header("Changes")
        term.diff(original, {k: result.get(k) for k in changes})

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_add_access_group(subparsers):
    """Register the 'user add-access-group' subcommand."""
    parser = subparsers.add_parser(
        'add-access-group',
        help='Deprecated generic access-group membership command',
        description=(
            'Deprecated. Use project add-user for projects or instrument bind-sa '
            'for instrument operators.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user add-access-group 0000-0002-1825-0097 my-group
    crucible user add-access-group fabrice my-group
""",
    )
    parser.add_argument('user',       metavar='USER',  help='ORCID, MFID, username, or email of the user')
    parser.add_argument('group_name', metavar='GROUP', help='Access group name')
    parser.set_defaults(func=_execute_add_access_group)


def _execute_add_access_group(args):
    """Execute the 'user add-access-group' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import resolve_user_id
    try:
        client = CrucibleClient()
        user_id = resolve_user_id(client, args.user)
        client.users.add_to_access_group(user_id, args.group_name)
        term.success(f"Added {args.user} to access group '{args.group_name}'", args)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_remove_access_group(subparsers):
    """Register the 'user remove-access-group' subcommand."""
    parser = subparsers.add_parser(
        'remove-access-group',
        help='Deprecated generic access-group membership command',
        description=(
            'Deprecated. Use project remove-user for projects or instrument unbind-sa '
            'for instrument operators.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user remove-access-group 0000-0002-1825-0097 my-group
    crucible user remove-access-group fabrice my-group
"""
    )
    parser.add_argument('user',       metavar='USER',  help='ORCID, MFID, username, or email of the user')
    parser.add_argument('group_name', metavar='GROUP', help='Access group name')
    parser.set_defaults(func=_execute_remove_access_group)


def _execute_remove_access_group(args):
    """Execute the 'user remove-access-group' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import resolve_user_id
    try:
        client = CrucibleClient()
        user_id = resolve_user_id(client, args.user)
        client.users.remove_from_access_group(user_id, args.group_name)
        term.success(f"Removed {args.user} from access group '{args.group_name}'", args)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error removing user from access group: {e}")
        sys.exit(1)


def _execute_list(args):
    """Execute the 'user list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        username_filter = getattr(args, 'username', None)
        kwargs = {'username': username_filter} if username_filter else {}
        users = client.users.list(limit=args.limit, **kwargs)

        if getattr(args, 'json', False):
            print(json.dumps(users, indent=2, default=str))
            return

        term.header(f"Users ({len(users)})")

        if not users:
            print(f"  {term.dim('No users found.')}")
            return

        rows = []
        for user in users:
            name = term.user_link(
                term.fmt_name(user, default='-', fallback_username=False),
                user.get('unique_id'),
            )
            user_id  = term.cyan(user.get('unique_id')) if user.get('unique_id') else '-'
            username = user.get('username') or '-'
            rows.append((username, name, user_id))
        term.table(
            rows,
            ['Username', 'Name', 'ID'],
            max_widths=[24, 25, 26],
            min_widths=[24, 4, 26],
        )

    except Exception as e:
        from .helpers import fail
        fail("listing users", e, args)


def _register_list_datasets(subparsers):
    """Register the 'user list-datasets' subcommand."""
    parser = subparsers.add_parser(
        'list-datasets',
        help='List datasets accessible to a user',
        description=(
            'List dataset MFIDs accessible to a user. Inspecting another user '
            'requires platform-administrator permissions.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user list-datasets 0000-0002-1825-0097
    crucible user list-datasets fabrice
"""
    )
    parser.add_argument('user', metavar='USER', help='ORCID, MFID, username, or email of the user')
    parser.add_argument(
        '--limit', type=int, default=_config.default_limit, metavar='N',
        help=f'Maximum number of datasets to return (default: {_config.default_limit})',
    )
    parser.set_defaults(func=_execute_list_datasets)


def _register_check_access(subparsers):
    """Register the 'user check-access' subcommand."""
    parser = subparsers.add_parser(
        'check-access',
        help='Check user access to a dataset',
        description='Show a user\'s effective access role on a dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user check-access 0000-0002-1825-0097 0tcbwt4cp9x1z000bazhkv5gkg
    crucible user check-access fabrice 0tcbwt4cp9x1z000bazhkv5gkg
"""
    )
    parser.add_argument('user', metavar='USER', help='ORCID, MFID, username, or email of the user')
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.set_defaults(func=_execute_check_access)


def _register_list_access_groups(subparsers):
    """Register the 'user list-access-groups' subcommand."""
    import argparse
    parser = subparsers.add_parser(
        'list-access-groups',
        help='List access groups for a user',
        description="List the access groups a user belongs to",
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user list-access-groups 0000-0002-1825-0097
    crucible user list-access-groups fabrice
"""
    )
    parser.add_argument('user', metavar='USER', help='ORCID, MFID, username, or email of the user')
    parser.set_defaults(func=_execute_list_access_groups)


def _register_list_projects(subparsers):
    """Register the 'user list-projects' subcommand."""
    import argparse
    parser = subparsers.add_parser(
        'list-projects',
        help='List projects for a user',
        description='List projects a user is associated with',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible user list-projects 0000-0002-1825-0097
    crucible user list-projects fabrice
"""
    )
    parser.add_argument('user', metavar='USER', help='ORCID, MFID, username, or email of the user')
    parser.set_defaults(func=_execute_list_projects)


def _execute_list_datasets(args):
    """Execute the 'user list-datasets' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        datasets = client.datasets.list(
            accessible_to_user=args.user,
            limit=args.limit,
        )
        dataset_ids = [dataset['unique_id'] for dataset in datasets]

        term.header(f"Datasets · {args.user} ({len(dataset_ids)})")
        if not dataset_ids:
            print(f"  {term.dim('No datasets found.')}")
            return
        for dsid in dataset_ids:
            print(f"  {term.cyan(dsid)}")

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("listing user datasets", e, args)


def _execute_check_access(args):
    """Execute the 'user check-access' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        access = client.users.check_dataset_access(args.user, args.dataset_id)

        _p = term.field_printer(14)

        term.header(f"Access · {args.dataset_id}")
        _p("User", access.user_id)
        _p("Effective", access.effective_access)

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("checking access", e, args)


def _execute_list_access_groups(args):
    """Execute the 'user list-access-groups' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import resolve_user_id
    try:
        client = CrucibleClient()
        user_id = resolve_user_id(client, args.user)
        groups = client.users.list_access_groups(user_id)

        term.header(f"Access Groups · {args.user} ({len(groups)})")
        if not groups:
            print(f"  {term.dim('No access groups found.')}")
            return
        for g in groups:
            print(f"  {g}")

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("retrieving access groups", e, args)


def _execute_list_projects(args):
    """Execute the 'user list-projects' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import resolve_user_id
    try:
        client = CrucibleClient()
        user_id = resolve_user_id(client, args.user)
        projects = client.users.get_projects(user_id)

        term.header(f"Projects · {args.user} ({len(projects)})")
        if not projects:
            print(f"  {term.dim('No projects found.')}")
            return

        from .helpers import project_explorer_url
        def _project_row(project):
            project_id = project.get('project_id')
            title = project.get('title')
            url = project_explorer_url(project_id)
            return (
                project_id if title else term.project_link(project_id, url),
                term.navigation_link(title, url) if title else '-',
                project.get('organization') or '-',
            )
        rows = [_project_row(project) for project in projects]
        term.table(
            rows,
            ['Project ID', 'Title', 'Organization'],
            max_widths=[25, 30, 20],
            min_widths=[25, 5, 12],
        )

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("retrieving user projects", e, args)
