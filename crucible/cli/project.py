#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project subcommand for Crucible CLI.

Provides project-related operations: list, get, create.
"""

import sys
import logging
import json

logger = logging.getLogger(__name__)

from . import term

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def register_subcommand(subparsers):
    """
    Register the project subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'project',
        help='Project operations (list, get, create)',
        description='Manage Crucible projects',
    )

    # Project subcommands
    project_subparsers = parser.add_subparsers(
        title='project commands',
        dest='project_command',
        help='Available project operations'
    )

    # Register individual project commands
    _register_list(project_subparsers)
    _register_get(project_subparsers)
    _register_create(project_subparsers)
    _register_list_users(project_subparsers)
    _register_add_user(project_subparsers)


def _register_list(subparsers):
    """Register the 'project list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List projects',
        description='List all projects'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        metavar='N',
        help='Maximum number of results to return (default: 100)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'project get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get project by ID',
        description='Retrieve project information'
    )

    project_id_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )
    # Disable file completion for project_id
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'project create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new project',
        description='Create a new project in Crucible',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible project create

    # Command-line mode
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov"
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov" \\
        --title "Silicon Wafer Study" --lead-name "Jane Doe"
"""
    )

    parser.add_argument(
        '--project-id', '-id',
        required=False,
        default=None,
        metavar='ID',
        help='Unique project identifier (e.g., "my-project"). If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '-o', '--organization',
        required=False,
        default=None,
        metavar='ORG',
        help='Organization name (e.g., "LBNL", "Argonne", "Molecular Foundry"). If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '-e', '--email',
        required=False,
        default=None,
        metavar='EMAIL',
        dest='project_lead_email',
        help='Project lead email address. If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '--title',
        required=False,
        default=None,
        metavar='TITLE',
        help='Human-readable project title (optional)'
    )

    parser.add_argument(
        '--lead-name',
        required=False,
        default=None,
        metavar='NAME',
        dest='project_lead_name',
        help='Project lead full name (optional)'
    )

    parser.add_argument(
        '--status',
        required=False,
        default=None,
        metavar='STATUS',
        help='Project status (optional)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_create)


def _register_list_users(subparsers):
    """Register the 'project list-users' subcommand."""
    import argparse

    def _add_args(p):
        pid_arg = p.add_argument('project_id', metavar='PROJECT_ID', help='Project ID')
        if ARGCOMPLETE_AVAILABLE:
            pid_arg.completer = argcomplete.completers.SuppressCompleter()
        p.add_argument('--limit', type=int, default=100, metavar='N',
                       help='Maximum number of results to return (default: 100)')
        p.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    parser = subparsers.add_parser(
        'list-users',
        help='List users in a project',
        description='List all users associated with a project (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible project list-users my-project
    crucible project list-users lammps-test
"""
    )
    _add_args(parser)
    parser.set_defaults(func=_execute_list_users)


def _register_add_user(subparsers):
    """Register the 'project add-user' subcommand."""
    parser = subparsers.add_parser(
        'add-user',
        help='Add a user to a project',
        description='Add a user to a project by ORCID (requires admin permissions)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible project add-user my-project --orcid 0000-0002-1825-0097
    crucible project add-user lammps-test --orcid 0000-0001-2345-6789
"""
    )

    project_id_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )
    # Disable file completion for project_id
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--orcid',
        required=True,
        metavar='ORCID',
        help='User ORCID identifier (format: 0000-0000-0000-000X)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_add_user)


def _execute_list(args):
    """Execute the 'project list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        projects = client.projects.list(limit=args.limit)

        term.header(f"Projects ({len(projects)})")
        if not projects:
            print(f"  {term.dim('No projects found.')}")
        else:
            rows = [
                (
                    p.get('project_id') or '—',
                    p.get('title') or '—',
                    p.get('organization') or '—',
                    p.get('project_lead_email') or '—',
                )
                for p in projects
            ]
            term.table(rows, ['ID', 'Title', 'Organization', 'Lead Email'],
                       max_widths=[20, 30, 20, 30])

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _show_project(project):
    """Display project fields."""
    W = 14

    def _p(label, value):
        print(f"  {label:<{W}}{value if value not in (None, '') else '—'}")

    term.header("Project")
    pid = project.get('project_id')
    _p("ID",           term.cyan(pid) if pid else None)
    _p("Title",        project.get('title'))
    _p("Organization", project.get('organization'))
    _p("Lead",         project.get('project_lead_name'))
    _p("Lead Email",   project.get('project_lead_email'))
    _p("Status",       project.get('status'))


def _execute_get(args):
    """Execute the 'project get' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        project = client.projects.get(args.project_id)

        if project is None:
            logger.error(f"Project not found: {args.project_id}")
            sys.exit(1)

        _show_project(project)

    except Exception as e:
        logger.error(f"Error retrieving project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'project create' subcommand."""
    import re
    from crucible.client import CrucibleClient
    # Interactive mode if any required arguments are missing
    project_id = args.project_id
    organization = args.organization
    project_lead_email = args.project_lead_email
    title = args.title
    project_lead_name = args.project_lead_name
    status = args.status

    interactive = project_id is None or organization is None or project_lead_email is None
    if interactive:
        term.header("Create Project")
        print("")

    # Prompt for project_id
    if project_id is None:
        while True:
            project_id = input("Project ID (e.g., my-project): ").strip()
            if project_id:
                # Validate project_id format (alphanumeric, hyphens, underscores)
                if re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                    break
                else:
                    logger.error("Invalid project ID. Use only letters, numbers, hyphens, and underscores.")
            else:
                logger.error("Project ID is required.")

    # Prompt for organization
    if organization is None:
        while True:
            organization = input("Organization (e.g., LBNL, Argonne): ").strip()
            if organization:
                break
            else:
                logger.error("Organization is required.")

    # Prompt for project lead email
    if project_lead_email is None:
        while True:
            project_lead_email = input("Project lead email: ").strip()
            if project_lead_email:
                # Basic email validation
                if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', project_lead_email):
                    break
                else:
                    logger.error("Invalid email format.")
            else:
                logger.error("Project lead email is required.")

    # Optional fields — only prompt in interactive mode
    if interactive:
        if title is None:
            val = input("Project title (optional, press Enter to skip): ").strip()
            title = val or None

        if project_lead_name is None:
            val = input("Project lead name (optional, press Enter to skip): ").strip()
            project_lead_name = val or None

        if status is None:
            val = input("Status (optional, press Enter to skip): ").strip()
            status = val or None

    try:
        from crucible.models import Project
        client = CrucibleClient()

        # Check if project already exists
        existing = client.projects.get(project_id)
        if existing is not None:
            logger.warning(f"Project '{project_id}' already exists.")
            _show_project(existing)
            return

        # Build Project model and create
        project = Project(
            project_id=project_id,
            organization=organization,
            project_lead_email=project_lead_email,
            title=title,
            project_lead_name=project_lead_name,
            status=status,
        )
        result = client.projects.create(project)

        logger.info("✓ Project created")
        _show_project(result)

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_users(args):
    """Execute the 'project get-users' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        users = client.projects.get_users(args.project_id, limit=args.limit)

        term.header(f"Users · {args.project_id} ({len(users)})")
        if not users:
            print(f"  {term.dim('No users found.')}")
        else:
            rows = []
            for u in users:
                name_parts = [u.get('first_name') or '', u.get('last_name') or '']
                name  = ' '.join(p for p in name_parts if p) or '—'
                orcid = u.get('orcid') or '—'
                email = u.get('email') or u.get('lbl_email') or '—'
                rows.append((name, orcid, email))
            term.table(rows, ['Name', 'ORCID', 'Email'], max_widths=[25, 19, 35])

    except Exception as e:
        logger.error(f"Error listing project users: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_add_user(args):
    """Execute the 'project add-user' subcommand."""
    import re
    from crucible.client import CrucibleClient
    # Validate ORCID format
    if not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$', args.orcid):
        logger.error(f"Invalid ORCID format: {args.orcid}")
        logger.error("Expected format: 0000-0000-0000-000X")
        sys.exit(1)

    try:
        client = CrucibleClient()
        result = client.projects.add_user(args.orcid, args.project_id)

        logger.info(f"\n✓ User {args.orcid} added to project {args.project_id} successfully!")

    except Exception as e:
        logger.error(f"Error adding user to project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
