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
    from pycrucible.config import config

    # Validate arguments
    if args.dataset and args.sample:
        # Case 1: Link sample to dataset
        _link_sample_to_dataset(config, args.dataset, args.sample)
    elif args.parent and args.child:
        # Case 2: Link parent-child relationship
        if args.type:
            # Explicit type provided
            _link_with_explicit_type(config, args.parent, args.child, args.type)
        else:
            # Auto-detect types
            _link_with_autodetect(config, args.parent, args.child)
    else:
        logger.error("Invalid arguments. Use either:")
        logger.error("  -p/--parent and -c/--child for parent-child relationships")
        logger.error("  -d/--dataset and -s/--sample for sample-to-dataset linking")
        sys.exit(1)


def _link_sample_to_dataset(config, dataset_id, sample_id):
    """Link a sample to a dataset."""
    logger.info(f"Linking sample '{sample_id}' to dataset '{dataset_id}'...")

    try:
        result = config.client.add_sample_to_dataset(dataset_id, sample_id)
        logger.info(f"Successfully linked sample to dataset")
        logger.debug(f"Result: {result}")
    except Exception as e:
        logger.error(f"Failed to link sample to dataset: {e}")
        sys.exit(1)


def _link_with_explicit_type(config, parent_id, child_id, resource_type):
    """Link resources with explicitly specified type."""
    logger.info(f"Linking {resource_type}s: '{parent_id}' (parent) -> '{child_id}' (child)")

    try:
        if resource_type == 'dataset':
            result = config.client.link_datasets(parent_id, child_id)
            logger.info(f"Successfully linked datasets")
        elif resource_type == 'sample':
            result = config.client.link_samples(parent_id, child_id)
            logger.info(f"Successfully linked samples")
        logger.debug(f"Result: {result}")
    except Exception as e:
        logger.error(f"Failed to link {resource_type}s: {e}")
        sys.exit(1)


def _link_with_autodetect(config, parent_id, child_id):
    """Link resources with auto-detection of resource types."""
    logger.info("Auto-detecting resource types...")

    # Try to detect parent type
    parent_type = _detect_resource_type(config, parent_id)
    if not parent_type:
        logger.error(f"Could not determine type of parent resource '{parent_id}'")
        sys.exit(1)

    # Try to detect child type
    child_type = _detect_resource_type(config, child_id)
    if not child_type:
        logger.error(f"Could not determine type of child resource '{child_id}'")
        sys.exit(1)

    # Check that both are the same type
    if parent_type != child_type:
        logger.error(f"Type mismatch: parent is {parent_type}, child is {child_type}")
        logger.error("Both resources must be the same type for parent-child linking")
        sys.exit(1)

    logger.info(f"Detected: both are {parent_type}s")
    _link_with_explicit_type(config, parent_id, child_id, parent_type)


def _detect_resource_type(config, resource_id):
    """
    Detect if a resource is a dataset or sample.

    Returns:
        str: 'dataset' or 'sample', or None if not found
    """
    resource_type, _ = config.client.get_resource_type(resource_id)
    if resource_type:
        logger.debug(f"'{resource_id}' is a {resource_type}")
    return resource_type
