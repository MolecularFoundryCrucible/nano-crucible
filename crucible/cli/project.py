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
from ..config import config as _config

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
    _register_update(project_subparsers)
    _register_edit(project_subparsers)
    _register_list_users(project_subparsers)
    _register_add_user(project_subparsers)
    _register_remove_user(project_subparsers)


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
        default=_config.default_limit,
        metavar='N',
        help=f'Maximum number of results to return (default: {_config.default_limit})'
    )

    parser.add_argument(
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in results'
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
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in output'
    )

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
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible project create

    # Command-line mode
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov"
    crucible project create --project-id my-project -o "LBNL" -e "0000-0002-1825-0097"
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov" \\
        --title "Silicon Wafer Study"
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
        '-e', '--lead',
        required=False,
        default=None,
        metavar='EMAIL_OR_ORCID',
        dest='project_lead_email',
        help='Project lead email or ORCID. If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '--title',
        required=False,
        default=None,
        metavar='TITLE',
        help='Human-readable project title (optional)'
    )

    parser.add_argument(
        '--status',
        required=False,
        default=None,
        metavar='STATUS',
        help='Project status (optional)'
    )

    parser.add_argument(
        '--metadata',
        dest='metadata',
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
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
        p.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                       help=f'Maximum number of results to return (default: {_config.default_limit})')
        p.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    parser = subparsers.add_parser(
        'list-users',
        help='List users in a project',
        description='List all users associated with a project (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
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
        description='Add a user to a project by ORCID or email (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project add-user my-project --orcid 0000-0002-1825-0097
    crucible project add-user my-project --email user@lbl.gov
"""
    )

    project_id_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--orcid',
        metavar='ORCID',
        help='User ORCID identifier (format: 0000-0000-0000-000X)'
    )
    group.add_argument(
        '--email',
        metavar='EMAIL',
        help='User email address'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_add_user)


def _register_update(subparsers):
    """Register the 'project update' subcommand."""
    parser = subparsers.add_parser(
        'update',
        help='Update a project record',
        description='Partially update a project record (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project update my-project --title "New Title"
    crucible project update my-project --status active --organization "Molecular Foundry"
    crucible project update my-project --lead-orcid 0000-0002-1825-0097
"""
    )
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Project ID')
    parser.add_argument('--title',        dest='title',               metavar='TITLE',  help='Project title')
    parser.add_argument('--organization', dest='organization',        metavar='ORG',    help='Organization name')
    parser.add_argument('--status',       dest='status',              metavar='STATUS', help='Project status')
    parser.add_argument('--lead-email',   dest='project_lead_email',  metavar='EMAIL',  help='Project lead email')
    parser.add_argument('--lead-orcid',   dest='project_lead_orcid',  metavar='ORCID',  help='Project lead ORCID')
    parser.add_argument('--metadata',     dest='metadata',            metavar='JSON',
                        help='Scientific metadata as JSON string or path to JSON file')
    parser.add_argument('--overwrite',    action='store_true',
                        help='Replace all existing scientific metadata instead of merging (only with --metadata)')
    parser.set_defaults(func=_execute_update)


def _register_remove_user(subparsers):
    """Register the 'project remove-user' subcommand."""
    parser = subparsers.add_parser(
        'remove-user',
        help='Remove a user from a project',
        description='Remove a user from a project by ORCID or email (requires admin permissions)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project remove-user my-project --orcid 0000-0002-1825-0097
    crucible project remove-user my-project --email user@lbl.gov
"""
    )
    project_id_arg = parser.add_argument(
        'project_id', metavar='PROJECT_ID', help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--orcid', metavar='ORCID', help='User ORCID identifier')
    group.add_argument('--email', metavar='EMAIL', help='User email address')
    parser.set_defaults(func=_execute_remove_user)


def _execute_list(args):
    """Execute the 'project list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        projects = client.projects.list(limit=args.limit,
                                        include_metadata=getattr(args, 'include_metadata', False))

        try:
            from crucible.config import config
            _base = config.graph_explorer_url.rstrip('/')
        except Exception:
            _base = None

        term.header(f"Projects ({len(projects)})")
        if not projects:
            print(f"  {term.dim('No projects found.')}")
        else:
            rows = [
                (
                    term.project_link(p.get('project_id'),
                                      f"{_base}/{p.get('project_id')}" if _base else None),
                    p.get('title') or '-',
                    p.get('organization') or '-',
                    _lead_name(p) or '-',
                )
                for p in projects
            ]
            term.table(rows, ['ID', 'Title', 'Organization', 'Lead'],
                       max_widths=[20, 30, 20, 25])

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _lead_name(project):
    """Return the lead's display name from embedded lead dict, or fallback to project_lead_email."""
    lead = project.get('lead') or {}
    parts = [lead.get('first_name') or '', lead.get('last_name') or '']
    name = ' '.join(p for p in parts if p)
    return name or project.get('project_lead_email') or None


def _show_project(project, include_metadata=False):
    """Display project fields."""
    _p = term.field_printer(14)

    try:
        from crucible.config import config
        _base = config.graph_explorer_url.rstrip('/')
    except Exception:
        _base = None

    lead = project.get('lead') or {}

    term.header("Project")
    pid = project.get('project_id')
    _p("ID",           term.project_link(pid, f"{_base}/{pid}" if _base and pid else None))
    _p("Title",        project.get('title'))
    _p("Organization", project.get('organization'))
    _p("Lead",         _lead_name(project))
    _p("Lead Email",   lead.get('email') or project.get('project_lead_email'))
    _p("Status",       project.get('status'))

    if include_metadata:
        from .helpers import show_scientific_metadata
        show_scientific_metadata(project.get('scientific_metadata'))


def _execute_get(args):
    """Execute the 'project get' subcommand."""
    from crucible.client import CrucibleClient
    include_metadata = getattr(args, 'include_metadata', False) or _config.include_metadata
    try:
        client = CrucibleClient()
        project = client.projects.get(args.project_id,
                                      include_metadata=include_metadata)

        if project is None:
            logger.error(f"Project not found: {args.project_id}")
            sys.exit(1)

        _show_project(project, include_metadata=include_metadata)

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

    # Prompt for project lead (email or ORCID)
    if project_lead_email is None:
        while True:
            project_lead_email = input("Project lead email or ORCID: ").strip()
            if project_lead_email:
                break
            else:
                logger.error("Project lead is required.")

    # Optional fields — only prompt in interactive mode
    if interactive:
        if title is None:
            val = input("Project title (optional, press Enter to skip): ").strip()
            title = val or None

        if status is None:
            val = input("Status (optional, press Enter to skip): ").strip()
            status = val or None

    metadata_dict = None
    if getattr(args, 'metadata', None):
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    try:
        from crucible.models import Project
        client = CrucibleClient()

        # Route to the right field based on format.
        is_orcid = bool(re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$', project_lead_email))
        project = Project(
            project_id=project_id,
            organization=organization,
            project_lead_orcid=project_lead_email if is_orcid else None,
            project_lead_email=None if is_orcid else project_lead_email,
            title=title,
            status=status,
        )
        result = client.projects.create(project, scientific_metadata=metadata_dict)

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
                name  = ' '.join(p for p in name_parts if p) or '-'
                orcid = u.get('orcid') or u.get('unique_id') or '-'
                email = u.get('email') or '-'
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

    orcid = getattr(args, 'orcid', None)
    email = getattr(args, 'email', None)

    if orcid and not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$', orcid):
        logger.error(f"Invalid ORCID format: {orcid}")
        logger.error("Expected format: 0000-0000-0000-000X")
        sys.exit(1)

    try:
        import requests as _req
        client = CrucibleClient()
        users = client.projects.add_user(orcid=orcid, project_id=args.project_id, email=email)

        name = orcid or email
        if isinstance(users, list):
            match = next((u for u in users if
                          (orcid and (u.get('orcid') or u.get('unique_id')) == orcid) or
                          (email and u.get('email') == email)), None)
            if match:
                first = match.get('first_name') or ''
                last  = match.get('last_name') or ''
                name  = ' '.join(p for p in (first, last) if p) or name

        logger.info(f"\n✓ {name} added to project {args.project_id} successfully!")

    except _req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            identifier = orcid or email
            logger.error(f"Not found: check that '{identifier}' has a Crucible account "
                         f"and that project '{args.project_id}' exists")
        else:
            logger.error(f"Error adding user to project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error adding user to project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_update(args):
    """Execute the 'project update' subcommand."""
    from crucible.client import CrucibleClient

    fields = {k: v for k, v in {
        'title':               args.title,
        'organization':        args.organization,
        'status':              args.status,
        'project_lead_email':  args.project_lead_email,
        'project_lead_orcid':  args.project_lead_orcid,
    }.items() if v is not None}

    has_metadata = bool(getattr(args, 'metadata', None))

    if not fields and not has_metadata:
        logger.error("No fields to update. Provide at least one of: --title, --organization, --status, --lead-email, --lead-orcid, --metadata")
        sys.exit(1)

    metadata_dict = None
    if has_metadata:
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

    try:
        client = CrucibleClient()

        if fields:
            result = client.projects.update(args.project_id, **fields)
            logger.info("✓ Project updated")
            _show_project(result)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.projects.update_scientific_metadata(args.project_id, metadata_dict, overwrite=overwrite)
            action = "replaced" if overwrite else "updated"
            logger.info(f"✓ Scientific metadata {action} for project {args.project_id}")

    except Exception as e:
        logger.error(f"Error updating project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_remove_user(args):
    """Execute the 'project remove-user' subcommand."""
    import requests as _req
    from crucible.client import CrucibleClient

    orcid = getattr(args, 'orcid', None)
    email = getattr(args, 'email', None)

    try:
        client = CrucibleClient()

        try:
            user = client.users.get(orcid=orcid, email=email)
            first = user.get('first_name') or ''
            last  = user.get('last_name') or ''
            name  = ' '.join(p for p in (first, last) if p) or orcid or email
        except Exception:
            name = orcid or email

        client.projects.remove_user(args.project_id, orcid=orcid, email=email)
        logger.info(f"Removed {name} from project '{args.project_id}'")

    except _req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            identifier = orcid or email
            logger.error(f"Not found: check that '{identifier}' is a member of '{args.project_id}'")
        else:
            logger.error(f"Error removing user from project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error removing user from project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _project_updatable_fields():
    """Return ordered list of fields that can be updated on a project."""
    from .schema import PROJECT_FIELDS, editable_keys
    return editable_keys(PROJECT_FIELDS)


def _register_edit(subparsers):
    """Register the 'project edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit project fields interactively',
        description='Open project fields in $EDITOR and update on save',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project edit my-project
    EDITOR=vim crucible project edit my-project
"""
    )
    pid_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        pid_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_edit)


def _edit_project(project_id, client, debug=False):
    """Core edit logic for a project - shared with top-level 'crucible edit' command."""
    project = client.projects.get(project_id, include_metadata=True)
    if project is None:
        logger.error(f"Project not found: {project_id}")
        sys.exit(1)

    from .schema import PROJECT_FIELDS, ordered_dict
    valid_fields = set(_project_updatable_fields())
    original_fields = ordered_dict(PROJECT_FIELDS, project, verbose=True, editable_only=True)
    original_meta = project.get('scientific_metadata') or {}

    original = dict(original_fields)
    original['scientific_metadata'] = original_meta

    try:
        edited = term.open_editor_json(original)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    field_changes = {k: v for k, v in edited.items() if k in valid_fields and v != original_fields.get(k)}
    edited_meta = edited.get('scientific_metadata')
    meta_changed = isinstance(edited_meta, dict) and edited_meta != original_meta

    if not field_changes and not meta_changed:
        logger.info("No changes.")
        return

    try:
        if field_changes:
            client.projects.update(project_id, **field_changes)
        if meta_changed:
            client.projects.update_scientific_metadata(project_id, edited_meta, overwrite=True)

        diff_updated = dict(field_changes)
        if meta_changed:
            diff_updated['scientific_metadata'] = edited_meta
        term.header("Changes")
        term.diff(original, diff_updated)
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_edit(args):
    """Execute the 'project edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        logger.error(f"Error connecting: {e}")
        sys.exit(1)
    _edit_project(args.project_id, client, debug=getattr(args, 'debug', False))
