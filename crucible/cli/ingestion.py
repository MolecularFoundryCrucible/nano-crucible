#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingestion subcommand — manage ingestion requests.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    parser = subparsers.add_parser(
        'ingestion',
        help='Manage ingestion requests',
        description='List, inspect, and wait on ingestion requests.',
    )
    sub = parser.add_subparsers(dest='ingestion_command', metavar='COMMAND')
    sub.required = True

    _register_list(sub)
    _register_get(sub)
    _register_wait(sub)
    _register_list_ingestors(sub)


def _register_list(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='List ingestion requests',
        description='List ingestion requests, optionally scoped to a dataset or file.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ingestion list
    crucible ingestion list --dataset DSID
    crucible ingestion list --file FILE_ID
""",
    )
    parser.add_argument('--dataset', '-d', dest='dataset_id', default=None,
                        metavar='DSID', help='Filter by dataset ID')
    parser.add_argument('--file', '-f', dest='file_id', default=None,
                        metavar='FILE_ID', help='Filter by file MFID')
    parser.add_argument('--limit', '-l', type=int, default=50, metavar='N',
                        help='Maximum results (default: 50)')
    parser.set_defaults(func=_execute_list)


def _execute_list(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        reqs   = client.ingestions.list(dsid=args.dataset_id,
                                        file_id=args.file_id,
                                        limit=args.limit)

        scope = args.dataset_id or args.file_id or 'all'
        term.header(f"Ingestion Requests · {scope} ({len(reqs)})")
        if not reqs:
            print(f"  {term.dim('No ingestion requests found.')}")
            return

        rows = []
        for r in reqs:
            rows.append((
                str(r.get('id', '-')),
                term.status_label(r.get('status')),
                r.get('ingestion_class') or '-',
                term.cyan(r.get('file_mfid')) if r.get('file_mfid') else '-',
                term.fmt_ts(r.get('time_created')) or '-',
            ))
        term.table(rows, ['ID', 'Status', 'Class', 'File MFID', 'Created'],
                   max_widths=[8, 12, 25, 30, 20])

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_list_ingestors(subparsers):
    parser = subparsers.add_parser(
        'list-ingestors',
        help='List available ingestion classes',
        description='List the ingestion classes available on the server.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ingestion list-ingestors
""",
    )
    parser.set_defaults(func=_execute_list_ingestors)


def _execute_list_ingestors(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        ingestors = client.ingestions.list_ingestors()

        term.header(f"Ingestors ({len(ingestors)})")
        if not ingestors:
            print(f"  {term.dim('No ingestors found.')}")
            return
        for name in ingestors:
            print(f"  {name}")

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_get(subparsers):
    parser = subparsers.add_parser(
        'get',
        help='Get a single ingestion request',
        description='Show details of a single ingestion request by ID.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ingestion get 42
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', type=int,
                        help='Integer ingestion request ID')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        r = client.ingestions.get(args.request_id)
        _p = term.field_printer(16)
        term.header(f"Ingestion Request #{r.get('id')}")
        _p("Status",  term.status_label(r.get('status')))
        _p("Class",   r.get('ingestion_class') or '-')
        _p("File",    r.get('file_mfid') or '-')
        _p("Dataset", r.get('dataset_mfid') or '-')
        _p("Created", term.fmt_ts(r.get('time_created')))
        if r.get('time_completed'):
            _p("Completed", term.fmt_ts(r.get('time_completed')))
        if r.get('error_message'):
            _p("Error", term.red(r.get('error_message')))

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_wait(subparsers):
    parser = subparsers.add_parser(
        'wait',
        help='Wait for an ingestion request to complete',
        description='Poll an ingestion request until it reaches a terminal state.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible ingestion wait 42
""",
    )
    parser.add_argument('request_id', metavar='REQUEST_ID', type=int,
                        help='Integer ingestion request ID')
    parser.set_defaults(func=_execute_wait)


def _execute_wait(args):
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        logger.info(f"Waiting for ingestion request {args.request_id}...")
        r = client.ingestions.wait(args.request_id)
        status = r.get('status', '-')
        if status == 'complete':
            term.success(f"Ingestion {args.request_id} completed", args)
        else:
            logger.error(f"Ingestion {args.request_id} ended with status: {status}")
            sys.exit(1)

    except Exception as e:
        from .helpers import fail
        fail("", e, args)
