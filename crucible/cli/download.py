#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download subcommand — download a sample or dataset record and its files.
"""

import sys
import logging

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the download subcommand."""
    parser = subparsers.add_parser(
        'download',
        help='Download a sample or dataset',
        description=(
            'Download a resource record as record.json and, for datasets, '
            'any associated files.'
        ),
    )
    parser.add_argument(
        'resource_id',
        help='Unique ID of the sample or dataset to download',
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='crucible-downloads',
        help='Directory to save files (default: crucible-downloads/)',
    )
    parser.add_argument(
        '--no-files',
        action='store_true',
        default=False,
        help='Download record JSON only, skip data files',
    )
    parser.add_argument(
        '--no-record',
        action='store_true',
        default=False,
        help='Skip saving record.json, download data files only',
    )
    parser.add_argument(
        '--no-overwrite',
        action='store_true',
        default=False,
        help='Skip files that already exist locally',
    )
    parser.add_argument(
        '--include',
        nargs='+',
        metavar='PATTERN',
        help='Glob patterns — only download matching files (e.g. "*.h5")',
    )
    parser.add_argument(
        '--exclude',
        nargs='+',
        metavar='PATTERN',
        help='Glob patterns — skip matching files (e.g. "*.log")',
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the download command."""
    from crucible.config import config
    try:
        downloaded = config.client.download(
            args.resource_id,
            output_dir=args.output_dir,
            no_files=args.no_files,
            no_record=args.no_record,
            overwrite_existing=not args.no_overwrite,
            include=args.include,
            exclude=args.exclude,
        )
        for path in downloaded:
            logger.info(path)
    except Exception as e:
        logger.error(f"Error downloading {args.resource_id}: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
