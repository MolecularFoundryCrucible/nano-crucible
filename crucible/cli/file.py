#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File subcommand for Crucible CLI - file-ID-scoped operations.

Operations that take a dataset ID (list-files, add-file, bulk download)
live under 'crucible dataset'. Operations that take a file MFID live here.
"""

import os
import sys
import logging
from . import term

logger = logging.getLogger(__name__)


def _bare_name(file_record: dict) -> str:
    """Extract display filename from a file record."""
    sp = file_record.get('storage_path') or ''
    if sp.startswith('mf-storage-prod/'):
        # strip mf-storage-prod/{dsid}/
        after_bucket = sp[len('mf-storage-prod/'):]
        _, _, name = after_bucket.partition('/')
        return name or after_bucket
    staging = file_record.get('filename') or ''
    return os.path.basename(staging) or file_record.get('mfid', '')


def _status_label(file_record: dict) -> str:
    """Short colored status for a file record: ingested / pending / a non-gcs backend name."""
    backend = file_record.get('storage_backend') or 'gcs'
    if backend != 'gcs':
        return backend
    return term.green('ingested') if file_record.get('storage_path') else term.yellow('pending')


def register_subcommand(subparsers):
    """Register the top-level 'file' subcommand."""
    parser = subparsers.add_parser(
        'file',
        help='File operations by file MFID',
        description='Inspect and download individual files using their MFID.',
    )
    file_subparsers = parser.add_subparsers(dest='file_command', metavar='COMMAND')
    file_subparsers.required = True

    _register_list(file_subparsers)
    _register_get(file_subparsers)
    _register_download(file_subparsers)
    _register_ingestion(file_subparsers)
    _register_request_ingestion(file_subparsers)
    _register_delete(file_subparsers)


def _register_list(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='List files (all or scoped to a dataset)',
        description='List files across all datasets, or scoped to a specific dataset.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file list
    crucible file list --dataset DSID
    crucible file list --limit 50
    crucible file list --sha256 abc123...
""",
    )
    parser.add_argument(
        '--dataset', '-d', metavar='DSID', default=None,
        help='Scope to a specific dataset (faster than global list)',
    )
    parser.add_argument(
        '--limit', type=int, default=100, metavar='N',
        help='Maximum number of files to return (default: 100)',
    )
    parser.add_argument(
        '--sha256', metavar='HASH',
        help='Filter by SHA-256 hex digest',
    )
    parser.set_defaults(func=_execute_list)


def _execute_list(args):
    """Execute 'crucible file list'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        dsid = getattr(args, 'dataset', None)
        if dsid:
            files = client.datasets.list_files(dsid)
        else:
            files = client.files.list(limit=args.limit, sha256_hash=args.sha256)

        sha256_filter = getattr(args, 'sha256', None)
        if sha256_filter and dsid:
            files = [f for f in files if f.get('sha256_hash', '').startswith(sha256_filter)]

        header = f"Files · {dsid} ({len(files)})" if dsid else f"Files ({len(files)})"
        term.header(header)
        if not files:
            print(f"  {term.dim('No files found.')}")
            return

        rows = []
        for f in files:
            name         = _bare_name(f)
            size         = term.fmt_size(f.get('size')) if f.get('size') is not None else '-'
            mfid         = f.get('mfid', '')
            dataset_mfid = f.get('dataset_mfid', '')
            status       = _status_label(f)
            rows.append((name, size, term.cyan(mfid), term.cyan(dataset_mfid), status))

        term.table(
            rows,
            ['File', 'Size', 'MFID', 'Dataset', 'Status'],
            max_widths=[40, 10, 26, 26, 10],
            min_widths=[4, 4, 26, 26, 6],
        )

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_get(subparsers):
    parser = subparsers.add_parser(
        'get',
        help='Show file metadata and download link',
        description='Display metadata for a file by its MFID. '
                    'Includes a signed download link if the file has been ingested.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file get mf_abc123
""",
    )
    parser.add_argument('file_id', metavar='FILE_ID', help='File MFID')
    parser.set_defaults(func=_execute_get)


def _execute_get(args):
    """Execute 'crucible file get'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        f = client.files.get(args.file_id)

        _p = term.field_printer(12)
        term.header("File")
        _p("MFID",    term.cyan(f.get('mfid')) if f.get('mfid') else None)
        _p("Dataset", term.cyan(f.get('dataset_mfid')) if f.get('dataset_mfid') else None)
        _p("Name",    _bare_name(f))
        _p("Size",    term.fmt_size(f.get('size')))
        _p("SHA256",  f.get('sha256_hash'))

        backend = f.get('storage_backend') or 'gcs'
        if backend != 'gcs':
            _p("Status",   f"Cataloged ({backend})")
            _p("Location", f.get('storage_path') or term.dim("(not set)"))
            if f.get('access_note'):
                _p("Access note", f['access_note'])
        elif f.get('storage_path'):
            _p("Status", term.green("Ingested"))
            try:
                url = client.files.get_download_link(args.file_id)
                _p("Download", term.navigation_link(_bare_name(f), url))
            except Exception:
                _p("Download", term.dim("unavailable"))
        else:
            _p("Status", term.yellow("Pending ingestion"))

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_download(subparsers):
    parser = subparsers.add_parser(
        'download',
        help='Download a single file by MFID',
        description='Download a file to a local directory using its MFID.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file download mf_abc123
    crucible file download mf_abc123 -o my_data/
""",
    )
    parser.add_argument('file_id', metavar='FILE_ID', help='File MFID')
    parser.add_argument(
        '-o', '--output-dir',
        dest='output_dir',
        default='.',
        metavar='DIR',
        help='Directory to save the file (default: current directory)',
    )
    parser.set_defaults(func=_execute_download)


def _execute_download(args):
    """Execute 'crucible file download'."""
    import requests as _requests
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        try:
            output_path = client.files.download(args.file_id, output_dir=args.output_dir)
        except RuntimeError as e:
            logger.error(str(e))
            sys.exit(1)
        except _requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.error(f"File {args.file_id} is not yet available for download")
            else:
                logger.error(f"Failed to download: {e}")
            sys.exit(1)

        term.success(f"Downloaded {output_path}", args)

    except SystemExit:
        raise
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_delete(subparsers):
    parser = subparsers.add_parser(
        'delete',
        help='Delete a file by MFID',
        description=(
            'Permanently delete a file record and its stored data. '
            'Prompts for confirmation unless -y is given.'
        ),
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file delete mf_abc123
    crucible file delete mf_abc123 --yes
""",
    )
    parser.add_argument('file_id', metavar='FILE_MFID', help='File MFID')
    parser.add_argument(
        '-y', '--yes', action='store_true',
        help='Confirm deletion without prompting',
    )
    parser.set_defaults(func=_execute_delete)


def _execute_delete(args):
    """Execute 'crucible file delete'."""
    from crucible.client import CrucibleClient
    from .helpers import prompt_confirm
    confirmed = args.yes or prompt_confirm(
        f"Delete file {args.file_id}? This cannot be undone.",
        option='--yes',
    )
    if not confirmed:
        print("Aborted.")
        return
    try:
        client = CrucibleClient()
        client.files.delete(args.file_id)
        term.success(f"Deleted {args.file_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("deleting file", e, args)


def _register_ingestion(subparsers):
    parser = subparsers.add_parser(
        'ingestion',
        help='Show ingestion requests for a file',
        description='List ingestion requests for a file by its MFID.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file ingestion mf_abc123
""",
    )
    parser.add_argument('file_id', metavar='FILE_ID', help='File MFID')
    parser.set_defaults(func=_execute_ingestion)


def _execute_ingestion(args):
    """Execute 'crucible file ingestion'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        reqs = client.ingestions.list(file_id=args.file_id)

        term.header(f"Ingestion Requests · {args.file_id} ({len(reqs)})")
        if not reqs:
            print(f"  {term.dim('No ingestion requests found.')}")
            return

        rows = []
        for r in reqs:
            rows.append((
                str(r.get('id', '-')),
                term.status_label(r.get('status')),
                r.get('ingestion_class') or '-',
                term.fmt_ts(r.get('created_at') or r.get('creation_time')) or '-',
            ))
        term.table(rows, ['ID', 'Status', 'Class', 'Created'], max_widths=[8, 12, 25, 20])

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_request_ingestion(subparsers):
    parser = subparsers.add_parser(
        'request-ingestion',
        help='(Re)request ingestion for a cataloged file',
        description="Request ingestion for a file that hasn't been ingested yet, e.g. one "
                    "cataloged without upload via 'dataset create --no-upload'.",
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file request-ingestion mf_abc123
    crucible file request-ingestion mf_abc123 --ingestor lammps
    crucible file request-ingestion mf_abc123 --wait
""",
    )
    parser.add_argument('file_id', metavar='FILE_ID', help='File MFID')
    parser.add_argument(
        '--ingestor',
        default=None,
        metavar='CLASS',
        help='Ingestion class to use (default: auto-detected from file format)'
    )
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait for ingestion to complete before returning'
    )
    parser.set_defaults(func=_execute_request_ingestion)


def _execute_request_ingestion(args):
    """Execute 'crucible file request-ingestion'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        req = client.files.request_ingestion(
            args.file_id,
            ingestion_class=getattr(args, 'ingestor', None),
            wait_for_response=getattr(args, 'wait', False),
        )

        term.header(f"Ingestion Requested · {args.file_id}")
        _p = term.field_printer(8)
        _p("ID",     req.get('id'))
        _p("Status", term.status_label(req.get('status')))
        _p("Class",  req.get('ingestion_class') or '-')

    except Exception as e:
        from .helpers import fail
        fail("", e, args)
