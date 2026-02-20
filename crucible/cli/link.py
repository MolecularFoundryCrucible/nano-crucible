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
    # Link two datasets (auto-detect)
    crucible link -p parent_dataset_id -c child_dataset_id

    # Link two samples (auto-detect)
    crucible link -p parent_sample_id -c child_sample_id

    # Link with explicit type (skip auto-detection)
    crucible link -p parent_id -c child_id --type dataset
    crucible link -p parent_id -c child_id --type sample

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

    # Optional type specification to skip auto-detection
    parser.add_argument(
        '--type',
        choices=['dataset', 'sample'],
        help='Resource type (dataset or sample) to skip auto-detection'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the link command."""
    from crucible.config import config

    # Determine parent and child IDs
    if args.dataset and args.sample:
        # Case 1: Explicit dataset + sample flags
        parent_id = args.dataset
        child_id = args.sample
        logger.info(f"Linking sample '{child_id}' to dataset '{parent_id}'...")
    elif args.parent and args.child:
        # Case 2: Generic parent-child flags
        parent_id = args.parent
        child_id = args.child

        # Auto-detect types if not explicitly provided
        if not args.type:
            logger.info("Auto-detecting resource types...")
            try:
                parent_type = config.client.get_resource_type(parent_id)
                child_type = config.client.get_resource_type(child_id)
                logger.info(f"Detected: parent is {parent_type}, child is {child_type}")
            except Exception as e:
                logger.error(f"Failed to detect resource types: {e}")
                sys.exit(1)
        else:
            logger.info(f"Linking {args.type}s: '{parent_id}' (parent) -> '{child_id}' (child)")
    else:
        logger.error("Invalid arguments. Use either:")
        logger.error("  -p/--parent and -c/--child for linking resources")
        logger.error("  -d/--dataset and -s/--sample for linking sample to dataset")
        sys.exit(1)

    # Use the unified link method
    try:
        result = config.client.link(parent_id, child_id)
        logger.info("Successfully linked resources")
        logger.debug(f"Result: {result}")
    except Exception as e:
        logger.error(f"Failed to link resources: {e}")
        sys.exit(1)
