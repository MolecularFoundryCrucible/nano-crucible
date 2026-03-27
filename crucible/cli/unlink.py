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

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the unlink subcommand."""
    parser = subparsers.add_parser(
        'unlink',
        help='Unlink Crucible resources',
        description='Remove the association between two Crucible resources',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Unlink two resources (types auto-detected: dataset-sample, dataset-dataset, sample-sample)
    crucible unlink -p parent_id -c child_id

    # Explicit dataset/sample flags
    crucible unlink -d dataset_id -s sample_id
"""
    )

    parser.add_argument(
        '-p', '--parent',
        metavar='ID',
        help='First resource ID (type auto-detected)'
    )
    parser.add_argument(
        '-c', '--child',
        metavar='ID',
        help='Second resource ID (type auto-detected)'
    )
    parser.add_argument(
        '-d', '--dataset',
        metavar='ID',
        help='Dataset ID'
    )
    parser.add_argument(
        '-s', '--sample',
        metavar='ID',
        help='Sample ID'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the unlink command."""
    from crucible.config import config

    if args.dataset and args.sample:
        logger.info(f"Unlinking sample '{args.sample}' from dataset '{args.dataset}'...")
        try:
            result = config.client.datasets.remove_sample(args.dataset, args.sample)
            logger.info(f"✓ Unlinked sample {args.sample} from dataset {args.dataset}")
        except Exception as e:
            logger.error(f"Failed to unlink resources: {e}")
            sys.exit(1)

    elif args.parent and args.child:
        try:
            result = config.client.unlink(args.parent, args.child)
            logger.info(f"✓ Unlinked resources successfully")
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to unlink resources: {e}")
            sys.exit(1)

    else:
        logger.error("Invalid arguments. Use either:")
        logger.error("  -p/--parent and -c/--child for auto-detected unlinking")
        logger.error("  -d/--dataset and -s/--sample for explicit unlinking")
        sys.exit(1)
