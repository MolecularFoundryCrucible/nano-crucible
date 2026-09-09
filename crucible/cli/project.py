#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project subcommand for Crucible CLI.

Provides project-related operations: list, get, create.
"""

import argparse
import sys
import logging
import json
import warnings

logger = logging.getLogger(__name__)

from . import term
from ..config import config as _config
from ..constants import PROJECT_MEMBER_ROLES

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


class _DeprecatedMembersAction(argparse.Action):
    """Set include_members while warning about the former CLI spelling."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        warnings.warn(
            "--members is deprecated; use --include-members instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        setattr(namespace, self.dest, True)


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
    _register_search(project_subparsers)
    _register_search_metadata(project_subparsers)
    _register_get(project_subparsers)
    _register_create(project_subparsers)
    _register_update(project_subparsers)
    _register_edit(project_subparsers)
    _register_list_users(project_subparsers)
    _register_add_user(project_subparsers)
    _register_remove_user(project_subparsers)
    _register_update_user_role(project_subparsers)
    _register_transfer_ownership(project_subparsers)
    _register_request_join(project_subparsers)
    _register_list_join_requests(project_subparsers)
    from ._access import register_access_commands
    register_access_commands(project_subparsers, 'projects', id_metavar='PROJECT_ID')


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
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON array'
    )

    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'project get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get project by MFID or project slug',
        description='Retrieve a project by canonical MFID or exact project_id slug'
    )

    project_id_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT',
        help='Project MFID or project_id slug'
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
        '--include-members',
        action='store_true',
        dest='include_members',
        help='Include the project member list (project members/platform admins only)'
    )

    parser.add_argument(
        '--members',
        action=_DeprecatedMembersAction,
        dest='include_members',
        help='Deprecated alias for --include-members'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON'
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
    crucible project create --project-id my-project -o "LBNL" -e "lead-username"
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov" \\
        --title "Silicon Wafer Study"
"""
    )

    from .helpers import DeprecatedAliasAction
    parser.add_argument(
        '--project-id', '-i',
        required=False,
        default=None,
        metavar='ID',
        help='Unique project identifier (e.g., "my-project"). If not provided, will prompt interactively.'
    )
    parser.add_argument(
        '-id',
        action=DeprecatedAliasAction,
        deprecated_options={'-id'},
        replacement='--project-id',
        dest='project_id',
        default=argparse.SUPPRESS,
        metavar='ID',
        help=argparse.SUPPRESS,
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
        metavar='USER',
        dest='project_lead',
        help='Project lead ORCID, MFID, username, or email. If not provided, will prompt interactively.'
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
        description='Add a user to a project by ORCID, MFID, username, or email (requires editor or above; the granted role must be below your role)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project add-user my-project --user 0000-0002-1825-0097
    crucible project add-user my-project --user fabrice
    crucible project add-user my-project --user user@lbl.gov
    crucible project add-user my-project --user fabrice --role editor
"""
    )

    project_id_arg = parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument('--user', '-u', metavar='USER', default=None,
                        help='ORCID, MFID, username, or email of the user')
    parser.add_argument('--role', choices=PROJECT_MEMBER_ROLES, default=None,
                        help='Role to grant (default: contributor)')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--orcid',    metavar='ORCID',    help='(deprecated, use --user)')
    group.add_argument('--email',    metavar='EMAIL',    help='(deprecated, use --user)')
    group.add_argument('--username', metavar='USERNAME', help='(deprecated, use --user)')

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
    crucible project update my-project --project-id new-project-slug
    crucible project transfer-ownership my-project newlead@example.com --confirm
"""
    )
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Project ID')
    parser.add_argument('--title',        dest='title',               metavar='TITLE',  help='Project title')
    parser.add_argument('--organization', dest='organization',        metavar='ORG',    help='Organization name')
    parser.add_argument('--status',       dest='status',              metavar='STATUS', help='Project status')
    parser.add_argument('--project-id', '-i', dest='new_project_id',  metavar='ID',
                        help='Rename the project to a new project ID')
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
        description='Remove yourself from a project, or remove a member as project owner or platform administrator',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project remove-user my-project --user 0000-0002-1825-0097
    crucible project remove-user my-project --user fabrice
    crucible project remove-user my-project --user user@lbl.gov
"""
    )
    project_id_arg = parser.add_argument(
        'project_id', metavar='PROJECT_ID', help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument('--user', '-u', metavar='USER', default=None,
                        help='ORCID, MFID, username, or email of the user')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--orcid',    metavar='ORCID',    help='(deprecated, use --user)')
    group.add_argument('--email',    metavar='EMAIL',    help='(deprecated, use --user)')
    group.add_argument('--username', metavar='USERNAME', help='(deprecated, use --user)')
    parser.set_defaults(func=_execute_remove_user)


def _execute_list(args):
    """Execute the 'project list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        projects = client.projects.list(limit=args.limit,
                                        include_metadata=getattr(args, 'include_metadata', False))

        if getattr(args, 'json', False):
            print(json.dumps(projects, indent=2, default=str))
            return

        term.header(f"Projects ({len(projects)})")
        if not projects:
            print(f"  {term.dim('No projects found.')}")
        else:
            from .helpers import project_explorer_url
            def _project_row(project):
                project_id = project.get('project_id')
                title = project.get('title')
                url = project_explorer_url(project_id)
                return (
                    project_id if title else term.project_link(project_id, url),
                    term.navigation_link(title, url) if title else '-',
                    project.get('organization') or '-',
                    _lead_name(project) or '-',
                )
            rows = [_project_row(project) for project in projects]
            term.table(rows, ['Project ID', 'Title', 'Organization', 'Lead'],
                       max_widths=[25, 30, 20, 25],
                       min_widths=[25, 5, 12, 4])

    except Exception as e:
        from .helpers import fail
        fail("listing projects", e, args)


def _lead_name(project):
    """Return the lead's display name or canonical identifier."""
    lead = project.get('lead') or {}
    user_id = (
        lead.get('unique_id')
        or project.get('project_lead')
        or project.get('project_lead_orcid')
    )
    name = term.fmt_name(
        lead,
        default=user_id,
        fallback_username=False,
    )
    return term.user_link(name, user_id)


def _show_project(project, include_metadata=False, include_members=False):
    """Display project fields."""
    _p = term.field_printer(14)

    from .helpers import project_explorer_url

    term.header("Project")
    pid = project.get('project_id')
    uid = project.get('unique_id')
    project_url = project_explorer_url(pid)
    title = project.get('title')
    _p("Title",        term.bold(title) if title else term.dim('-'))
    _p("Project ID",   pid)
    _p("MFID",         term.mfid_link(uid, project_url))
    _p("Organization", project.get('organization'))
    _p("Status",       term.status_label(project.get('status')))

    lead = _lead_name(project)
    if lead:
        term.subheader("People")
        _p("Lead", lead)

    timing = (
        ("Created", project.get('creation_time')),
        ("Modified", project.get('modification_time')),
    )
    if any(value for _, value in timing):
        term.subheader("Timing")
        for label, value in timing:
            if value:
                _p(label, term.fmt_ts(value))

    if include_metadata:
        from .helpers import show_scientific_metadata
        show_scientific_metadata(project.get('scientific_metadata'))

    members = project.get('members')
    if include_members or members:
        from .helpers import sort_members
        members = sort_members(members or [])
        term.subheader(f"Members ({len(members)})")
        if not members:
            print(f"  {term.dim('No members found.')}")
            return
        rows = [(
            m.get('username') or '-',
            term.user_link(
                term.fmt_name(m, default='-', fallback_username=False),
                m.get('unique_id'),
            ),
            term.role_label(m.get('role')),
        ) for m in members]
        term.table(rows, ['Username', 'Name', 'Role'], max_widths=[25, 25, 12])


def _execute_get(args):
    """Execute the 'project get' subcommand."""
    from crucible.client import CrucibleClient
    include_metadata = getattr(args, 'json', False) or getattr(args, 'include_metadata', False) or _config.include_metadata
    include_members = getattr(args, 'include_members', False)
    try:
        client = CrucibleClient()
        project = client.projects.get(args.project_id,
                                      include_metadata=include_metadata,
                                      include_members=include_members)

        if project is None:
            logger.error(f"Project not found: {args.project_id}")
            sys.exit(1)

        if getattr(args, 'json', False):
            import json
            print(json.dumps(project, indent=2, default=str))
        else:
            _show_project(
                project,
                include_metadata=include_metadata,
                include_members=include_members,
            )

    except Exception as e:
        from .helpers import fail
        fail("retrieving project", e, args)


def _execute_create(args):
    """Execute the 'project create' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import prompt_optional, prompt_required, validate_user_reference
    from ..utils.identifiers import validate_slug
    # Interactive mode if any required arguments are missing
    project_id = args.project_id
    organization = args.organization
    project_lead = args.project_lead
    title = args.title
    status = args.status

    interactive = project_id is None or organization is None or project_lead is None
    if interactive:
        term.header("Create Project")
        print("")

    if project_id is None:
        project_id = prompt_required(
            "Project ID",
            validator=lambda value: validate_slug(value, 'project'),
            option='--project-id',
        )

    if organization is None:
        organization = prompt_required("Organization", option='--organization')

    if project_lead is None:
        project_lead = prompt_required(
            "Project lead",
            validator=validate_user_reference,
            option='--lead',
        )

    if interactive:
        if title is None:
            title = prompt_optional("Project title")

        if status is None:
            status = prompt_optional("Status")

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
        project_lead = validate_user_reference(project_lead)
        client = CrucibleClient()

        project = Project(
            project_id=project_id,
            organization=organization,
            project_lead=project_lead,
            title=title,
            status=status,
        )
        result = client.projects.create(project, scientific_metadata=metadata_dict)

        term.success("Project created", args)
        _show_project(result)

    except Exception as e:
        from .helpers import fail
        fail("creating project", e, args)


def _execute_list_users(args):
    """Execute the 'project get-users' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import sort_members
    try:
        client = CrucibleClient()
        users = sort_members(client.projects.get_users(args.project_id, limit=args.limit))

        term.header(f"Users · {args.project_id} ({len(users)})")
        if not users:
            print(f"  {term.dim('No users found.')}")
        else:
            rows = []
            for u in users:
                name = term.user_link(
                    term.fmt_name(
                        u.model_dump(), default='-', fallback_username=False),
                    u.unique_id,
                )
                username = u.username or '-'
                role     = term.role_label(u.role)
                rows.append((username, name, role))
            term.table(rows, ['Username', 'Name', 'Role'], max_widths=[25, 25, 12])

    except Exception as e:
        from .helpers import fail
        fail("listing project users", e, args)


def _execute_add_user(args):
    """Execute the 'project add-user' subcommand."""
    import re
    import warnings
    from crucible.client import CrucibleClient
    from .helpers import parse_user_ref

    orcid    = getattr(args, 'orcid', None)
    email    = getattr(args, 'email', None)
    username = getattr(args, 'username', None)
    user_ref = getattr(args, 'user', None)

    if orcid or email or username:
        warnings.warn(
            "--orcid/--email/--username are deprecated; use --user instead: "
            "crucible project add-user PROJECT_ID --user VALUE",
            DeprecationWarning, stacklevel=2,
        )
    elif user_ref:
        ref = parse_user_ref(user_ref)
        orcid, email, username = ref.get('orcid'), ref.get('email'), ref.get('username')
    else:
        logger.error("Provide a user identifier: crucible project add-user PROJECT_ID --user VALUE")
        sys.exit(1)

    if orcid and not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$', orcid):
        logger.error(f"Invalid ORCID format: {orcid}")
        logger.error("Expected format: 0000-0000-0000-000X")
        sys.exit(1)

    try:
        client = CrucibleClient()
        role = getattr(args, 'role', None)
        users = client.projects.add_user(user_unique_id=orcid, project_id=args.project_id,
                                         email=email, username=username, role=role)

        name = orcid or username or email
        if isinstance(users, list):
            match = next((u for u in users if
                          (orcid and u.unique_id == orcid) or
                          (username and u.username == username)), None)
            if match:
                name = ' '.join(p for p in (match.first_name or '', match.last_name or '') if p) or name

        print()
        term.success(f"{name} added to project {args.project_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("adding user to project", e, args)


def _execute_update(args):
    """Execute the 'project update' subcommand."""
    from crucible.client import CrucibleClient

    fields = {k: v for k, v in {
        'title':               args.title,
        'organization':        args.organization,
        'status':              args.status,
        'project_id':          args.new_project_id,
    }.items() if v is not None}

    has_metadata = bool(getattr(args, 'metadata', None))

    if not fields and not has_metadata:
        logger.error("No fields to update. Provide at least one of: --title, --organization, --status, --project-id, --metadata")
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
        current_project_id = args.project_id

        if fields:
            result = client.projects.update(current_project_id, **fields)
            term.success("Project updated", args)
            _show_project(result)
            current_project_id = result.get('project_id', current_project_id)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.projects.update_scientific_metadata(current_project_id, metadata_dict, overwrite=overwrite)
            action = "replaced" if overwrite else "updated"
            term.success(f"Scientific metadata {action} for project {current_project_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("updating project", e, args)


def _execute_remove_user(args):
    """Execute the 'project remove-user' subcommand."""
    import requests as _req
    import warnings
    from crucible.client import CrucibleClient
    from .helpers import parse_user_ref

    orcid    = getattr(args, 'orcid', None)
    email    = getattr(args, 'email', None)
    username = getattr(args, 'username', None)
    user_ref = getattr(args, 'user', None)

    if orcid or email or username:
        warnings.warn(
            "--orcid/--email/--username are deprecated; use --user instead: "
            "crucible project remove-user PROJECT_ID --user VALUE",
            DeprecationWarning, stacklevel=2,
        )
    elif user_ref:
        ref = parse_user_ref(user_ref)
        orcid, email, username = ref.get('orcid'), ref.get('email'), ref.get('username')
    else:
        logger.error("Provide a user identifier: crucible project remove-user PROJECT_ID --user VALUE")
        sys.exit(1)

    try:
        client = CrucibleClient()

        try:
            user = client.users.get(orcid=orcid, email=email, username=username)
            user_unique_id = user.get('unique_id')
            first = user.get('first_name') or ''
            last  = user.get('last_name') or ''
            name  = ' '.join(p for p in (first, last) if p) or orcid or username or email
        except Exception:
            user_unique_id = orcid
            name = orcid or username or email

        client.projects.remove_user(
            args.project_id,
            user_unique_id=user_unique_id,
            email=None if user_unique_id else email,
            username=None if user_unique_id else username,
        )
        term.success(f"Removed {name} from project '{args.project_id}'", args)

    except _req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            identifier = orcid or username or email
            logger.error(f"Not found: check that '{identifier}' is a member of '{args.project_id}'")
        else:
            logger.error(f"Error removing user from project: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        from .helpers import fail
        fail("removing user from project", e, args)


def _register_update_user_role(subparsers):
    """Register the 'project update-user-role' subcommand."""
    parser = subparsers.add_parser(
        'update-user-role',
        help="Change a member's role in a project",
        description='Change a project member\'s role (current and requested roles must both be below your role; ownership is transfer-only)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project update-user-role my-project 0000-0002-1825-0097 editor
"""
    )
    project_id_arg = parser.add_argument(
        'project_id', metavar='PROJECT_ID', help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument(
        'user_unique_id', metavar='USER_ID',
        help="Member's canonical ORCID or user MFID",
    )
    parser.add_argument('role', choices=PROJECT_MEMBER_ROLES,
                        help='New role to grant')
    parser.set_defaults(func=_execute_update_user_role)


def _execute_update_user_role(args):
    """Execute the 'project update-user-role' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, sort_members

    try:
        client = CrucibleClient()
        users = sort_members(client.projects.update_user_role(
            args.project_id, args.user_unique_id, args.role))
        term.success(
            f"{args.user_unique_id} is now '{args.role}' in project '{args.project_id}'", args)
        rows = [(
            u.username or '-',
            term.user_link(
                term.fmt_name(
                    u.model_dump(), default='-', fallback_username=False),
                u.unique_id,
            ),
            term.role_label(u.role),
        ) for u in users]
        term.table(rows, ['Username', 'Name', 'Role'], max_widths=[25, 25, 12])
    except Exception as e:
        fail("updating user role", e, args)


def _register_transfer_ownership(subparsers):
    """Register the 'project transfer-ownership' subcommand."""
    parser = subparsers.add_parser(
        'transfer-ownership',
        help='Transfer ownership of a project',
        description='Preview or execute an ownership transfer (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project transfer-ownership my-project newlead@example.com
    crucible project transfer-ownership my-project newlead@example.com --confirm
"""
    )
    project_id_arg = parser.add_argument(
        'project_id', metavar='PROJECT_ID', help='Project ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        project_id_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('new_owner', metavar='NEW_OWNER', help='ORCID, MFID, username, or email of the new owner')
    parser.add_argument('--confirm', action='store_true', help='Execute the transfer (default: preview only)')
    parser.set_defaults(func=_execute_transfer_ownership)


def _execute_transfer_ownership(args):
    """Execute the 'project transfer-ownership' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_transfer_ownership

    try:
        client = CrucibleClient()
        result = client.projects.transfer_ownership(args.project_id, args.new_owner, confirm=args.confirm)
        show_transfer_ownership(result, args.confirm)
    except Exception as e:
        fail("transferring project ownership", e, args)


def _register_request_join(subparsers):
    """Register the 'project request-join' subcommand."""
    parser = subparsers.add_parser(
        'request-join',
        help='Request to join a project',
        description='Request to join a project. Any authenticated user.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project request-join my-project
    crucible project request-join my-project --reason "Need access for XRD analysis"
"""
    )
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Project ID')
    parser.add_argument('--reason', metavar='TEXT', default=None,
                        help='Optional explanation for the request')
    parser.set_defaults(func=_execute_request_join)


def _execute_request_join(args):
    """Execute the 'project request-join' subcommand."""
    from crucible.client import CrucibleClient
    from .access_group import _show_join_request
    try:
        client = CrucibleClient()
        record = client.projects.request_join(args.project_id, reason=args.reason)
        term.success("Join request submitted", args)
        _show_join_request(record, client=client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_list_join_requests(subparsers):
    """Register the 'project list-join-requests' subcommand."""
    parser = subparsers.add_parser(
        'list-join-requests',
        help='List join requests for a project (admin or project lead)',
        description='List join requests for a project. Requires admin or project lead permissions.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project list-join-requests my-project
    crucible project list-join-requests my-project --status pending
"""
    )
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Project ID')
    parser.add_argument('--status', choices=['pending', 'approved', 'rejected'], default=None,
                        help='Filter by status')
    parser.add_argument('--limit', type=int, default=100, metavar='N')
    parser.set_defaults(func=_execute_list_join_requests)


def _execute_list_join_requests(args):
    """Execute the 'project list-join-requests' subcommand."""
    from crucible.client import CrucibleClient
    from .access_group import _table_rows
    try:
        client = CrucibleClient()
        records = client.projects.list_join_requests(args.project_id, status=args.status,
                                                      limit=args.limit)
        term.header(f"Join Requests · {args.project_id} ({len(records)})")
        if not records:
            print(f"  {term.dim('No join requests found.')}")
            return
        term.table(_table_rows(records, client=client),
                  ['ID', 'Group', 'Status', 'Requester', 'Requested'],
                  max_widths=[6, 25, 10, 25, 12])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


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
        from .helpers import fail
        fail("updating project", e, debug)


def _execute_edit(args):
    """Execute the 'project edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)
    _edit_project(args.project_id, client, debug=getattr(args, 'debug', False))


def _register_search(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Fuzzy search projects by name or ID',
        description='Fuzzy search across all projects, including ones you are not a member of. '
                    'Use "crucible project request-join" to ask to join a project you find.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible project search alphafold
    crucible project search "10k"
""",
    )
    parser.add_argument('query', metavar='QUERY', help='Search term (min 3 chars)')
    parser.add_argument('--limit', '-l', type=int, default=20, metavar='N',
                        help='Maximum results (default: 20, max: 50)')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_search)


def _execute_search(args):
    if len(args.query) < 3:
        from .helpers import fail
        fail("searching projects", ValueError("Search term must be at least 3 characters."), args)
    from crucible.client import CrucibleClient
    try:
        client  = CrucibleClient()
        results = client.projects.search(args.query, limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Projects matching '{args.query}' ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
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
        rows = [_project_row(project) for project in results]
        term.table(
            rows,
            ['Project ID', 'Title', 'Organization'],
            max_widths=[25, 30, 20],
            min_widths=[25, 5, 12],
        )
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_search_metadata(subparsers):
    for name in ('search-metadata', 'search-md'):
        parser = subparsers.add_parser(
            name,
            help='Search projects by scientific metadata' if name == 'search-metadata' else None,
            description='Full-text search across scientific metadata of all accessible projects.',
            formatter_class=term.ColorHelpFormatter,
        )
        parser.add_argument('query', metavar='QUERY', help='Search query string')
        parser.add_argument('--limit', '-l', type=int, default=50, metavar='N',
                            help='Maximum results (default: 50)')
        parser.add_argument('--json', action='store_true', default=False,
                            help='Output as JSON array')
        parser.set_defaults(func=_execute_search_metadata)


def _execute_search_metadata(args):
    from crucible.client import CrucibleClient
    try:
        client  = CrucibleClient()
        results = client.projects.search_metadata(args.query, limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Metadata search: {args.query} ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        for r in results:
            print(f"  {term.cyan(r.get('unique_id', '-'))}")
    except Exception as e:
        from .helpers import fail
        fail("", e, args)
