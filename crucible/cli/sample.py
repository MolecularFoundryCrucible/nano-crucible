#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample subcommand for Crucible CLI.

Provides sample-related operations: list, get, create, link, etc.
"""

import sys
import logging
import json

logger = logging.getLogger(__name__)

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def register_subcommand(subparsers):
    """
    Register the sample subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'sample',
        help='Sample operations (list, get, create, etc.)',
        description='Manage Crucible samples',
    )

    # Sample subcommands
    sample_subparsers = parser.add_subparsers(
        title='sample commands',
        dest='sample_command',
        help='Available sample operations'
    )

    # Register individual sample commands
    _register_list(sample_subparsers)
    _register_get(sample_subparsers)
    _register_create(sample_subparsers)
    _register_link(sample_subparsers)
    _register_link_dataset(sample_subparsers)


def _register_list(subparsers):
    """Register the 'sample list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List samples',
        description='List samples in a project'
    )

    parser.add_argument(
        '-pid', '--project-id',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses config current_project if not specified)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        metavar='N',
        help='Maximum number of results to return (default: 100)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_list)


def _register_get(subparsers):
    """Register the 'sample get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get sample by ID',
        description='Retrieve sample information'
    )

    sample_id_arg = parser.add_argument(
        'sample_id',
        metavar='SAMPLE_ID',
        help='Sample unique ID'
    )
    # Disable file completion for sample_id
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'sample create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new sample',
        description='Create a new sample in Crucible',
        epilog="""
Examples:
    crucible sample create -n "Silicon Wafer A" -pid my-project
    crucible sample create -n "Sample 001" -pid my-project --description "Test sample"
"""
    )

    parser.add_argument(
        '-n', '--name',
        required=True,
        metavar='NAME',
        help='Sample name'
    )

    parser.add_argument(
        '-pid', '--project-id',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses config current_project if not specified)'
    )

    parser.add_argument(
        '--description',
        default=None,
        metavar='TEXT',
        help='Sample description (optional)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_create)


def _register_link(subparsers):
    """Register the 'sample link' subcommand."""
    parser = subparsers.add_parser(
        'link',
        help='Link parent and child samples',
        description='Create a parent-child relationship between samples'
    )

    parser.add_argument(
        '-p', '--parent',
        required=True,
        metavar='PARENT_ID',
        help='Parent sample ID'
    )

    parser.add_argument(
        '-c', '--child',
        required=True,
        metavar='CHILD_ID',
        help='Child sample ID'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_link)


def _register_link_dataset(subparsers):
    """Register the 'sample link-dataset' subcommand."""
    parser = subparsers.add_parser(
        'link-dataset',
        help='Link a sample to a dataset',
        description='Associate a dataset with a sample'
    )

    parser.add_argument(
        '-s', '--sample',
        required=True,
        metavar='SAMPLE_ID',
        help='Sample ID'
    )

    parser.add_argument(
        '-d', '--dataset',
        required=True,
        metavar='DATASET_ID',
        help='Dataset ID'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_link_dataset)


def _execute_list(args):
    """Execute the 'sample list' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    # Get project_id
    project_id = args.project_id
    if project_id is None:
        project_id = config.current_project
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    try:
        client = CrucibleClient()
        samples = client.samples.list(project_id=project_id, limit=args.limit)

        logger.info(f"\n=== Samples in project {project_id} ===")
        logger.info(f"Found {len(samples)} sample(s)\n")

        if samples:
            for sample in samples:
                logger.info(f"ID: {sample.get('unique_id', 'N/A')}")
                if sample.get('sample_name'):
                    logger.info(f"  Name: {sample['sample_name']}")
                if sample.get('creation_time'):
                    logger.info(f"  Created: {sample['creation_time']}")
                logger.info("")

    except Exception as e:
        logger.error(f"Error listing samples: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'sample get' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        sample = client.samples.get(args.sample_id)

        if sample is None:
            logger.error(f"Sample not found: {args.sample_id}")
            sys.exit(1)

        logger.info("\n=== Sample Information ===")
        logger.info(f"ID: {sample.get('unique_id', 'N/A')}")
        if sample.get('sample_name'):
            logger.info(f"Name: {sample['sample_name']}")
        if sample.get('project_id'):
            logger.info(f"Project: {sample['project_id']}")
        if sample.get('creation_time'):
            logger.info(f"Created: {sample['creation_time']}")
        if sample.get('description'):
            logger.info(f"Description: {sample['description']}")

    except Exception as e:
        logger.error(f"Error retrieving sample: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'sample create' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    # Get project_id
    project_id = args.project_id
    if project_id is None:
        project_id = config.current_project
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    try:
        client = CrucibleClient()
        result = client.samples.create(
            sample_name=args.name,
            project_id=project_id,
            description=args.description
        )

        logger.info(f"✓ Sample created successfully!")
        logger.info(f"Sample ID: {result.get('unique_id', 'N/A')}")
        logger.info(f"Name: {result.get('sample_name', 'N/A')}")

        if args.verbose:
            logger.debug(f"\nFull result: {json.dumps(result, indent=2)}")

    except Exception as e:
        logger.error(f"Error creating sample: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_link(args):
    """Execute the 'sample link' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        result = client.samples.link(args.parent, args.child)

        logger.info(f"✓ Linked sample {args.child} as child of {args.parent}")
        if args.verbose:
            logger.debug(f"Result: {result}")

    except Exception as e:
        logger.error(f"Error linking samples: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_link_dataset(args):
    """Execute the 'sample link-dataset' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        result = client.samples.add_to_dataset(args.sample, args.dataset)

        logger.info(f"✓ Linked dataset {args.dataset} to sample {args.sample}")
        if args.verbose:
            logger.debug(f"Result: {result}")

    except Exception as e:
        logger.error(f"Error linking dataset to sample: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
