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


def _register_list(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='List all files across datasets',
        description='List all files you have access to across all datasets.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible file list
    crucible file list --limit 50
    crucible file list --sha256 abc123...
""",
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
        files = client.datasets.list_files(limit=args.limit, sha256_hash=args.sha256)

        term.header(f"Files ({len(files)})")
        if not files:
            print(f"  {term.dim('No files found.')}")
            return

        rows = []
        for f in files:
            name    = _bare_name(f)
            size    = term.fmt_size(f.get('size')) if f.get('size') is not None else '-'
            mfid    = f.get('mfid', '')
            status  = term.green('ingested') if f.get('storage_path') else term.yellow('pending')
            rows.append((term.cyan(name), size, term.dim(mfid), status))

        term.table(rows, ['File', 'Size', 'MFID', 'Status'], max_widths=[40, 10, 30, 10])

    except Exception as e:
        logger.error(f"Error: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


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
        f = client.datasets.get_file(args.file_id)

        _p = term.field_printer(12)
        term.header("File")
        _p("MFID",   f.get('mfid'))
        _p("Name",   _bare_name(f))
        _p("Size",   term.fmt_size(f.get('size')))
        _p("SHA256", f.get('sha256_hash'))

        if f.get('storage_path'):
            _p("Status", term.green("Ingested"))
            try:
                url = client.datasets.get_download_link(args.file_id)
                _p("Download", term.hyperlink(term.cyan("link"), url))
            except Exception:
                _p("Download", term.dim("unavailable"))
        else:
            _p("Status", term.yellow("Pending ingestion"))

    except Exception as e:
        logger.error(f"Error: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


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
    import tempfile
    import requests as _requests
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()

        f    = client.datasets.get_file(args.file_id)
        name = _bare_name(f)

        if not f.get('storage_path'):
            logger.error(f"{name} has not been ingested yet - cannot download")
            sys.exit(1)

        try:
            url = client.datasets.get_download_link(args.file_id)
        except _requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.error(f"{name} is not yet available for download")
            else:
                logger.error(f"Failed to get download link: {e}")
            sys.exit(1)

        output_path = os.path.join(args.output_dir, name)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        logger.info(f"Downloading {name}...")
        response = client._session.get(url, stream=True)
        response.raise_for_status()

        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(output_path)))
        try:
            with os.fdopen(tmp_fd, 'wb') as out:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    out.write(chunk)
            os.replace(tmp_path, output_path)
        except Exception:
            os.unlink(tmp_path)
            raise

        print(f"  {term.green('✓')} {output_path}")

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
