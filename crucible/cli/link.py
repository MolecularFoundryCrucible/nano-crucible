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
from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the link subcommand."""
    from crucible.constants import RELATIONSHIP_TYPES

    parser = subparsers.add_parser(
        'link',
        help='Link Crucible resources (datasets, samples)',
        description='Create parent-child relationships between datasets or samples, or link samples to datasets',
        formatter_class=lambda prog: term.ColorHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Link two datasets (resource types auto-detected)
    crucible link -p PARENT_DATASET_MFID -c CHILD_DATASET_MFID

    # Link two samples (resource types auto-detected)
    crucible link -p PARENT_SAMPLE_MFID -c CHILD_SAMPLE_MFID

    # Link sample to dataset
    crucible link -d DATASET_MFID -s SAMPLE_MFID

    # Record what kind of link it is (parent-child links only)
    crucible link -p PARENT_MFID -c CHILD_MFID --relationship-type is_part_of
"""
    )

    # Parent-child relationship flags
    parser.add_argument(
        '-p', '--parent',
        metavar='MFID',
        help='Parent resource MFID'
    )

    parser.add_argument(
        '-c', '--child',
        metavar='MFID',
        help='Child resource MFID'
    )

    # Dataset-sample relationship flags
    parser.add_argument(
        '-d', '--dataset',
        metavar='MFID',
        help='Dataset MFID'
    )

    parser.add_argument(
        '-s', '--sample',
        metavar='MFID',
        help='Sample MFID'
    )

    parser.add_argument(
        '--relationship-type',
        choices=RELATIONSHIP_TYPES,
        metavar='TYPE',
        help=f"Kind of link, describing the child relative to the parent "
             f"({', '.join(RELATIONSHIP_TYPES)}). Only applies to "
             f"dataset-to-dataset and sample-to-sample links."
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the link command."""
    from crucible.client import CrucibleClient

    # Determine parent and child IDs
    if args.dataset and args.sample:
        # Case 1: Explicit dataset + sample flags. The pair is known here
        # without a lookup, so reject the type now rather than after two
        # round trips inside client.link().
        if args.relationship_type:
            logger.error(
                "--relationship-type does not apply when linking a sample to a "
                "dataset; it is only meaningful for -p/--parent with -c/--child.")
            sys.exit(1)
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
        CrucibleClient().link(parent_id, child_id, args.relationship_type)
        term.success("Linked resources", args)
    except Exception as e:
        logger.error(f"Failed to link resources: {e}")
        sys.exit(1)
