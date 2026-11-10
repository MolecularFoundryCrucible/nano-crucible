#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Join-request subcommand.

Lets a user request to join a project, follow and withdraw the request, and
lets project editors and above (and admins) review it. Accessible as both
'crucible access-group' and 'crucible ag'.
"""

import argparse
import sys
import json
import logging
from . import term
from .helpers import (RemovedOptionAction, add_limit_arguments, count_label,
                      print_more_hint, resolve_limit, page_kwargs)
from ..constants import (JOIN_REQUEST_SCOPES, JOIN_REQUEST_SORTS,
                         JOIN_REQUEST_STATUSES, PROJECT_MEMBER_ROLES,
                         SORT_DIRECTIONS)

_STATUS_CHOICES = list(JOIN_REQUEST_STATUSES) + ['all']

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    for name in ('access-group', 'ag'):
        parser = subparsers.add_parser(
            name,
            help='Request, follow, and review project join requests',
            description='Request to join a project, follow or withdraw your requests, '
                        'and review requests to projects you manage.',
        )
        ag_subparsers = parser.add_subparsers(dest='ag_command', metavar='COMMAND')
        ag_subparsers.required = True

        _register_request(ag_subparsers)
        _register_list(ag_subparsers)
        _register_mine(ag_subparsers)
        _register_get(ag_subparsers)
        _register_approve(ag_subparsers)
        _register_reject(ag_subparsers)
        _register_withdraw(ag_subparsers)


def _project_label(record):
    project = record.get('project') or {}
    return project.get('project_id') or record.get('group_name') or record.get('project_mfid')


def _user_cell(record, role, names):
    user_id = record.get(f'{role}_id')
    user = record.get(role) or {}
    label = user.get('username') or names.get(user_id, user_id)
    return term.user_link(label, user_id)


def _names_for(client, records, roles):
    from .helpers import resolve_usernames
    missing = [r.get(f'{role}_id') for r in records for role in roles
               if not (r.get(role) or {}).get('username')]
    return resolve_usernames(client, missing)


def _show_join_request(record, client=None):
    """Print a JoinRequest record."""
    names = _names_for(client, [record], ('requester', 'reviewer'))
    project = record.get('project') or {}
    _p = term.field_printer(16)
    term.header("Join Request")
    _p("Request ID", record.get('id'))
    _p("Project",    _project_label(record))
    if project.get('title'):
        _p("Title",  project.get('title'))
    _p("Status",     term.status_label(record.get('status')))
    _p("Reason",     record.get('reason'))
    _p("Requested",  term.fmt_ts(record.get('request_time')))
    _p("Requester",  _user_cell(record, 'requester', names))
    if record.get('review_time') or record.get('reviewer_notes'):
        _p("Closed",       term.fmt_ts(record.get('review_time')))
        if record.get('reviewer_id'):
            _p("Reviewer", _user_cell(record, 'reviewer', names))
        if record.get('granted_role'):
            _p("Granted Role", record.get('granted_role'))
        _p("Review Notes", record.get('reviewer_notes'))


def _table_rows(records, client=None):
    names = _names_for(client, records, ('requester',))
    return [
        (
            str(r.get('id', '-')),
            _project_label(r) or '-',
            term.status_label(r.get('status') or '-'),
            _user_cell(r, 'requester', names) or '-',
            term.fmt_date(r.get('request_time')),
        )
        for r in records
    ]


def _print_table(records, args, title, client):
    term.header(f"{title} — {args.status} ({count_label(records)})")
    if not records:
        print(f"  {term.dim('No join requests found.')}")
        return
    term.table(_table_rows(records, client=client),
               ['ID', 'Project', 'Status', 'Requester', 'Requested'],
               max_widths=[6, 25, 10, 25, 12])
    print_more_hint(records, resolve_limit(args), args)


# ── request ───────────────────────────────────────────────────────────────────

def _register_request(subparsers):
    parser = subparsers.add_parser(
        'request',
        help='Request to join a project',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag request my-project
    crucible ag request my-project --reason "Need access for XRD analysis"
""",
    )
    parser.add_argument('project_ref', metavar='PROJECT', help='Project ID or MFID')
    parser.add_argument('--reason', metavar='TEXT', default=None,
                        help='Optional explanation for the request (at most 2000 characters)')
    parser.set_defaults(func=_execute_request)


def _execute_request(args):
    from crucible.config import get_client
    try:
        client = get_client()
        record = client.access_groups.request_join(args.project_ref, reason=args.reason)
        term.success("Join request submitted", args)
        print()
        _show_join_request(record, client=client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── list ──────────────────────────────────────────────────────────────────────

def _register_list(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='List join requests you may review',
        description='List join requests to projects where you are an editor or above '
                    '(every project for admins). Use --scope for other views.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag list                          # pending requests you may review
    crucible ag list --project my-project
    crucible ag list --status approved --status rejected
    crucible ag list --status all --sort requester_name --direction asc
    crucible ag list --scope accessible --search smith
""",
    )
    parser.add_argument('--project', metavar='PROJECT', default=None,
                        help='Only requests to this project (ID or MFID)')
    parser.add_argument('--group', dest='project', metavar='PROJECT', default=argparse.SUPPRESS,
                        action=RemovedOptionAction, removed_options={'--group'},
                        replacement='--project', help=argparse.SUPPRESS)
    parser.add_argument('--status', choices=_STATUS_CHOICES, action='append', default=None,
                        help='Filter by status; repeatable (default: pending)')
    parser.add_argument('--scope', choices=list(JOIN_REQUEST_SCOPES), default='reviewable',
                        help='reviewable: those you may review (default); submitted: your own; '
                             'accessible: both')
    parser.add_argument('--requester', dest='requester_id', metavar='USER', default=None,
                        help="Only this user's requests (ORCID or MFID)")
    parser.add_argument('--search', dest='q', metavar='TEXT', default=None,
                        help="Match the requester's name, username, or ORCID")
    parser.add_argument('--sort', choices=list(JOIN_REQUEST_SORTS), default=None,
                        help='Order results (default: request_time)')
    parser.add_argument('--direction', choices=list(SORT_DIRECTIONS), default=None,
                        help='Sort direction (default: desc)')
    add_limit_arguments(parser, 'requests')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_list)


def _statuses(args):
    """Return the status filter and set args.status to its display label."""
    chosen = args.status or ['pending']
    args.status = ', '.join(chosen)
    return None if 'all' in chosen else chosen


def _execute_list(args):
    from crucible.config import get_client
    try:
        client = get_client()
        status = _statuses(args)
        filters = dict(
            status=status, scope=args.scope, requester_id=args.requester_id,
            q=args.q, sort=args.sort, direction=args.direction,
            limit=resolve_limit(args), **page_kwargs(args))
        if args.project:
            records = client.projects.list_join_requests(args.project, **filters)
        else:
            records = client.access_groups.list_join_requests(**filters)
        if getattr(args, 'json', False):
            print_more_hint(records, resolve_limit(args), args)
            print(json.dumps(records, indent=2, default=str))
            return
        _print_table(records, args, "Join Requests", client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── mine ──────────────────────────────────────────────────────────────────────

def _register_mine(subparsers):
    parser = subparsers.add_parser(
        'mine',
        help='List your own join requests',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag mine                  # pending only (default)
    crucible ag mine --status approved
    crucible ag mine --status all
""",
    )
    parser.add_argument('--status', choices=_STATUS_CHOICES, action='append', default=None,
                        help='Filter by status; repeatable (default: pending)')
    add_limit_arguments(parser, 'requests')
    parser.set_defaults(func=_execute_mine)


def _execute_mine(args):
    from crucible.config import get_client
    try:
        client = get_client()
        status = _statuses(args)
        records = client.account.join_requests(status=status, limit=resolve_limit(args), **page_kwargs(args))
        _print_table(records, args, "My Join Requests", client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── get ───────────────────────────────────────────────────────────────────────

def _register_get(subparsers):
    parser = subparsers.add_parser(
        'get',
        help='Get a join request by ID',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag get 42
""",
    )
    parser.add_argument('request_id', type=int, metavar='REQUEST_ID', help='Join request ID')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON object')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    from crucible.config import get_client
    try:
        client = get_client()
        record = client.access_groups.get(args.request_id)
        if record is None:
            logger.error(f"Join request not found: {args.request_id}")
            sys.exit(1)
        if getattr(args, 'json', False):
            print(json.dumps(record, indent=2, default=str))
            return
        _show_join_request(record, client=client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── approve / reject ───────────────────────────────────────────────────────────

def _register_approve(subparsers):
    parser = subparsers.add_parser(
        'approve',
        help='Approve one or more pending join requests (project editor or above)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag approve 42
    crucible ag approve 42 43 44 -m "Welcome aboard"
    crucible ag approve 42 --role editor
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of join requests to approve')
    parser.add_argument('-m', '--message', dest='reviewer_notes', metavar='TEXT', default=None,
                        help='Optional reviewer notes')
    parser.add_argument('--role', choices=list(PROJECT_MEMBER_ROLES), default=None,
                        help='Role to grant, below your own (default: contributor)')
    parser.set_defaults(func=_execute_approve)


def _execute_approve(args):
    from crucible.config import get_client
    try:
        client = get_client()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)

    had_error = False
    for rid in args.request_id:
        try:
            record = client.access_groups.approve_join_request(
                rid, reviewer_notes=args.reviewer_notes, role=args.role)
            term.success(f"Join request {rid} approved", args)
            print()
            _show_join_request(record, client=client)
        except Exception as e:
            had_error = True
            logger.error(f"Error approving join request {rid}: {e}")
            if getattr(args, 'debug', False):
                import traceback
                traceback.print_exc()

    if had_error:
        sys.exit(1)


def _register_reject(subparsers):
    parser = subparsers.add_parser(
        'reject',
        help='Reject one or more pending join requests (project editor or above)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag reject 42
    crucible ag reject 42 43 44 -m "Not currently accepting new members"
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of join requests to reject')
    parser.add_argument('-m', '--message', dest='reviewer_notes', metavar='TEXT', default=None,
                        help='Optional reviewer notes')
    parser.set_defaults(func=_execute_reject)


def _execute_reject(args):
    from crucible.config import get_client
    try:
        client = get_client()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)

    had_error = False
    for rid in args.request_id:
        try:
            record = client.access_groups.reject_join_request(rid, reviewer_notes=args.reviewer_notes)
            term.success(f"Join request {rid} rejected", args)
            print()
            _show_join_request(record, client=client)
        except Exception as e:
            had_error = True
            logger.error(f"Error rejecting join request {rid}: {e}")
            if getattr(args, 'debug', False):
                import traceback
                traceback.print_exc()

    if had_error:
        sys.exit(1)


# ── withdraw ──────────────────────────────────────────────────────────────────

def _register_withdraw(subparsers):
    parser = subparsers.add_parser(
        'withdraw',
        help='Withdraw one or more of your pending join requests',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag withdraw 42
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of join requests to withdraw')
    parser.set_defaults(func=_execute_withdraw)


def _execute_withdraw(args):
    from crucible.config import get_client
    try:
        client = get_client()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)

    had_error = False
    for rid in args.request_id:
        try:
            record = client.access_groups.withdraw_join_request(rid)
            term.success(f"Join request {rid} withdrawn", args)
            print()
            _show_join_request(record, client=client)
        except Exception as e:
            had_error = True
            logger.error(f"Error withdrawing join request {rid}: {e}")
            if getattr(args, 'debug', False):
                import traceback
                traceback.print_exc()

    if had_error:
        sys.exit(1)
