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
    # Interactive mode (prompts for input)
    crucible project create

    # Command-line mode (all arguments provided)
    crucible project create --project-id my-project -o "LBNL" -e "lead@lbl.gov"
    crucible project create --project-id alphafold-exp -o "Argonne" -e "researcher@anl.gov"
"""
    )

    parser.add_argument(
        '--project-id', '-id',
        required=False,
        default=None,
        metavar='ID',
        help='Unique project identifier (e.g., "my-project"). If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '-o', '--organization',
        required=False,
        default=None,
        metavar='ORG',
        help='Organization name (e.g., "LBNL", "Argonne", "Molecular Foundry"). If not provided, will prompt interactively.'
    )

    parser.add_argument(
        '-e', '--email',
        required=False,
        default=None,
        metavar='EMAIL',
        dest='project_lead_email',
        help='Project lead email address. If not provided, will prompt interactively.'
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
                if project.get('organization'):
                    logger.info(f"  Organization: {project['organization']}")
                if project.get('title'):
                    logger.info(f"  Title: {project['title']}")
                if project.get('project_lead_email'):
                    logger.info(f"  Lead: {project['project_lead_email']}")
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
        if project.get('organization'):
            logger.info(f"Organization: {project['organization']}")
        if project.get('title'):
            logger.info(f"Title: {project['title']}")
        if project.get('project_lead_email'):
            logger.info(f"Lead Email: {project['project_lead_email']}")
        if project.get('project_lead_name'):
            logger.info(f"Lead Name: {project['project_lead_name']}")
        if project.get('status'):
            logger.info(f"Status: {project['status']}")

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
    import re
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    # Interactive mode if any required arguments are missing
    project_id = args.project_id
    organization = args.organization
    project_lead_email = args.project_lead_email

    if project_id is None or organization is None or project_lead_email is None:
        logger.info("\n=== Interactive Project Creation ===")
        logger.info("Please provide the following information:\n")

    # Prompt for project_id
    if project_id is None:
        while True:
            project_id = input("Project ID (e.g., my-project): ").strip()
            if project_id:
                # Validate project_id format (alphanumeric, hyphens, underscores)
                if re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                    break
                else:
                    logger.error("Invalid project ID. Use only letters, numbers, hyphens, and underscores.")
            else:
                logger.error("Project ID is required.")

    # Prompt for organization
    if organization is None:
        while True:
            organization = input("Organization (e.g., LBNL, Argonne): ").strip()
            if organization:
                break
            else:
                logger.error("Organization is required.")

    # Prompt for project lead email
    if project_lead_email is None:
        while True:
            project_lead_email = input("Project lead email: ").strip()
            if project_lead_email:
                # Basic email validation
                if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', project_lead_email):
                    break
                else:
                    logger.error("Invalid email format.")
            else:
                logger.error("Project lead email is required.")

    try:
        logger.info("\n=== Creating Project ===")
        client = CrucibleClient()
        result = client.projects.get_or_create(
            project_id=project_id,
            organization=organization,
            project_lead_email=project_lead_email
        )

        logger.info(f"\n✓ Project created successfully!")
        logger.info(f"Project ID: {result.get('project_id', 'N/A')}")
        logger.info(f"Organization: {result.get('organization', 'N/A')}")
        logger.info(f"Lead Email: {result.get('project_lead_email', 'N/A')}")

        if args.verbose:
            logger.debug(f"\nFull result: {json.dumps(result, indent=2)}")

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
