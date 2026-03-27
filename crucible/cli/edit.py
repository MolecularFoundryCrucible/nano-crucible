#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Top-level edit subcommand — edit any resource by MFID.

Automatically detects whether the ID refers to a dataset or sample
and opens the appropriate fields in $EDITOR.
"""

import sys
import logging

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the top-level 'edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit a resource by MFID (auto-detects type)',
        description='Edit a dataset or sample — resource type is detected automatically.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible edit 0td7evvtg5wb90005k1j97ak94
    EDITOR=vim crucible edit 0td7evvtg5wb90005k1j97ak94
"""
    )

    parser.add_argument(
        'resource_id',
        metavar='ID',
        help='Resource MFID (dataset or sample)'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the top-level edit command."""
    from crucible.client import CrucibleClient

    try:
        client = CrucibleClient()
        resource_type = client.get_resource_type(args.resource_id)

        if resource_type == 'dataset':
            from .dataset import _edit_dataset
            _edit_dataset(args.resource_id, client, debug=getattr(args, 'debug', False))

        elif resource_type == 'sample':
            from .sample import _edit_sample
            _edit_sample(args.resource_id, client, debug=getattr(args, 'debug', False))

        else:
            logger.error(f"Could not determine resource type for: {args.resource_id}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error editing {args.resource_id}: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
