#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Link subcommand for creating relationships between Crucible resources.

Supports linking:
- Dataset to dataset (parent-child)
- Sample to sample (parent-child)
- Sample to dataset
"""

import sys
import logging

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the link subcommand."""
    parser = subparsers.add_parser(
        'link',
        help='Link Crucible resources (datasets, samples)',
        description='Create parent-child relationships between datasets or samples, or link samples to datasets',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Link two datasets (resource types auto-detected)
    crucible link -p parent_dataset_id -c child_dataset_id

    # Link two samples (resource types auto-detected)
    crucible link -p parent_sample_id -c child_sample_id

    # Link sample to dataset
    crucible link -d dataset_id -s sample_id
"""
    )

    # Parent-child relationship flags
    parser.add_argument(
        '-p', '--parent',
        metavar='ID',
        help='Parent resource ID'
    )

    parser.add_argument(
        '-c', '--child',
        metavar='ID',
        help='Child resource ID'
    )

    # Dataset-sample relationship flags
    parser.add_argument(
        '-d', '--dataset',
        metavar='ID',
        help='Dataset ID (for linking sample to dataset)'
    )

    parser.add_argument(
        '-s', '--sample',
        metavar='ID',
        help='Sample ID (for linking sample to dataset)'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the link command."""
    from crucible.client import CrucibleClient

    # Determine parent and child IDs
    if args.dataset and args.sample:
        # Case 1: Explicit dataset + sample flags
        parent_id = args.dataset
        child_id = args.sample
        logger.info(f"Linking sample '{child_id}' to dataset '{parent_id}'...")
    elif args.parent and args.child:
        # Case 2: Generic parent-child flags (auto-detects resource types)
        parent_id = args.parent
        child_id = args.child
    else:
        logger.error("Invalid arguments. Use either:")
        logger.error("  -p/--parent and -c/--child for linking resources")
        logger.error("  -d/--dataset and -s/--sample for linking sample to dataset")
        sys.exit(1)

    # Use the unified link method
    try:
        CrucibleClient().link(parent_id, child_id)
        logger.info("Successfully linked resources")
    except Exception as e:
        logger.error(f"Failed to link resources: {e}")
        sys.exit(1)
