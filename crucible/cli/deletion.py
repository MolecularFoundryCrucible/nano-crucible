#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletion subcommand for Crucible CLI.

Provides the soft-deletion workflow: users submit deletion requests,
admins approve or reject them.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    """Register the deletion subcommand with the main parser."""
    parser = subparsers.add_parser(
        'deletion',
        help='Deletion request workflow (request, approve, reject)',
        description='Manage soft-deletion requests. Users submit requests; admins approve or reject.',
    )

    deletion_subparsers = parser.add_subparsers(
        title='deletion commands',
        dest='deletion_command',
        help='Available deletion operations',
    )

    _register_request(deletion_subparsers)
    _register_list(deletion_subparsers)
    _register_get(deletion_subparsers)
    _register_approve(deletion_subparsers)
    _register_reject(deletion_subparsers)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _short_ts(ts):
    """YYYY-MM-DD — compact enough for a table column."""
    if not ts:
        return '—'
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(ts).strip())
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return str(ts)


def _status_label(status):
    """Return a styled status string."""
    if not status:
        return '—'
    if not (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()):
        return status
    if status == 'pending':
        return f"\033[33m{status}\033[0m"    # yellow
    if status == 'approved':
        return f"\033[32m{status}\033[0m"    # green
    if status == 'rejected':
        return f"\033[31m{status}\033[0m"    # red
    return status


def _show_deletion_request(record):
    """Print a DeletionRequest record."""
    _p = term.field_printer(16)
    term.header("Deletion Request")
    _p("Request ID",   record.get('id'))
    _p("Resource ID",  term.mfid_link(record.get('resource_id') or ''))
    _p("Resource Type", record.get('resource_type'))
    _p("Name",         record.get('resource_name'))
    _p("Status",       _status_label(record.get('status')))
    _p("Reason",       record.get('reason'))
    _p("Requested",    term.fmt_ts(record.get('request_time')))
    _p("Requester ID", record.get('requester_id'))
    if record.get('reviewer_notes') or record.get('review_time'):
        _p("Review Time",  term.fmt_ts(record.get('review_time')))
        _p("Reviewer ID",  record.get('reviewer_id'))
        _p("Review Notes", record.get('reviewer_notes'))


# ── Subcommand registration ───────────────────────────────────────────────────

def _register_request(subparsers):
    """Register the 'deletion request' subcommand."""
    parser = subparsers.add_parser(
        'request',
        help='Submit a deletion request for a dataset or sample',
        description=(
            'Submit a soft-deletion request for a dataset or sample. '
            'The resource is immediately hidden from list results until an admin reviews the request.'
        ),
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible deletion request mf-abc123
    crucible deletion request mf-abc123 -m "Duplicate upload"
""",
    )
    parser.add_argument('resource_id', metavar='RESOURCE_ID',
                        help='MFID of the dataset or sample to delete')
    parser.add_argument('-m', '--message', metavar='TEXT', default=None,
                        dest='reason',
                        help='Optional reason for the deletion request')
    parser.set_defaults(func=_execute_request)


def _register_list(subparsers):
    """Register the 'deletion list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List deletion requests (admin)',
        description='List deletion requests. Shows pending by default. Requires admin.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible deletion list              # pending only (default)
    crucible deletion list --approved
    crucible deletion list --rejected
    crucible deletion list --all
""",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--approved', action='store_true', help='Show approved requests')
    group.add_argument('--rejected', action='store_true', help='Show rejected requests')
    group.add_argument('--all',      action='store_true', help='Show all requests regardless of status')
    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'deletion get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get a deletion request by ID (admin)',
        description='Fetch a single deletion request record. Requires admin.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible deletion get 42
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', type=int,
                        help='Integer ID of the deletion request')
    parser.set_defaults(func=_execute_get)


def _register_approve(subparsers):
    """Register the 'deletion approve' subcommand."""
    parser = subparsers.add_parser(
        'approve',
        help='Approve a pending deletion request (admin)',
        description='Approve a pending deletion request. The resource remains hidden. Requires admin.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible deletion approve 42
    crucible deletion approve 42 43 44 -m "Confirmed duplicate"
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of deletion requests to approve')
    parser.add_argument('-m', '--message', metavar='TEXT', default=None,
                        dest='notes',
                        help='Optional reviewer notes')
    parser.set_defaults(func=_execute_approve)


def _register_reject(subparsers):
    """Register the 'deletion reject' subcommand."""
    parser = subparsers.add_parser(
        'reject',
        help='Reject a pending deletion request (admin)',
        description='Reject a pending deletion request. The resource is restored to active. Requires admin.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible deletion reject 42
    crucible deletion reject 42 43 44 -m "Still referenced by active project"
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', nargs='+', type=int,
                        help='Integer ID(s) of deletion requests to reject')
    parser.add_argument('-m', '--message', metavar='TEXT', default=None,
                        dest='notes',
                        help='Optional reviewer notes')
    parser.set_defaults(func=_execute_reject)


# ── Execute functions ─────────────────────────────────────────────────────────

def _execute_request(args):
    """Execute the 'deletion request' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        record = client.deletions.request(args.resource_id, reason=args.reason)
        logger.info(f"✓ Deletion request submitted (ID: {record.get('id')})")
        print()
        _show_deletion_request(record)
    except Exception as e:
        logger.error(f"Error submitting deletion request: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list(args):
    """Execute the 'deletion list' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()

        if args.all:
            status = None
            status_label = 'all'
        elif args.approved:
            status = 'approved'
            status_label = 'approved'
        elif args.rejected:
            status = 'rejected'
            status_label = 'rejected'
        else:
            status = 'pending'
            status_label = 'pending'

        records = sorted(client.deletions.list(status=status), key=lambda r: r.get('id') or 0)

        term.header(f"Deletion Requests — {status_label} ({len(records)})")

        if not records:
            print(f"  {term.dim('No deletion requests found.')}")
            return

        try:
            from crucible.config import config
            _base = config.graph_explorer_url.rstrip('/')
        except Exception:
            _base = None

        rows = [
            (
                record.get('id'),
                term.mfid_link(record.get('resource_id') or '',
                               f"{_base}/{record.get('resource_id')}" if _base else None) or '—',
                record.get('resource_type') or '—',
                record.get('resource_name') or '—',
                _status_label(record.get('status') or ''),
                _short_ts(record.get('request_time')),
            )
            for record in records
        ]
        term.table(rows,
                   ['ID', 'Resource ID', 'Type', 'Name', 'Status', 'Requested'],
                   max_widths=[6, 26, 10, 15, 10, 10])
    except Exception as e:
        logger.error(f"Error listing deletion requests: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'deletion get' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        record = client.deletions.get(args.request_id)
        _show_deletion_request(record)
    except Exception as e:
        logger.error(f"Error fetching deletion request: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_approve(args):
    """Execute the 'deletion approve' subcommand."""
    from crucible.client import CrucibleClient
    client = CrucibleClient()
    for rid in args.request_id:
        try:
            record = client.deletions.approve(rid, reviewer_notes=args.notes)
            logger.info(f"✓ Deletion request {rid} approved")
            print()
            _show_deletion_request(record)
        except Exception as e:
            logger.error(f"Error approving deletion request {rid}: {e}")
            if getattr(args, 'debug', False):
                import traceback
                traceback.print_exc()


def _execute_reject(args):
    """Execute the 'deletion reject' subcommand."""
    from crucible.client import CrucibleClient
    client = CrucibleClient()
    for rid in args.request_id:
        try:
            record = client.deletions.reject(rid, reviewer_notes=args.notes)
            logger.info(f"✓ Deletion request {rid} rejected")
            print()
            _show_deletion_request(record)
        except Exception as e:
            logger.error(f"Error rejecting deletion request {rid}: {e}")
            if getattr(args, 'debug', False):
                import traceback
                traceback.print_exc()
