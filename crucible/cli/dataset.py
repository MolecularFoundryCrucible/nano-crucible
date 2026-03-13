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
    _register_update(dataset_subparsers)
    _register_update_metadata(dataset_subparsers)
    _register_link(dataset_subparsers)
    _register_list_parents(dataset_subparsers)
    _register_list_children(dataset_subparsers)
    _register_download(dataset_subparsers)
    _register_search(dataset_subparsers)
    _register_parsers(dataset_subparsers)
    _register_ingestors(dataset_subparsers)


def _register_list(subparsers):
    """Register the 'dataset list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List datasets',
        description='List datasets, with optional filters',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset list -pid my-project
    crucible dataset list -pid my-project -m XRD
    crucible dataset list -pid my-project -k silicon --limit 20
    crucible dataset list --session 2024-01-15-run
"""
    )

    parser.add_argument(
        '-pid', '--project-id',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses config current_project if not specified)'
    )

    parser.add_argument(
        '-m', '--measurement',
        default=None,
        metavar='TYPE',
        help='Filter by measurement type (exact match)'
    )

    parser.add_argument(
        '-k', '--keyword',
        default=None,
        metavar='WORD',
        help='Filter by keyword (case-insensitive substring match)'
    )

    parser.add_argument(
        '--session',
        default=None,
        metavar='NAME',
        help='Filter by session name (exact match)'
    )

    parser.add_argument(
        '--data-format',
        default=None,
        dest='data_format',
        metavar='FORMAT',
        help='Filter by data format (exact match)'
    )

    parser.add_argument(
        '--instrument',
        default=None,
        dest='instrument_name',
        metavar='NAME',
        help='Filter by instrument name (exact match)'
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

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )
    # Disable file completion for dataset_id
    if ARGCOMPLETE_AVAILABLE:
        dataset_id_arg.completer = argcomplete.completers.SuppressCompleter()

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

    # Upload multiple files using wildcards
    crucible dataset create -i *.dat -pid my-project -m "raw_data"

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
        help='Input file(s) to upload (supports wildcards like *.dat)'
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

    # Ingestor
    from crucible.constants import AVAILABLE_INGESTORS
    ingestor_arg = parser.add_argument(
        '--ingestor',
        dest='ingestor',
        default='ApiUploadIngestor',
        metavar='CLASS',
        help='Server-side ingestor class to use (default: ApiUploadIngestor). '
             'Run "crucible dataset ingestors" to see all available options.'
    )
    if ARGCOMPLETE_AVAILABLE:
        ingestor_arg.completer = lambda **kwargs: AVAILABLE_INGESTORS

    # Dry run flag
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Show what would be uploaded without actually uploading'
    )

    parser.set_defaults(func=_execute_create)


def _dataset_updatable_fields():
    """Return sorted list of fields that can be updated on a dataset (derived from BaseDataset model)."""
    from ..models import BaseDataset
    # Exclude server-managed / identifier fields
    _readonly = {'unique_id', 'owner_user_id', 'size', 'sha256_hash_file_to_upload'}
    return sorted(set(BaseDataset.model_fields.keys()) - _readonly)


def _register_update(subparsers):
    """Register the 'dataset update' subcommand."""
    fields = _dataset_updatable_fields()
    parser = subparsers.add_parser(
        'update',
        help='Update dataset fields',
        description='Update fields of an existing dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog=f"""
Updatable fields:
    {', '.join(fields)}

Examples:
    crucible dataset update DSID --set dataset_name="My Dataset"
    crucible dataset update DSID --set public=true
    crucible dataset update DSID --set measurement=XRD --set session_name=run-01
"""
    )

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        dataset_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--set', '-s',
        action='append',
        dest='set_fields',
        metavar='KEY=VALUE',
        required=True,
        help='Set a dataset field (repeatable). Values are auto-cast to int, float, bool, or string.'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'dataset update' subcommand."""
    from crucible.client import CrucibleClient
    valid_fields = set(_dataset_updatable_fields())
    updates = {}
    for field in args.set_fields:
        if '=' not in field:
            logger.error(f"Error: --set requires KEY=VALUE format, got: '{field}'")
            sys.exit(1)
        key, _, value = field.partition('=')
        key = key.strip()
        if key not in valid_fields:
            logger.error(
                f"Unknown field '{key}'.\n"
                f"Valid fields: {', '.join(sorted(valid_fields))}"
            )
            sys.exit(1)
        updates[key] = _cast_value(value)

    try:
        client = CrucibleClient()
        result = client.datasets.update(args.dataset_id, **updates)

        logger.info(f"✓ Dataset {args.dataset_id} updated")
        if args.verbose:
            logger.debug(f"Updated fields: {list(updates.keys())}")
            logger.debug(f"Result: {result}")

    except Exception as e:
        logger.error(f"Error updating dataset: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_update_metadata(subparsers):
    """Register the 'dataset update-metadata' subcommand."""
    parser = subparsers.add_parser(
        'update-metadata',
        help='Update scientific metadata',
        description='Update scientific metadata for a dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Key=value pairs (auto-cast to int/float/bool/str)
    crucible dataset update-metadata DSID --set temperature=300 --set pressure=1.0

    # Inline JSON string
    crucible dataset update-metadata DSID --metadata '{"temperature": 300}'

    # From a JSON file
    crucible dataset update-metadata DSID --metadata metadata.json

    # Mix: load base from file, override one field
    crucible dataset update-metadata DSID --metadata base.json --set temperature=300

    # Full replace instead of merge
    crucible dataset update-metadata DSID --set temperature=300 --overwrite
"""
    )

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        dataset_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--metadata',
        default=None,
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
    )

    parser.add_argument(
        '--set', '-s',
        action='append',
        dest='set_fields',
        metavar='KEY=VALUE',
        help='Set a single metadata field (repeatable). Values are auto-cast to int, float, bool, or string.'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Replace all existing metadata instead of merging'
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


def _register_list_parents(subparsers):
    """Register the 'dataset list-parents' subcommand."""
    parser = subparsers.add_parser(
        'list-parents',
        help='List parent datasets',
        description='List parent datasets of a given dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-parents DATASET_ID
    crucible dataset list-parents DATASET_ID --limit 20
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT, metavar='N',
                        help=f'Maximum number of results (default: {DEFAULT_LIMIT})')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_parents)


def _register_list_children(subparsers):
    """Register the 'dataset list-children' subcommand."""
    parser = subparsers.add_parser(
        'list-children',
        help='List child datasets',
        description='List child datasets derived from a given dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-children DATASET_ID
    crucible dataset list-children DATASET_ID --limit 20
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT, metavar='N',
                        help=f'Maximum number of results (default: {DEFAULT_LIMIT})')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_children)


def _register_download(subparsers):
    """Register the 'dataset download' subcommand."""
    parser = subparsers.add_parser(
        'download',
        help='Download dataset files',
        description='Download files from a Crucible dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Download all files into ./crucible-downloads/<dataset_id>/
    crucible dataset download DATASET_ID

    # Download to a specific directory
    crucible dataset download DATASET_ID -o my_data/

    # Download a single file
    crucible dataset download DATASET_ID -f results.csv

    # Force re-download of files that already exist locally
    crucible dataset download DATASET_ID --overwrite
"""
    )

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        dataset_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '-o', '--output-dir',
        dest='output_dir',
        default=None,
        metavar='DIR',
        help='Directory to save downloaded files (default: crucible-downloads/DATASET_ID/)'
    )

    parser.add_argument(
        '-f', '--file',
        dest='file_name',
        default=None,
        metavar='FILE',
        help='Download a specific file only (supports regex)'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        dest='overwrite',
        help='Re-download and overwrite files that already exist locally'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_download)


def _execute_download(args):
    """Execute the 'dataset download' subcommand."""
    from crucible.client import CrucibleClient
    output_dir = args.output_dir or f"crucible-downloads/{args.dataset_id}"

    try:
        client = CrucibleClient()
        logger.info(f"Downloading dataset {args.dataset_id} to {output_dir}/")

        downloaded = client.datasets.download(
            args.dataset_id,
            file_name=args.file_name,
            output_dir=output_dir,
            overwrite_existing=args.overwrite
        )

        if not downloaded:
            if args.file_name:
                logger.info(f"No files matched '{args.file_name}'")
            else:
                logger.info("No files to download (all already exist or dataset is empty)")
        else:
            logger.info(f"✓ Downloaded {len(downloaded)} file(s):")
            for path in downloaded:
                logger.info(f"  {path}")

    except Exception as e:
        logger.error(f"Error downloading dataset: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_search(subparsers):
    """Register the 'dataset search' subcommand."""
    parser = subparsers.add_parser(
        'search',
        help='Search datasets by scientific metadata',
        description='Full-text search across scientific metadata of all datasets',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset search "thermal conductivity"
    crucible dataset search "silicon XRD 300K"
    crucible dataset search temperature -v
"""
    )

    parser.add_argument(
        'query',
        metavar='QUERY',
        help='Search query string'
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
        help='Verbose output (show full metadata for each result)'
    )

    parser.set_defaults(func=_execute_search)


def _execute_search(args):
    """Execute the 'dataset search' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        results = client.datasets.search_scientific_metadata(args.query)

        if args.limit:
            results = results[:args.limit]

        logger.info(f"\n=== Search results for '{args.query}' ===")
        logger.info(f"Found {len(results)} result(s)\n")

        for i, r in enumerate(results, 1):
            mfid = r.get('dataset_mfid', 'N/A')
            logger.info(f"{i}. {mfid}")
            if args.verbose:
                scimd = r.get('scientific_metadata', {})
                for key, value in scimd.items():
                    if isinstance(value, dict):
                        logger.info(f"   {key}: <dict with {len(value)} keys>")
                    elif isinstance(value, list):
                        logger.info(f"   {key}: <list with {len(value)} items>")
                    else:
                        logger.info(f"   {key}: {value}")
            logger.info("")

    except Exception as e:
        logger.error(f"Error searching datasets: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_parsers(subparsers):
    """Register the 'dataset parsers' subcommand."""
    parser = subparsers.add_parser(
        'parsers',
        help='List available dataset parsers',
        description='Show all available dataset parsers, including those installed via third-party packages',
        epilog="""
Examples:
    crucible dataset parsers
    crucible dataset parsers -v
"""
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show additional parser details'
    )

    parser.set_defaults(func=_execute_parsers)


def _execute_list(args):
    """Execute the 'dataset list' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    # Get project_id
    project_id = args.project_id
    if project_id is None:
        project_id = config.current_project
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    # Build optional filters
    filters = {}
    if args.measurement:
        filters['measurement'] = args.measurement
    if args.keyword:
        filters['keyword'] = args.keyword
    if args.session:
        filters['session_name'] = args.session
    if args.data_format:
        filters['data_format'] = args.data_format
    if args.instrument_name:
        filters['instrument_name'] = args.instrument_name

    try:
        client = CrucibleClient()
        datasets = client.datasets.list(project_id=project_id, limit=args.limit, **filters)

        header = f"\n=== Datasets in project {project_id} ===" if project_id else "\n=== Datasets ==="
        logger.info(header)
        if filters:
            logger.info(f"Filters: {', '.join(f'{k}={v}' for k, v in filters.items())}")
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
    # Get project_id
    project_id = args.project_id
    project_from_config = False
    if project_id is None:
        project_id = config.current_project
        project_from_config = True
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    # Expand wildcards in input files
    import glob
    expanded_files = []
    for pattern in args.input:
        matches = glob.glob(pattern)
        if matches:
            expanded_files.extend(matches)
        else:
            # No matches, keep the original (will fail validation if it doesn't exist)
            expanded_files.append(pattern)

    # Validate input files
    input_files = [Path(f) for f in expanded_files]
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
        from crucible.parsers import get_all_parsers
        all_parsers = get_all_parsers()
        non_base = sorted(k for k in all_parsers if k != 'base')
        if non_base:
            logger.info(f"Tip: No parser type specified (-t). Using generic upload (BaseParser).")
            logger.info(f"     Available parsers: {', '.join(non_base)}")
            logger.info(f"     Run 'crucible dataset parsers' to see all options.\n")
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

    # If a custom ingestor is used and the user didn't explicitly set -m,
    # clear the parser's default measurement so the server assigns it
    if args.ingestor != 'ApiUploadIngestor' and args.measurement is None:
        parser.measurement = None

    # Display dataset information
    logger.info("\n=== Dataset Information ===")
    if project_from_config:
        logger.info(f"Project: {project_id} (from config)")
    else:
        logger.info(f"Project: {project_id}")
    logger.info(f"Parser: {ParserClass.__name__}")
    if parser.dataset_name:
        logger.info(f"Name: {parser.dataset_name}")
    if parser.measurement:
        logger.info(f"Measurement: {parser.measurement}")
    else:
        logger.info(f"Measurement: (assigned by server)")
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
        logger.info(f"Ingestor: {args.ingestor}")
        logger.info("\nTo upload this dataset, run the command again without --dry-run")
    else:
        logger.info("\n=== Uploading to Crucible ===")
        if dataset_mfid is None:
            logger.info("Server will assign mfid")
        elif args.mfid is True:
            logger.info(f"Using locally generated mfid: {dataset_mfid}")
        else:
            logger.info(f"Using provided mfid: {dataset_mfid}")
        logger.info(f"Ingestor: {args.ingestor}")

        try:
            result = parser.upload_dataset(
                ingestor=args.ingestor,
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


def _cast_value(value):
    """Auto-cast a string value to int, float, bool, or string."""
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _execute_update_metadata(args):
    """Execute the 'dataset update-metadata' subcommand."""
    from crucible.client import CrucibleClient
    if not args.metadata and not args.set_fields:
        logger.error("Error: provide at least one of --metadata or --set KEY=VALUE")
        sys.exit(1)

    metadata_dict = {}

    # Parse --metadata (JSON string or file)
    if args.metadata:
        metadata_path = Path(args.metadata)
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata_dict = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Invalid JSON in file {metadata_path}: {e}")
                sys.exit(1)
        else:
            try:
                metadata_dict = json.loads(args.metadata)
            except json.JSONDecodeError:
                logger.error(f"Error: '{args.metadata}' is not valid JSON and no such file exists.")
                sys.exit(1)

    # Parse --set KEY=VALUE pairs (override/extend --metadata)
    if args.set_fields:
        for field in args.set_fields:
            if '=' not in field:
                logger.error(f"Error: --set requires KEY=VALUE format, got: '{field}'")
                sys.exit(1)
            key, _, value = field.partition('=')
            metadata_dict[key.strip()] = _cast_value(value)

    try:
        client = CrucibleClient()
        result = client.datasets.update_scientific_metadata(
            args.dataset_id, metadata_dict, overwrite=args.overwrite
        )

        action = "replaced" if args.overwrite else "updated"
        logger.info(f"✓ Metadata {action} for dataset {args.dataset_id}")
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


def _execute_list_parents(args):
    """Execute the 'dataset list-parents' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        parents = client.datasets.list_parents(args.dataset_id, limit=args.limit)

        if not parents:
            logger.info("No parent datasets found.")
            return

        logger.info(f"\n=== Parent Datasets of {args.dataset_id} ({len(parents)}) ===\n")
        for ds in parents:
            uid = ds.get('unique_id', 'N/A')
            name = ds.get('dataset_name') or '(unnamed)'
            logger.info(f"  {uid}  {name}")
            if args.verbose:
                logger.debug(f"    measurement={ds.get('measurement')}  project={ds.get('project_id')}")

    except Exception as e:
        logger.error(f"Error listing parent datasets: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_children(args):
    """Execute the 'dataset list-children' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        children = client.datasets.list_children(args.dataset_id, limit=args.limit)

        if not children:
            logger.info("No child datasets found.")
            return

        logger.info(f"\n=== Child Datasets of {args.dataset_id} ({len(children)}) ===\n")
        for ds in children:
            uid = ds.get('unique_id', 'N/A')
            name = ds.get('dataset_name') or '(unnamed)'
            logger.info(f"  {uid}  {name}")
            if args.verbose:
                logger.debug(f"    measurement={ds.get('measurement')}  project={ds.get('project_id')}")

    except Exception as e:
        logger.error(f"Error listing child datasets: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_parsers(args):
    """Execute the 'dataset parsers' subcommand."""
    from crucible.parsers import PARSER_REGISTRY, get_all_parsers
    all_parsers = get_all_parsers()
    builtin_names = set(PARSER_REGISTRY.keys())

    logger.info(f"\n=== Available Dataset Parsers ===\n")

    for name, cls in sorted(all_parsers.items()):
        source = "built-in" if name in builtin_names else "installed"
        measurement = getattr(cls, '_measurement', 'N/A')
        data_format = getattr(cls, '_data_format', None)

        logger.info(f"  {name}  [{source}]")
        if args.verbose:
            logger.info(f"    Class:       {cls.__module__}.{cls.__name__}")
            logger.info(f"    Measurement: {measurement}")
            if data_format:
                logger.info(f"    Data format: {data_format}")
    
    logger.info("")
    logger.info(f"Use with: crucible dataset create -i FILE -t TYPE ...")
    logger.info(f"Additional parsers can be installed via third-party packages.")
    logger.info(f"  (registered under the 'crucible.parsers' entry-point group)")


def _register_ingestors(subparsers):
    """Register the 'dataset ingestors' subcommand."""
    parser = subparsers.add_parser(
        'ingestors',
        help='List available server-side ingestors',
        description='Show all known server-side ingestor classes',
        epilog="""
Examples:
    crucible dataset ingestors
    crucible dataset ingestors --filter scopefoundry

Use the ingestor name with:
    crucible dataset create -i FILE --ingestor INGESTOR_CLASS
"""
    )

    parser.add_argument(
        '--filter', '-f',
        dest='filter',
        default=None,
        metavar='TEXT',
        help='Filter ingestors by name (case-insensitive substring match)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_ingestors)


def _execute_ingestors(args):
    """Execute the 'dataset ingestors' subcommand."""
    from crucible.constants import AVAILABLE_INGESTORS
    ingestors = AVAILABLE_INGESTORS
    if args.filter:
        ingestors = [i for i in ingestors if args.filter.lower() in i.lower()]

    logger.info(f"\n=== Available Server-Side Ingestors ===\n")

    if not ingestors:
        logger.info(f"  No ingestors match filter: '{args.filter}'")
    else:
        for name in ingestors:
            logger.info(f"  {name}")

    logger.info(f"")
    logger.info(f"Use with: crucible dataset create -i FILE --ingestor INGESTOR_CLASS")
    logger.info(f"Default:  ApiUploadIngestor (generic upload, no server-side parsing)")
