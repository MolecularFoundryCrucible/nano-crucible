#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User subcommand for Crucible CLI.

Provides user-related operations: get, create.
"""

import sys
import logging
import json
import re

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
    _register_create(user_subparsers)
    _register_list(user_subparsers)
    _register_list_datasets(user_subparsers)
    _register_check_access(user_subparsers)
    _register_list_access_groups(user_subparsers)
    _register_list_projects(user_subparsers)


def _register_get(subparsers):
    """Register the 'user get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get user by ORCID or email',
        description='Retrieve user information (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible user get --orcid 0000-0002-1825-0097
    crucible user get --email user@example.com
"""
    )

    parser.add_argument(
        '--orcid',
        metavar='ORCID',
        help='User ORCID identifier (format: 0000-0000-0000-000X)'
    )

    parser.add_argument(
        '--email',
        metavar='EMAIL',
        help='User email address'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'user create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new user',
        description='Add a new user to Crucible (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible user create

    # Command-line mode (all arguments provided)
    crucible user create --orcid 0000-0002-1825-0097 \\
        --first-name "Jane" --last-name "Doe" \\
        --email "jane@example.com" \\
        --projects project1,project2
"""
    )

    parser.add_argument(
        '--orcid',
        metavar='ORCID',
        help='User ORCID identifier (format: 0000-0000-0000-000X). If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '--first-name',
        dest='first_name',
        metavar='NAME',
        help='First name. If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '--last-name',
        dest='last_name',
        metavar='NAME',
        help='Last name. If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '--email',
        metavar='EMAIL',
        help='Email address (optional)'
    )

    parser.add_argument(
        '--lbl-email',
        dest='lbl_email',
        metavar='EMAIL',
        help='LBL email address (optional)'
    )

    parser.add_argument(
        '--projects', '-p',
        metavar='IDS',
        help='Comma-separated list of project IDs to associate with user (optional)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_create)


def _register_list(subparsers):
    """Register the 'user list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List all users',
        description='List all users in the system (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
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

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_list)


def _show_user(user):
    """Display user fields."""
    _p = term.field_printer(16)

    name_parts = [user.get('first_name') or '', user.get('last_name') or '']
    full_name = ' '.join(p for p in name_parts if p) or None

    term.header("User")
    _p("Name",            full_name)
    _p("ORCID",           term.orcid_link(user.get('orcid')))
    _p("Email",           user.get('email'))
    _p("LBL Email",       user.get('lbl_email'))
    _p("Employee Number", user.get('employee_number'))
    _p("ID",              user.get('id'))


def _execute_get(args):
    """Execute the 'user get' subcommand."""
    from crucible.client import CrucibleClient
    if not args.orcid and not args.email:
        logger.error("Error: Either --orcid or --email must be provided")
        sys.exit(1)

    try:
        client = CrucibleClient()
        user = client.users.get(orcid=args.orcid, email=args.email)

        if user is None:
            identifier = args.orcid if args.orcid else args.email
            logger.error(f"User not found: {identifier}")
            sys.exit(1)

        _show_user(user)

    except Exception as e:
        logger.error(f"Error retrieving user: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'user create' subcommand."""
    from crucible.client import CrucibleClient
    # Interactive mode if required arguments are missing
    orcid = args.orcid
    first_name = args.first_name
    last_name = args.last_name
    email = args.email
    lbl_email = args.lbl_email
    projects = args.projects

    interactive = orcid is None or first_name is None or last_name is None
    if interactive:
        term.header("Create User")
        print("")

    # Prompt for ORCID
    if orcid is None:
        while True:
            orcid = input("ORCID (format: 0000-0000-0000-000X): ").strip()
            if orcid:
                # Validate ORCID format
                if re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$', orcid):
                    break
                else:
                    logger.error("Invalid ORCID format. Expected: 0000-0000-0000-000X")
            else:
                logger.error("ORCID is required.")

    # Prompt for first name
    if first_name is None:
        while True:
            first_name = input("First name: ").strip()
            if first_name:
                break
            else:
                logger.error("First name is required.")

    # Prompt for last name
    if last_name is None:
        while True:
            last_name = input("Last name: ").strip()
            if last_name:
                break
            else:
                logger.error("Last name is required.")

    # Optional fields — only prompt in interactive mode
    if interactive:
        if email is None:
            email_input = input("Email (optional, press Enter to skip): ").strip()
            if email_input:
                if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_input):
                    email = email_input
                else:
                    logger.warning("Invalid email format. Skipping.")

        if lbl_email is None:
            lbl_email_input = input("LBL Email (optional, press Enter to skip): ").strip()
            if lbl_email_input:
                if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', lbl_email_input):
                    lbl_email = lbl_email_input
                else:
                    logger.warning("Invalid email format. Skipping.")

        if projects is None:
            projects_input = input("Project IDs (comma-separated, optional, press Enter to skip): ").strip()
            if projects_input:
                projects = projects_input

    try:
        from crucible.models import User
        client = CrucibleClient()

        user = User(
            orcid=orcid,
            first_name=first_name,
            last_name=last_name,
            email=email or None,
            lbl_email=lbl_email or None,
        )
        project_ids = [p.strip() for p in projects.split(',')] if projects else []
        result = client.users.create(user, project_ids=project_ids)

        logger.info("✓ User created")
        _show_user(result)

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list(args):
    """Execute the 'user list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        users = client.users.list(limit=args.limit)

        term.header(f"Users ({len(users)})")

        if not users:
            print(f"  {term.dim('No users found.')}")
            return

        rows = []
        for user in users:
            name_parts = [user.get('first_name') or '', user.get('last_name') or '']
            name  = ' '.join(p for p in name_parts if p) or '—'
            orcid = user.get('orcid') or '—'
            email = user.get('email') or user.get('lbl_email') or '—'
            rows.append((name, orcid, email))
        term.table(rows, ['Name', 'ORCID', 'Email'], max_widths=[25, 19, 35])

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_list_datasets(subparsers):
    """Register the 'user list-datasets' subcommand."""
    parser = subparsers.add_parser(
        'list-datasets',
        help='List datasets accessible to a user',
        description='List dataset IDs the user has access to (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible user list-datasets 0000-0002-1825-0097
"""
    )
    parser.add_argument('orcid', metavar='ORCID', help='User ORCID identifier')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_datasets)


def _register_check_access(subparsers):
    """Register the 'user check-access' subcommand."""
    parser = subparsers.add_parser(
        'check-access',
        help='Check user access to a dataset',
        description='Check read/write permissions for a user on a specific dataset (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible user check-access 0000-0002-1825-0097 0tcbwt4cp9x1z000bazhkv5gkg
"""
    )
    parser.add_argument('orcid', metavar='ORCID', help='User ORCID identifier')
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_check_access)


def _register_list_access_groups(subparsers):
    """Register the 'user list-access-groups' subcommand."""
    import argparse
    parser = subparsers.add_parser(
        'list-access-groups',
        help='List access groups for a user',
        description="List the access groups a user belongs to",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible user list-access-groups 0000-0002-1825-0097
"""
    )
    parser.add_argument('orcid', metavar='ORCID', help='User ORCID identifier')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_access_groups)


def _register_list_projects(subparsers):
    """Register the 'user list-projects' subcommand."""
    import argparse
    parser = subparsers.add_parser(
        'list-projects',
        help='List projects for a user',
        description='List projects a user is associated with',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible user list-projects 0000-0002-1825-0097
"""
    )
    parser.add_argument('orcid', metavar='ORCID', help='User ORCID identifier')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_projects)


def _execute_list_datasets(args):
    """Execute the 'user list-datasets' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        dataset_ids = client.users.list_datasets(args.orcid)

        term.header(f"Datasets · {args.orcid} ({len(dataset_ids)})")
        if not dataset_ids:
            print(f"  {term.dim('No datasets found.')}")
            return
        for dsid in dataset_ids:
            print(f"  {term.cyan(dsid)}")

    except Exception as e:
        logger.error(f"Error listing user datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_check_access(args):
    """Execute the 'user check-access' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        perms = client.users.check_dataset_access(args.orcid, args.dataset_id)

        _p = term.field_printer(8)

        term.header(f"Access · {args.dataset_id}")
        _p("Read",  "yes" if perms.get('read')  else "no")
        _p("Write", "yes" if perms.get('write') else "no")

    except Exception as e:
        logger.error(f"Error checking access: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_access_groups(args):
    """Execute the 'user get-access-groups' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        groups = client.users.list_access_groups(args.orcid)

        term.header(f"Access Groups · {args.orcid} ({len(groups)})")
        if not groups:
            print(f"  {term.dim('No access groups found.')}")
            return
        for g in groups:
            print(f"  {g}")

    except Exception as e:
        logger.error(f"Error retrieving access groups: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_projects(args):
    """Execute the 'user get-projects' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        projects = client.users.get_projects(args.orcid)

        term.header(f"Projects · {args.orcid} ({len(projects)})")
        if not projects:
            print(f"  {term.dim('No projects found.')}")
            return

        rows = [
            (
                p.get('project_id') or '—',
                p.get('title') or '—',
                p.get('organization') or '—',
            )
            for p in projects
        ]
        term.table(rows, ['ID', 'Title', 'Organization'], max_widths=[20, 30, 20])

    except Exception as e:
        logger.error(f"Error retrieving user projects: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
