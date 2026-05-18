#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unlink subcommand for removing relationships between Crucible resources.

Supports unlinking:
- Dataset from sample (and vice versa) — resource types auto-detected
- Dataset from parent dataset — resource types auto-detected
- Sample from parent sample — resource types auto-detected
"""

import sys
import logging
from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the unlink subcommand."""
    parser = subparsers.add_parser(
        'unlink',
        help='Unlink Crucible resources',
        description='Remove the association between two Crucible resources',
        formatter_class=lambda prog: term.ColorHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Unlink two resources (types auto-detected)
    crucible unlink MFID1 MFID2

    # Legacy flag syntax (still supported)
    crucible unlink -p parent_id -c child_id
    crucible unlink -d dataset_id -s sample_id
"""
    )

    parser.add_argument(
        'id1',
        nargs='?',
        metavar='ID1',
        help='First resource ID'
    )
    parser.add_argument(
        'id2',
        nargs='?',
        metavar='ID2',
        help='Second resource ID'
    )
    parser.add_argument(
        '-p', '--parent',
        metavar='ID',
        help='First resource ID (legacy)'
    )
    parser.add_argument(
        '-c', '--child',
        metavar='ID',
        help='Second resource ID (legacy)'
    )
    parser.add_argument(
        '-d', '--dataset',
        metavar='ID',
        help='Dataset ID (legacy)'
    )
    parser.add_argument(
        '-s', '--sample',
        metavar='ID',
        help='Sample ID (legacy)'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the unlink command."""
    from crucible.client import CrucibleClient

    if args.id1 and args.id2:
        try:
            CrucibleClient().unlink(args.id1, args.id2)
            logger.info(f"✓ Unlinked resources successfully")
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to unlink resources: {e}")
            sys.exit(1)

    elif args.dataset and args.sample:
        logger.info(f"Unlinking sample '{args.sample}' from dataset '{args.dataset}'...")
        try:
            CrucibleClient().datasets.remove_sample(args.dataset, args.sample)
            logger.info(f"✓ Unlinked sample {args.sample} from dataset {args.dataset}")
        except Exception as e:
            logger.error(f"Failed to unlink resources: {e}")
            sys.exit(1)

    elif args.parent and args.child:
        try:
            CrucibleClient().unlink(args.parent, args.child)
            logger.info(f"✓ Unlinked resources successfully")
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to unlink resources: {e}")
            sys.exit(1)

    else:
        logger.error("Usage: crucible unlink ID1 ID2")
        sys.exit(1)
