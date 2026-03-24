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
        epilog="""
Examples:
    crucible user list
    crucible user list --limit 50
"""
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        metavar='N',
        help='Maximum number of users to return (default: 100)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_list)


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

        logger.info("\n=== User Information ===")
        if user.get('orcid'):
            logger.info(f"ORCID: {user['orcid']}")
        if user.get('first_name') or user.get('last_name'):
            name_parts = []
            if user.get('first_name'):
                name_parts.append(user['first_name'])
            if user.get('last_name'):
                name_parts.append(user['last_name'])
            logger.info(f"Name: {' '.join(name_parts)}")
        if user.get('email'):
            logger.info(f"Email: {user['email']}")
        if user.get('lbl_email'):
            logger.info(f"LBL Email: {user['lbl_email']}")
        if user.get('id'):
            logger.info(f"ID: {user['id']}")

        if getattr(args, "debug", False):
            logger.debug(f"\nFull user data: {json.dumps(user, indent=2)}")

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

    if orcid is None or first_name is None or last_name is None:
        logger.info("\n=== Interactive User Creation ===")
        logger.info("Please provide the following information:\n")

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

    # Prompt for email (optional)
    if email is None:
        email_input = input("Email (optional, press Enter to skip): ").strip()
        if email_input:
            # Basic email validation
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_input):
                email = email_input
            else:
                logger.warning("Invalid email format. Skipping.")

    # Prompt for LBL email (optional)
    if lbl_email is None:
        lbl_email_input = input("LBL Email (optional, press Enter to skip): ").strip()
        if lbl_email_input:
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', lbl_email_input):
                lbl_email = lbl_email_input
            else:
                logger.warning("Invalid email format. Skipping.")

    # Prompt for projects (optional)
    if projects is None:
        projects_input = input("Project IDs (comma-separated, optional, press Enter to skip): ").strip()
        if projects_input:
            projects = projects_input

    # Build user_info dict
    user_info = {
        "orcid": orcid,
        "first_name": first_name,
        "last_name": last_name,
        "projects": [p.strip() for p in projects.split(',')] if projects else []
    }

    if email:
        user_info["email"] = email
    if lbl_email:
        user_info["lbl_email"] = lbl_email

    try:
        logger.info("\n=== Creating User ===")
        client = CrucibleClient()
        result = client.users.create(user_info)

        logger.info(f"\n✓ User created successfully!")
        logger.info(f"ORCID: {result.get('orcid', 'N/A')}")
        if result.get('first_name') or result.get('last_name'):
            name_parts = []
            if result.get('first_name'):
                name_parts.append(result['first_name'])
            if result.get('last_name'):
                name_parts.append(result['last_name'])
            logger.info(f"Name: {' '.join(name_parts)}")
        if result.get('email'):
            logger.info(f"Email: {result['email']}")
        if result.get('id'):
            logger.info(f"ID: {result['id']}")

        if getattr(args, "debug", False):
            logger.debug(f"\nFull result: {json.dumps(result, indent=2)}")

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

        if not users:
            logger.info("No users found.")
            return

        logger.info(f"\n=== Users ({len(users)}) ===\n")

        for i, user in enumerate(users, 1):
            # Format name
            name_parts = []
            if user.get('first_name'):
                name_parts.append(user['first_name'])
            if user.get('last_name'):
                name_parts.append(user['last_name'])
            name = ' '.join(name_parts) if name_parts else 'N/A'

            # Format ORCID
            orcid = user.get('orcid', 'N/A')

            # Format email
            email = user.get('email') or user.get('lbl_email', 'N/A')

            logger.info(f"{i}. {name}")
            logger.info(f"   ORCID: {orcid}")
            logger.info(f"   Email: {email}")

            if args.verbose:
                if user.get('id'):
                    logger.info(f"   ID: {user['id']}")
                if user.get('creation_time'):
                    logger.info(f"   Created: {user['creation_time']}")

            logger.info("")

        if getattr(args, "debug", False):
            logger.debug(f"\nFull data: {json.dumps(users, indent=2)}")

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

        if not dataset_ids:
            logger.info(f"No datasets found for user {args.orcid}.")
            return

        logger.info(f"\n=== Datasets accessible to {args.orcid} ({len(dataset_ids)}) ===\n")
        for dsid in dataset_ids:
            logger.info(f"  {dsid}")

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

        logger.info(f"\n=== Access for {args.orcid} on {args.dataset_id} ===\n")
        logger.info(f"  Read:  {'yes' if perms.get('read') else 'no'}")
        logger.info(f"  Write: {'yes' if perms.get('write') else 'no'}")

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

        if not groups:
            logger.info(f"No access groups found for user {args.orcid}.")
            return

        logger.info(f"\n=== Access Groups for {args.orcid} ({len(groups)}) ===\n")
        for g in groups:
            logger.info(f"  {g}")

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

        if not projects:
            logger.info(f"No projects found for user {args.orcid}.")
            return

        logger.info(f"\n=== Projects for {args.orcid} ({len(projects)}) ===\n")
        for p in projects:
            pid = p.get('project_id', 'N/A')
            title = p.get('title') or p.get('project_id', '')
            logger.info(f"  {pid}  {title}")
            if args.verbose:
                logger.info(f"    org={p.get('organization')}  lead={p.get('project_lead_email')}")

    except Exception as e:
        logger.error(f"Error retrieving user projects: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
