#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Access group join-request subcommand.

Lets a user request to join an access group (currently only projects) and
lets admins/leads review the request. Accessible as both
'crucible access-group' and 'crucible ag'.
"""

import sys
import logging
from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    for name in ('access-group', 'ag'):
        parser = subparsers.add_parser(
            name,
            help='Request and review access-group join requests',
            description='Request to join an access group (project), and review pending requests.',
        )
        ag_subparsers = parser.add_subparsers(dest='ag_command', metavar='COMMAND')
        ag_subparsers.required = True

        _register_request(ag_subparsers)
        _register_list(ag_subparsers)
        _register_mine(ag_subparsers)
        _register_get(ag_subparsers)
        _register_approve(ag_subparsers)
        _register_reject(ag_subparsers)


def _show_join_request(record, client=None):
    """Print a JoinRequest record."""
    from .helpers import resolve_usernames
    names = resolve_usernames(client, [record.get('requester_id'), record.get('reviewer_id')])
    _p = term.field_printer(16)
    term.header("Join Request")
    _p("Request ID", record.get('id'))
    _p("Group",      record.get('group_name'))
    _p("Status",     term.status_label(record.get('status')))
    _p("Reason",     record.get('reason'))
    _p("Requested",  term.fmt_ts(record.get('request_time')))
    requester_id = record.get('requester_id')
    _p("Requester",  term.user_link(names.get(requester_id, requester_id), requester_id))
    if record.get('reviewer_notes') or record.get('review_time'):
        _p("Review Time",  term.fmt_ts(record.get('review_time')))
        reviewer_id = record.get('reviewer_id')
        _p("Reviewer",     term.user_link(names.get(reviewer_id, reviewer_id), reviewer_id))
        _p("Review Notes", record.get('reviewer_notes'))


def _table_rows(records, client=None):
    from .helpers import resolve_usernames
    names = resolve_usernames(client, [r.get('requester_id') for r in records])
    rows = []
    for r in records:
        rows.append((
            str(r.get('id', '-')),
            r.get('group_name') or '-',
            term.status_label(r.get('status') or '-'),
            term.user_link(
                names.get(r.get('requester_id'), r.get('requester_id')),
                r.get('requester_id'),
            ) or '-',
            term.fmt_date(r.get('request_time')),
        ))
    return rows


# ── request ───────────────────────────────────────────────────────────────────

def _register_request(subparsers):
    parser = subparsers.add_parser(
        'request',
        help='Request to join an access group',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag request my-project
    crucible ag request my-project --reason "Need access for XRD analysis"
""",
    )
    parser.add_argument('group_name', metavar='GROUP', help='Access group name (project ID)')
    parser.add_argument('--reason', metavar='TEXT', default=None,
                        help='Optional explanation for the request')
    parser.set_defaults(func=_execute_request)


def _execute_request(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        record = client.access_groups.request_join(args.group_name, reason=args.reason)
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
        help='List join requests (admin, or lead of the given group)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag list                          # pending only (default)
    crucible ag list --group my-project
    crucible ag list --status approved
    crucible ag list --status all
""",
    )
    parser.add_argument('--group', dest='group_name', metavar='GROUP', default=None,
                        help='Filter to one group. Required for a non-admin lead.')
    parser.add_argument('--status', choices=['pending', 'approved', 'rejected', 'all'],
                        default='pending', help='Filter by status (default: pending)')
    parser.add_argument('--requester', dest='requester_id', metavar='ORCID', default=None,
                        help='Filter to one user\'s requests (admin use)')
    parser.add_argument('--limit', type=int, default=100, metavar='N')
    parser.set_defaults(func=_execute_list)


def _execute_list(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        status = None if args.status == 'all' else args.status
        records = client.access_groups.list_join_requests(
            group_name=args.group_name, status=status,
            requester_id=args.requester_id, limit=args.limit,
        )
        term.header(f"Join Requests — {args.status} ({len(records)})")
        if not records:
            print(f"  {term.dim('No join requests found.')}")
            return
        term.table(_table_rows(records, client=client),
                  ['ID', 'Group', 'Status', 'Requester', 'Requested'],
                  max_widths=[6, 25, 10, 25, 12])
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
    parser.add_argument('--status', choices=['pending', 'approved', 'rejected', 'all'],
                        default='pending', help='Filter by status (default: pending)')
    parser.add_argument('--limit', type=int, default=100, metavar='N')
    parser.set_defaults(func=_execute_mine)


def _execute_mine(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        status = None if args.status == 'all' else args.status
        records = client.account.join_requests(status=status, limit=args.limit)
        term.header(f"My Join Requests — {args.status} ({len(records)})")
        if not records:
            print(f"  {term.dim('No join requests found.')}")
            return
        term.table(_table_rows(records, client=client),
                  ['ID', 'Group', 'Status', 'Requester', 'Requested'],
                  max_widths=[6, 25, 10, 25, 12])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── get ───────────────────────────────────────────────────────────────────────

def _register_get(subparsers):
    parser = subparsers.add_parser(
        'get',
        help='Get a join request by ID (admin only)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag get 42
""",
    )
    parser.add_argument('request_id', type=int, metavar='REQUEST_ID', help='Join request ID')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        record = client.access_groups.get(args.request_id)
        if record is None:
            logger.error(f"Join request not found: {args.request_id}")
            sys.exit(1)
        _show_join_request(record, client=client)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── approve / reject ───────────────────────────────────────────────────────────

def _register_approve(subparsers):
    parser = subparsers.add_parser(
        'approve',
        help='Approve one or more pending join requests (admin or group lead)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ag approve 42
    crucible ag approve 42 43 44 -m "Welcome aboard"
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of join requests to approve')
    parser.add_argument('-m', '--message', dest='reviewer_notes', metavar='TEXT', default=None,
                        help='Optional reviewer notes')
    parser.set_defaults(func=_execute_approve)


def _execute_approve(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)

    had_error = False
    for rid in args.request_id:
        try:
            record = client.access_groups.approve_join_request(rid, reviewer_notes=args.reviewer_notes)
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
        help='Reject one or more pending join requests (admin or group lead)',
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
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
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
