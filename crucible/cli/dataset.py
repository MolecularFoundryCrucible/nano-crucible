#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset subcommand for Crucible CLI.

Provides dataset-related operations: list, get, create, update-metadata, link, etc.
"""

import sys
import json
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

try:
    import mfid
except ImportError:
    mfid = None

try:
    import argcomplete
    from argcomplete.completers import FilesCompleter
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

#internal modules
from ..constants import DEFAULT_LIMIT

#%%

def register_subcommand(subparsers):
    """
    Register the dataset subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    parser = subparsers.add_parser(
        'dataset',
        help='Dataset operations (list, get, create, etc.)',
        description='Manage Crucible datasets',
    )

    # Dataset subcommands
    dataset_subparsers = parser.add_subparsers(
        title='dataset commands',
        dest='dataset_command',
        help='Available dataset operations'
    )

    # Register individual dataset commands
    _register_list(dataset_subparsers)
    _register_get(dataset_subparsers)
    _register_create(dataset_subparsers)
    _register_update_metadata(dataset_subparsers)
    _register_link(dataset_subparsers)


def _register_list(subparsers):
    """Register the 'dataset list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List datasets',
        description='List datasets in a project'
    )

    parser.add_argument(
        '-pid', '--project-id',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses config current_project if not specified)'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=DEFAULT_LIMIT,
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
    """Register the 'dataset get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get dataset by ID',
        description='Retrieve dataset information'
    )

    parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )

    parser.add_argument(
        '--include-metadata',
        action='store_true',
        help='Include scientific metadata in output'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'dataset create' subcommand."""
    from crucible.parsers import PARSER_REGISTRY

    parser = subparsers.add_parser(
        'create',
        help='Create and upload a new dataset',
        description='Parse and upload dataset files to Crucible',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Preview what would be uploaded (dry run)
    crucible dataset create -i file1.dat -pid my-project --dry-run

    # Generic upload (server assigns mfid)
    crucible dataset create -i file1.dat file2.csv -pid my-project

    # Upload with locally generated mfid
    crucible dataset create -i data.csv -pid my-project --mfid

    # Upload with explicit mfid (e.g., re-uploading same dataset)
    crucible dataset create -i data.csv -pid my-project --mfid 0tcxz5xs5xr6q0002vmzmp3beg

    # Generic upload with metadata and keywords
    crucible dataset create -i data.csv -pid my-project \\
        --metadata '{"temperature": 300, "pressure": 1.0}' \\
        --keywords "experiment,thermal" -m "thermal_analysis"

    # Parse and upload LAMMPS simulation
    crucible dataset create -i input.lmp -t lammps -pid my-project
"""
    )

    # Input file(s)
    input_arg = parser.add_argument(
        '-i', '--input',
        nargs='+',
        required=True,
        metavar='FILE',
        help='Input file(s) to upload'
    )
    if ARGCOMPLETE_AVAILABLE:
        input_arg.completer = FilesCompleter()

    # Dataset type (optional - if not provided, uses generic upload)
    available_types = ', '.join(sorted(PARSER_REGISTRY.keys()))
    type_arg = parser.add_argument(
        '-t', '--type',
        required=False,
        default=None,
        dest='dataset_type',
        metavar='TYPE',
        help=f'Dataset type (optional). Available: {available_types}. If not specified, files are uploaded without parsing.'
    )
    if ARGCOMPLETE_AVAILABLE:
        type_arg.completer = lambda **kwargs: sorted(PARSER_REGISTRY.keys())

    # Project ID
    parser.add_argument(
        '-pid', '--project-id',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses config current_project if not specified)'
    )

    # Unique ID / mfid
    parser.add_argument(
        '--mfid', '--uuid', '--unique-id', '--id',
        dest='mfid',
        nargs='?',
        const=True,
        default=None,
        metavar='ID',
        help='Unique dataset ID (mfid). If omitted, server assigns ID. If flag provided without value, generates locally. If value provided, uses that ID.'
    )

    # Dataset name
    parser.add_argument(
        '-n', '--name',
        dest='dataset_name',
        default=None,
        metavar='NAME',
        help='Human-readable dataset name (optional)'
    )

    # Verbose output
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    # Measurement type
    parser.add_argument(
        '-m', '--measurement',
        dest='measurement',
        default=None,
        metavar='TYPE',
        help='Measurement type (optional)'
    )

    # Scientific metadata JSON
    parser.add_argument(
        '--metadata',
        dest='metadata',
        default=None,
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
    )

    # Keywords
    parser.add_argument(
        '-k', '--keywords',
        dest='keywords',
        default=None,
        metavar='WORDS',
        help='Comma-separated keywords'
    )

    # Session name
    parser.add_argument(
        '--session',
        dest='session_name',
        default=None,
        metavar='NAME',
        help='Session name for grouping related datasets'
    )

    # Public flag
    parser.add_argument(
        '--public',
        action='store_true',
        dest='public',
        help='Make dataset public (default: private)'
    )

    # Instrument name
    parser.add_argument(
        '--instrument',
        dest='instrument_name',
        default=None,
        metavar='NAME',
        help='Instrument name (optional)'
    )

    # Data format
    parser.add_argument(
        '--data-format',
        dest='data_format',
        default=None,
        metavar='FORMAT',
        help='Data format type (optional)'
    )

    # Dry run flag
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Show what would be uploaded without actually uploading'
    )

    parser.set_defaults(func=_execute_create)


def _register_update_metadata(subparsers):
    """Register the 'dataset update-metadata' subcommand."""
    parser = subparsers.add_parser(
        'update-metadata',
        help='Update scientific metadata',
        description='Update scientific metadata for a dataset'
    )

    parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )

    parser.add_argument(
        '--metadata',
        required=True,
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_update_metadata)


def _register_link(subparsers):
    """Register the 'dataset link' subcommand."""
    parser = subparsers.add_parser(
        'link',
        help='Link parent and child datasets',
        description='Create a parent-child relationship between datasets'
    )

    parser.add_argument(
        '-p', '--parent',
        required=True,
        metavar='PARENT_ID',
        help='Parent dataset ID'
    )

    parser.add_argument(
        '-c', '--child',
        required=True,
        metavar='CHILD_ID',
        help='Child dataset ID'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_link)


def _execute_list(args):
    """Execute the 'dataset list' subcommand."""
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
        datasets = client.datasets.list(project_id=project_id, limit=args.limit)

        logger.info(f"\n=== Datasets in project {project_id} ===")
        logger.info(f"Found {len(datasets)} dataset(s)\n")

        if datasets:
            for ds in datasets:
                logger.info(f"ID: {ds.get('unique_id', 'N/A')}")
                if ds.get('dataset_name'):
                    logger.info(f"  Name: {ds['dataset_name']}")
                if ds.get('measurement'):
                    logger.info(f"  Measurement: {ds['measurement']}")
                if ds.get('creation_time'):
                    logger.info(f"  Created: {ds['creation_time']}")
                logger.info("")

    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'dataset get' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        dataset = client.datasets.get(args.dataset_id, include_metadata=args.include_metadata)

        if dataset is None:
            logger.error(f"Dataset not found: {args.dataset_id}")
            sys.exit(1)

        logger.info("\n=== Dataset Information ===")
        logger.info(f"ID: {dataset.get('unique_id', 'N/A')}")
        if dataset.get('dataset_name'):
            logger.info(f"Name: {dataset['dataset_name']}")
        if dataset.get('measurement'):
            logger.info(f"Measurement: {dataset['measurement']}")
        if dataset.get('project_id'):
            logger.info(f"Project: {dataset['project_id']}")
        if dataset.get('creation_time'):
            logger.info(f"Created: {dataset['creation_time']}")
        if dataset.get('public') is not None:
            logger.info(f"Public: {'Yes' if dataset['public'] else 'No'}")

        if args.include_metadata and dataset.get('scientific_metadata'):
            logger.info("\n=== Scientific Metadata ===")
            metadata = dataset['scientific_metadata']
            logger.info(json.dumps(metadata, indent=2))

    except Exception as e:
        logger.error(f"Error retrieving dataset: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'dataset create' subcommand."""
    from crucible.parsers import get_parser, BaseParser
    from crucible.config import config
    from crucible.cli import setup_logging

    # Set up logging
    setup_logging(verbose=args.verbose)

    # Get project_id
    project_id = args.project_id
    project_from_config = False
    if project_id is None:
        project_id = config.current_project
        project_from_config = True
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    # Validate input files
    input_files = [Path(f) for f in args.input]
    for input_file in input_files:
        if not input_file.exists():
            logger.error(f"Error: Input file not found: {input_file}")
            sys.exit(1)

    # Parse metadata
    metadata_dict = None
    if args.metadata:
        metadata_input = args.metadata
        if Path(metadata_input).exists():
            try:
                with open(metadata_input, 'r') as f:
                    metadata_dict = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON in file {metadata_input}: {e}")
                sys.exit(1)
        else:
            try:
                metadata_dict = json.loads(metadata_input)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON in --metadata: {e}")
                sys.exit(1)

    # Parse keywords
    keywords_list = None
    if args.keywords:
        keywords_list = [k.strip() for k in args.keywords.split(',')]

    # Handle mfid: None (server assigns), True (generate locally), or explicit value
    dataset_mfid = args.mfid
    if dataset_mfid is True:
        # --mfid flag present without value, generate locally
        if mfid is None:
            logger.error("Error: mfid package not installed. Install with 'pip install mfid' or provide explicit --mfid <value>")
            sys.exit(1)
        dataset_mfid = mfid.mfid()[0]
        logger.debug(f"Generated local mfid: {dataset_mfid}")
    elif dataset_mfid is not None:
        # Explicit mfid value provided
        logger.debug(f"Using provided mfid: {dataset_mfid}")
    else:
        # None - let server assign mfid
        logger.debug("No mfid provided, server will assign one")

    # Determine parser class
    if args.dataset_type is None:
        ParserClass = BaseParser
    else:
        try:
            ParserClass = get_parser(args.dataset_type)
        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

    # Initialize parser
    try:
        parser = ParserClass(
            files_to_upload=[str(f) for f in input_files],
            project_id=project_id,
            metadata=metadata_dict,
            keywords=keywords_list,
            mfid=dataset_mfid,
            measurement=args.measurement,
            dataset_name=args.dataset_name,
            session_name=args.session_name,
            public=args.public,
            instrument_name=args.instrument_name,
            data_format=args.data_format
        )
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Display dataset information
    logger.info("\n=== Dataset Information ===")
    if project_from_config:
        logger.info(f"Project: {project_id} (from config)")
    else:
        logger.info(f"Project: {project_id}")
    logger.info(f"Parser: {ParserClass.__name__}")
    if parser.dataset_name:
        logger.info(f"Name: {parser.dataset_name}")
    logger.info(f"Measurement: {parser.measurement}")
    if parser.data_format:
        logger.info(f"Data format: {parser.data_format}")
    if parser.session_name:
        logger.info(f"Session: {parser.session_name}")
    logger.info(f"Public: {'Yes' if parser.public else 'No'}")
    if parser.instrument_name:
        logger.info(f"Instrument: {parser.instrument_name}")

    # Display mfid info
    if dataset_mfid is None:
        logger.info(f"MFID: Will be assigned by server")
    else:
        logger.info(f"MFID: {dataset_mfid}")

    logger.info(f"\nFiles to upload ({len(parser.files_to_upload)}):")
    for f in parser.files_to_upload:
        logger.info(f"  - {Path(f).name}")

    if parser.keywords:
        logger.info(f"\nKeywords ({len(parser.keywords)}): {', '.join(parser.keywords)}")

    if parser.scientific_metadata:
        logger.info(f"\nScientific Metadata ({len(parser.scientific_metadata)} fields):")
        for key, value in parser.scientific_metadata.items():
            if key == 'dump_files':
                logger.info(f"  {key}: {len(value)} files")
            elif isinstance(value, (list, dict)) and len(str(value)) > 80:
                logger.info(f"  {key}: <{type(value).__name__} with {len(value)} items>")
            else:
                logger.info(f"  {key}: {value}")

    # Upload or dry run
    if args.dry_run:
        logger.info("\n=== Dry Run (not uploading) ===")
        if dataset_mfid is None:
            logger.info("MFID would be assigned by server upon upload")
        elif args.mfid is True:
            logger.info(f"Would use locally generated mfid: {dataset_mfid}")
        else:
            logger.info(f"Would use provided mfid: {dataset_mfid}")
        logger.info("\nTo upload this dataset, run the command again without --dry-run")
    else:
        logger.info("\n=== Uploading to Crucible ===")
        if dataset_mfid is None:
            logger.info("Server will assign mfid")
        elif args.mfid is True:
            logger.info(f"Using locally generated mfid: {dataset_mfid}")
        else:
            logger.info(f"Using provided mfid: {dataset_mfid}")

        try:
            result = parser.upload_dataset(
                verbose=args.verbose,
                wait_for_ingestion_response=True
            )

            logger.info("\n✓ Upload successful!")
            logger.info(f"Dataset ID: {result.get('created_record', {}).get('unique_id', 'N/A')}")

            if result and args.verbose:
                logger.debug("\nUpload result details:")
                for key, value in result.items():
                    logger.debug(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"\n✗ Upload failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    logger.info("\nDone!")


def _execute_update_metadata(args):
    """Execute the 'dataset update-metadata' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    # Parse metadata
    metadata_input = args.metadata
    if Path(metadata_input).exists():
        try:
            with open(metadata_input, 'r') as f:
                metadata_dict = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error: Invalid JSON in file {metadata_input}: {e}")
            sys.exit(1)
    else:
        try:
            metadata_dict = json.loads(metadata_input)
        except json.JSONDecodeError as e:
            logger.error(f"Error: Invalid JSON in --metadata: {e}")
            sys.exit(1)

    try:
        client = CrucibleClient()
        result = client.datasets.update_scientific_metadata(args.dataset_id, metadata_dict)

        logger.info(f"✓ Metadata updated for dataset {args.dataset_id}")
        if args.verbose:
            logger.debug(f"Result: {result}")

    except Exception as e:
        logger.error(f"Error updating metadata: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_link(args):
    """Execute the 'dataset link' subcommand."""
    from crucible.client import CrucibleClient
    from crucible.cli import setup_logging

    setup_logging(verbose=args.verbose)

    try:
        client = CrucibleClient()
        result = client.datasets.link_parent_child(args.parent, args.child)

        logger.info(f"✓ Linked dataset {args.child} as child of {args.parent}")
        if args.verbose:
            logger.debug(f"Result: {result}")

    except Exception as e:
        logger.error(f"Error linking datasets: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
