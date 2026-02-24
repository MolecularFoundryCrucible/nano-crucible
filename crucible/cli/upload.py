#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload subcommand for Crucible CLI.

Handles parsing and uploading datasets to Crucible.
"""

import sys
import logging
from pathlib import Path

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


def register_subcommand(subparsers):
    """
    Register the upload subcommand with the main parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    from crucible.parsers import PARSER_REGISTRY

    parser = subparsers.add_parser(
        'upload',
        help='[Legacy] Parse and upload datasets (use "dataset create" instead)',
        description='Parse dataset files and upload them to Crucible\n\nNOTE: This command is kept for backward compatibility. Use "crucible dataset create" instead.',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Generic upload (no parsing) - upload any files
    crucible upload -i file1.dat file2.csv -pid my-project -u

    # Generic upload with metadata and keywords
    crucible upload -i data.csv -pid my-project -u \\
        --metadata '{"temperature": 300, "pressure": 1.0}' \\
        --keywords "experiment,thermal" -m "thermal_analysis"

    # Generic upload with metadata from JSON file
    crucible upload -i data.csv -pid my-project -u --metadata metadata.json

    # Parse and upload LAMMPS simulation
    crucible upload -i input.lmp -t lammps -pid my-project -u

    # Parse LAMMPS and add extra metadata/keywords
    crucible upload -i input.lmp -t lammps -pid my-project -u \\
        --metadata '{"experiment_id": "EXP-001"}' \\
        --keywords "validation,benchmark"

    # Upload with specific mfid (all aliases work: --mfid, --uuid, --unique-id, --id)
    crucible upload -i input.lmp -t lammps -pid my-project -u --mfid abc123xyz

    # Upload with custom dataset name
    crucible upload -i input.lmp -t lammps -pid my-project -u -n "Water MD Simulation"

    # Upload with session name and make public
    crucible upload -i input.lmp -t lammps -pid my-project -u \\
        --session "2024-Q1-experiments" --public
"""
    )

    # Input file(s)
    input_arg = parser.add_argument(
        '-i', '--input',
        nargs='+',
        required=True,
        metavar='FILE',
        help='Input file(s) to parse'
    )
    # Add file completion for input files
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
        help=f'Dataset type (case-insensitive, optional). Available: {available_types}. If not specified, files are uploaded without parsing.'
    )
    # Add choices completion for dataset types
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

    # Upload flag
    parser.add_argument(
        '-u', '--upload',
        action='store_true',
        help='Upload to Crucible (default: parse only)'
    )

    # Unique ID / mfid (with multiple aliases)
    parser.add_argument(
        '--mfid', '--uuid', '--unique-id', '--id',
        dest='mfid',
        default=None,
        metavar='ID',
        help='Unique dataset ID (mfid). Auto-generated if not provided.'
    )

    # Dataset name (optional)
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
        help='Measurement type (optional, primarily for generic uploads)'
    )

    # Scientific metadata JSON
    parser.add_argument(
        '--metadata',
        dest='metadata',
        default=None,
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file (merges with parser-extracted metadata)'
    )

    # Keywords
    parser.add_argument(
        '-k', '--keywords',
        dest='keywords',
        default=None,
        metavar='WORDS',
        help='Comma-separated keywords (merges with parser-extracted keywords)'
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
        help='Instrument name (optional, parser-specific)'
    )

    # Data format
    parser.add_argument(
        '--data-format',
        dest='data_format',
        default=None,
        metavar='FORMAT',
        help='Data format type (optional, parser-specific)'
    )

    # Set the function to execute for this subcommand
    parser.set_defaults(func=execute)


def execute(args):
    """
    Execute the upload subcommand.

    Args:
        args: Parsed command-line arguments from argparse
    """
    import json
    from crucible.parsers import get_parser, BaseParser
    from crucible.config import config
    from crucible.cli import setup_logging

    # Set up logging based on verbose flag
    setup_logging(verbose=args.verbose)

    # Get project_id - use flag if provided, otherwise fall back to config
    project_id = args.project_id
    project_from_config = False
    if project_id is None:
        project_id = config.current_project
        project_from_config = True
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            logger.error("  Set default: crucible config set current_project YOUR_PROJECT_ID")
            sys.exit(1)

    # Validate input files exist
    input_files = [Path(f) for f in args.input]
    for input_file in input_files:
        if not input_file.exists():
            logger.error(f"Error: Input file not found: {input_file}")
            sys.exit(1)

    # Parse metadata early (before mode announcement) - support JSON string or file
    metadata_dict = None
    if args.metadata:
        metadata_input = args.metadata
        # Check if it's a file path
        if Path(metadata_input).exists():
            try:
                with open(metadata_input, 'r') as f:
                    metadata_dict = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON in file {metadata_input}: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error reading metadata file {metadata_input}: {e}")
                sys.exit(1)
        else:
            # It's a JSON string
            try:
                metadata_dict = json.loads(metadata_input)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON in --metadata: {e}")
                sys.exit(1)
    else:
        metadata_dict = None

    # Parse keywords early
    keywords_list = None
    if args.keywords:
        keywords_list = [k.strip() for k in args.keywords.split(',')]

    # Generate mfid if not provided
    dataset_mfid = args.mfid
    if dataset_mfid is None and args.upload:
        if mfid is None:
            logger.error("Error: mfid package not installed. Install with 'pip install mfid' or provide --mfid")
            sys.exit(1)
        dataset_mfid = mfid.mfid()[0]
        logger.debug(f"Generated mfid: {dataset_mfid}")

    # Determine parser class
    if args.dataset_type is None:
        # No dataset type specified - use BaseParser
        ParserClass = BaseParser
    else:
        # Get specific parser for dataset type
        try:
            ParserClass = get_parser(args.dataset_type)
        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

    # Parser will use its default measurement if not provided
    measurement_type = args.measurement

    # Initialize parser with all dataset properties
    # Specific parsers will augment metadata/keywords with extracted data
    try:
        parser = ParserClass(
            files_to_upload=[str(f) for f in input_files],
            project_id=project_id,
            metadata=metadata_dict,
            keywords=keywords_list,
            mfid=dataset_mfid,
            measurement=measurement_type,
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

    # Display dataset information (always shown)
    logger.info("\n=== Dataset Information ===")

    # Project and Parser
    if project_from_config:
        logger.info(f"Project: {project_id} (from config)")
    else:
        logger.info(f"Project: {project_id}")
    logger.info(f"Parser: {ParserClass.__name__}")

    # Dataset properties
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

    # Files
    logger.info(f"\nFiles to upload ({len(parser.files_to_upload)}):")
    for f in parser.files_to_upload:
        logger.info(f"  - {Path(f).name}")

    # Keywords
    if parser.keywords:
        logger.info(f"\nKeywords ({len(parser.keywords)}): {', '.join(parser.keywords)}")

    # Metadata
    if parser.scientific_metadata:
        logger.info(f"\nScientific Metadata ({len(parser.scientific_metadata)} fields):")
        for key, value in parser.scientific_metadata.items():
            if key == 'dump_files':
                logger.info(f"  {key}: {len(value)} files")
            elif isinstance(value, (list, dict)) and len(str(value)) > 80:
                logger.info(f"  {key}: <{type(value).__name__} with {len(value)} items>")
            else:
                logger.info(f"  {key}: {value}")

    # Upload if requested
    if args.upload:
        logger.info("\n=== Uploading to Crucible ===")

        if args.mfid:
            logger.info(f"Using provided mfid: {dataset_mfid}")

        try:
            # Upload - only pass behavioral flags
            result = parser.upload_dataset(
                verbose=args.verbose,
                wait_for_ingestion_response=True
            )

            logger.info("\n✓ Upload successful!")
            logger.info(f"Dataset ID: {result.get('created_record', {}).get('unique_id', 'N/A')}")

            if result:
                logger.debug("\nUpload result details:")
                for key, value in result.items():
                    logger.debug(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"\n✗ Upload failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        logger.info("\n(Use -u/--upload flag to upload to Crucible)")

    logger.info("\nDone!")
