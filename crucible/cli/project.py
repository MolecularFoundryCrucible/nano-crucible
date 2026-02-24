#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project subcommand for Crucible CLI.

Provides project-related operations: list, get, create.
"""

import sys
import logging
import json

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """
    Register the project subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'project',
        help='Project operations (list, get, create)',
        description='Manage Crucible projects',
    )

    # Project subcommands
    project_subparsers = parser.add_subparsers(
        title='project commands',
        dest='project_command',
        help='Available project operations'
    )

    # Register individual project commands
    _register_list(project_subparsers)
    _register_get(project_subparsers)
    _register_create(project_subparsers)


def _register_list(subparsers):
    """Register the 'project list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List projects',
        description='List all projects'
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
    """Register the 'project get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get project by ID',
        description='Retrieve project information'
    )

    parser.add_argument(
        'project_id',
        metavar='PROJECT_ID',
        help='Project ID'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'project create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new project',
        description='Create a new project in Crucible',
        epilog="""
Examples:
    crucible project create -n "My Project" -f "ALS"
    crucible project create -n "Q1 2024 Experiments" -f "Molecular Foundry"
"""
    )

    parser.add_argument(
        '-n', '--name',
        required=True,
        metavar='NAME',
        help='Project name'
    )

    parser.add_argument(
        '-f', '--facility',
        required=True,
        metavar='FACILITY',
        help='Facility name (e.g., "ALS", "Molecular Foundry")'
    )

    parser.add_argument(
        '--description',
        default=None,
        metavar='TEXT',
        help='Project description (optional)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_create)


def _execute_list(args):
    """Execute the 'project list' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        projects = client.projects.list(limit=args.limit)

        logger.info(f"\n=== Projects ===")
        logger.info(f"Found {len(projects)} project(s)\n")

        if projects:
            for project in projects:
                logger.info(f"ID: {project.get('project_id', 'N/A')}")
                if project.get('project_name'):
                    logger.info(f"  Name: {project['project_name']}")
                if project.get('facility'):
                    logger.info(f"  Facility: {project['facility']}")
                if project.get('creation_time'):
                    logger.info(f"  Created: {project['creation_time']}")
                logger.info("")

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'project get' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        project = client.projects.get(args.project_id)

        if project is None:
            logger.error(f"Project not found: {args.project_id}")
            sys.exit(1)

        logger.info("\n=== Project Information ===")
        logger.info(f"ID: {project.get('project_id', 'N/A')}")
        if project.get('project_name'):
            logger.info(f"Name: {project['project_name']}")
        if project.get('facility'):
            logger.info(f"Facility: {project['facility']}")
        if project.get('creation_time'):
            logger.info(f"Created: {project['creation_time']}")
        if project.get('description'):
            logger.info(f"Description: {project['description']}")

        if args.verbose:
            logger.debug(f"\nFull project data: {json.dumps(project, indent=2)}")

    except Exception as e:
        logger.error(f"Error retrieving project: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'project create' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        result = client.projects.create(
            project_name=args.name,
            facility=args.facility,
            description=args.description
        )

        logger.info(f"✓ Project created successfully!")
        logger.info(f"Project ID: {result.get('project_id', 'N/A')}")
        logger.info(f"Name: {result.get('project_name', 'N/A')}")
        logger.info(f"Facility: {result.get('facility', 'N/A')}")

        if args.verbose:
            logger.debug(f"\nFull result: {json.dumps(result, indent=2)}")

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
