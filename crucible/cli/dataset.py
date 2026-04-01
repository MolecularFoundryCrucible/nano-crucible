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

from . import term


def _normalize_file_paths(link_map, af_list, dsid):
    """Normalize paths from get_download_links and get_associated_files to bare filenames."""
    prefix_dl = dsid + '/'
    prefix_af = 'api-uploads/'
    links = {
        (k[len(prefix_dl):] if k.startswith(prefix_dl) else k): v
        for k, v in link_map.items()
    }
    meta_by_name = {}
    for m in af_list:
        fname = m.get('filename') or m.get('name', '')
        if fname.startswith(prefix_af):
            fname = fname[len(prefix_af):]
        meta_by_name[fname] = m
    return links, meta_by_name


def _show_scientific_metadata(sci_md_wrapper):
    """Display scientific metadata, unwrapping the API envelope."""
    if not sci_md_wrapper:
        return
    actual = sci_md_wrapper.get('scientific_metadata') if isinstance(sci_md_wrapper, dict) else sci_md_wrapper
    if not actual:
        term.subheader("Scientific Metadata")
        print("  (empty)")
        return
    term.subheader(f"Scientific Metadata ({len(actual)} fields)")
    max_key = max(len(k) for k in actual)
    for k, v in actual.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        elif isinstance(v, list) and len(v) > 8:
            print(f"  {k:<{max_key}}  <list with {len(v)} items>")
        else:
            print(f"  {k:<{max_key}}  {v}")


def _show_dataset(dataset, client, verbose=False, graph=False, include_metadata=False):
    """Display dataset fields. Extracted for reuse by top-level 'crucible get'."""
    _p = term.field_printer(14)

    try:
        from crucible.config import config
        _base = config.graph_explorer_url.rstrip('/')
    except Exception:
        _base = None

    def _ds_link(r):
        u, p = r.get('unique_id'), r.get('project_id')
        return term.mfid_link(u, f"{_base}/{p}/dataset/{u}" if _base and u and p else None)

    def _s_link(r):
        u, p = r.get('unique_id'), r.get('project_id')
        return term.mfid_link(u, f"{_base}/{p}/sample-graph/{u}" if _base and u and p else None)

    term.header("Dataset")

    _p("Name",        dataset.get('dataset_name') or '(unnamed)')
    _p("MFID",        _ds_link(dataset))
    _p("Measurement", dataset.get('measurement'))
    _p("Session",     dataset.get('session_name'))
    _p("Instrument",  dataset.get('instrument_name'))
    _p("Project",     dataset.get('project_id'))
    _p("Timestamp",   term.fmt_ts(dataset.get('timestamp')))
    _p("Description", dataset.get('description'))

    if verbose or graph:
        term.subheader("Ownership")
        pub = dataset.get('public')
        _p("Public",      "Yes" if pub else ("No" if pub is not None else None))
        _p("Owner ORCID", term.orcid_link(dataset.get('owner_orcid')))
        _p("Owner ID",    dataset.get('owner_user_id'))

        term.subheader("File")
        _p("Data Format",   dataset.get('data_format'))
        _p("Size",          term.fmt_size(dataset.get('size')))
        _p("Instrument ID", dataset.get('instrument_id'))
        _p("Source",        dataset.get('source_folder'))
        _p("SHA256",        dataset.get('sha256_hash_file_to_upload'))

        term.subheader("Timing")
        _p("Created",  term.fmt_ts(dataset.get('creation_time')))
        _p("Modified", term.fmt_ts(dataset.get('modification_time')))

        dsid = dataset.get('unique_id')

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_kw    = pool.submit(client.datasets.get_keywords, dsid)
            f_meta  = pool.submit(client.datasets.get_associated_files, dsid)
            f_links = pool.submit(client.datasets.get_download_links, dsid)
            keywords = f_kw.result()
            af_list  = f_meta.result()
            link_map = f_links.result()

        if keywords:
            words = [kw.get('keyword', kw) if isinstance(kw, dict) else kw for kw in keywords]
            term.subheader("Keywords")
            print(f"  {', '.join(words)}")

        links, meta_by_name = _normalize_file_paths(link_map, af_list, dsid)

        if meta_by_name:
            term.subheader(f"Files ({len(meta_by_name)})")
            for name in sorted(meta_by_name):
                url   = links.get(name)
                size  = meta_by_name[name].get('size')
                label = term.hyperlink(term.cyan(name), url) if url else name
                sz    = f"  {term.dim(term.fmt_size(size))}" if size is not None else ''
                print(f"  {label}{sz}")

    if include_metadata:
        _show_scientific_metadata(dataset.get('scientific_metadata'))

    if graph:
        samples = client.samples.list(dataset_id=dsid)
        term.subheader(f"Linked Samples ({len(samples)})")
        for s in samples:
            print(f"  {_s_link(s)}  {s.get('sample_name') or '(unnamed)'}")
        if not samples:
            print(f"  {term.dim('(none)')}")

        parents = client.datasets.list_parents(dsid)
        term.subheader(f"Parents ({len(parents)})")
        for p in parents:
            print(f"  {_ds_link(p)}  {p.get('dataset_name') or '(unnamed)'}")
        if not parents:
            print(f"  {term.dim('(none)')}")

        children = client.datasets.list_children(dsid)
        term.subheader(f"Children ({len(children)})")
        for c in children:
            print(f"  {_ds_link(c)}  {c.get('dataset_name') or '(unnamed)'}")
        if not children:
            print(f"  {term.dim('(none)')}")

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
from ..config import config as _config

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
    _register_delete(dataset_subparsers)
    _register_edit(dataset_subparsers)
    _register_link(dataset_subparsers)
    _register_add_sample(dataset_subparsers)
    _register_remove_sample(dataset_subparsers)
    _register_remove_child(dataset_subparsers)
    _register_list_parents(dataset_subparsers)
    _register_list_children(dataset_subparsers)
    _register_list_samples(dataset_subparsers)
    _register_download(dataset_subparsers)
    _register_add_file(dataset_subparsers)
    _register_list_files(dataset_subparsers)
    _register_search(dataset_subparsers)
    _register_add_keyword(dataset_subparsers)
    _register_list_keywords(dataset_subparsers)
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
    crucible dataset list -pid my-project --group-by measurement
    crucible dataset list -pid my-project --include "run-*" "*XRD*"
    crucible dataset list -pid my-project --exclude "*test*"
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
        '--group-by',
        dest='group_by',
        default=None,
        choices=['measurement', 'session', 'format', 'instrument'],
        metavar='FIELD',
        help='Group results by field: measurement, session, format, instrument (default from config, fallback: measurement)'
    )

    parser.add_argument(
        '--include',
        nargs='+',
        metavar='PATTERN',
        help='Only show datasets whose name matches any glob pattern (e.g. "run-*", "*XRD*")'
    )

    parser.add_argument(
        '--exclude',
        nargs='+',
        metavar='PATTERN',
        help='Exclude datasets whose name matches any glob pattern'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=_config.default_limit,
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
        help='Show all dataset fields'
    )

    parser.add_argument(
        '--graph',
        action='store_true',
        help='Also show linked samples, parents, and children'
    )

    parser.add_argument(
        '-o', '--output',
        dest='output',
        choices=['json'],
        default=None,
        metavar='FORMAT',
        help='Output format: json (always includes scientific metadata)'
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

    # Timestamp
    parser.add_argument(
        '--timestamp',
        dest='timestamp',
        default=None,
        metavar='DATE',
        help="User-defined timestamp (flexible: 'today', '2024-01-15', '2024-01-15 10:30', ISO 8601, etc.)"
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
    """Return ordered list of fields that can be updated on a dataset."""
    from .schema import DATASET_FIELDS, editable_keys
    return editable_keys(DATASET_FIELDS)


def _register_update(subparsers):
    """Register the 'dataset update' subcommand."""
    import argparse
    fields = _dataset_updatable_fields()

    def _add_args(p):
        did_arg = p.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
        if ARGCOMPLETE_AVAILABLE:
            did_arg.completer = argcomplete.completers.SuppressCompleter()
        p.add_argument('--set', '-s', action='append', dest='set_fields', metavar='KEY=VALUE',
                       help='Set a dataset field (repeatable). Values are auto-cast to int, float, bool, or string.')
        p.add_argument('--metadata', default=None, metavar='JSON',
                       help='Scientific metadata as JSON string or path to JSON file')
        p.add_argument('--overwrite', action='store_true',
                       help='Replace all existing scientific metadata instead of merging (only with --metadata)')
        p.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    parser = subparsers.add_parser(
        'update',
        help='Update dataset fields or scientific metadata',
        description='Update fields or scientific metadata of an existing dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Updatable fields (use --set):
    {', '.join(fields)}

Examples:
    crucible dataset update DSID --set dataset_name="My Dataset"
    crucible dataset update DSID --set public=true
    crucible dataset update DSID --set measurement=XRD --set session_name=run-01
    crucible dataset update DSID --metadata '{{"temperature": 300, "pressure": 1.0}}'
    crucible dataset update DSID --metadata metadata.json
    crucible dataset update DSID --set measurement=XRD --metadata '{{"temperature": 300}}'
"""
    )
    _add_args(parser)
    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'dataset update' subcommand."""
    from crucible.client import CrucibleClient

    has_set = bool(getattr(args, 'set_fields', None))
    has_metadata = bool(getattr(args, 'metadata', None))

    if not has_set and not has_metadata:
        logger.error("Error: provide at least one of --set KEY=VALUE or --metadata JSON")
        sys.exit(1)

    # Parse --set for model field updates
    updates = {}
    if has_set:
        valid_fields = set(_dataset_updatable_fields())
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

    # Parse --metadata for scientific metadata
    metadata_dict = None
    if has_metadata:
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

    try:
        client = CrucibleClient()

        if updates:
            client.datasets.update(args.dataset_id, **updates)
            logger.info(f"✓ Dataset {args.dataset_id} fields updated")
            if getattr(args, "debug", False):
                logger.debug(f"Updated fields: {list(updates.keys())}")

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.datasets.update_scientific_metadata(
                args.dataset_id, metadata_dict, overwrite=overwrite
            )
            action = "replaced" if overwrite else "updated"
            logger.info(f"✓ Scientific metadata {action} for dataset {args.dataset_id}")

    except Exception as e:
        logger.error(f"Error updating dataset: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_delete(subparsers):
    """Register the 'dataset delete' subcommand."""
    parser = subparsers.add_parser(
        'delete',
        help='Delete a dataset',
        description='Permanently delete a dataset (irreversible). Prompts for confirmation unless -y is given.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset delete DATASET_ID
    crucible dataset delete DATASET_ID -y
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID to delete')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')
    parser.set_defaults(func=_execute_delete)


def _execute_delete(args):
    """Execute the 'dataset delete' subcommand."""
    from crucible.client import CrucibleClient
    if not args.yes:
        confirm = input(f"Delete dataset {args.dataset_id}? This cannot be undone. [y/N] ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    try:
        client = CrucibleClient()
        client.datasets.delete(args.dataset_id)
        logger.info(f"✓ Deleted dataset {args.dataset_id}")
    except Exception as e:
        logger.error(f"Error deleting dataset: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_edit(subparsers):
    """Register the 'dataset edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit dataset fields interactively',
        description='Open dataset fields in $EDITOR and update on save. Scientific metadata is included as a top-level key.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset edit DATASET_ID
    EDITOR=vim crucible dataset edit DATASET_ID
"""
    )
    did_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_ID',
        help='Dataset unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        did_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_edit)


def _edit_dataset(dsid, client, debug=False):
    """Core edit logic for a dataset — shared with the top-level 'crucible edit' command."""
    dataset = client.datasets.get(dsid, include_metadata=True)
    if dataset is None:
        logger.error(f"Dataset not found: {dsid}")
        sys.exit(1)

    from .schema import DATASET_FIELDS, ordered_dict
    valid_fields = set(_dataset_updatable_fields())
    original_fields = ordered_dict(DATASET_FIELDS, dataset, verbose=True, editable_only=True)
    original_meta = dataset.get('scientific_metadata') or {}

    original = dict(original_fields)
    original['scientific_metadata'] = original_meta

    try:
        edited = term.open_editor_json(original)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    field_changes = {
        k: v for k, v in edited.items()
        if k in valid_fields and v != original_fields.get(k)
    }

    edited_meta = edited.get('scientific_metadata')
    meta_changed = isinstance(edited_meta, dict) and edited_meta != original_meta

    if not field_changes and not meta_changed:
        logger.info("No changes.")
        return

    try:
        if field_changes:
            client.datasets.update(dsid, **field_changes)
        if meta_changed:
            client.datasets.update_scientific_metadata(dsid, edited_meta, overwrite=True)

        diff_updated = dict(field_changes)
        if meta_changed:
            diff_updated['scientific_metadata'] = edited_meta
        term.header("Changes")
        term.diff(original, diff_updated)
    except Exception as e:
        logger.error(f"Error updating dataset: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_edit(args):
    """Execute the 'dataset edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        logger.error(f"Error connecting: {e}")
        sys.exit(1)
    _edit_dataset(args.dataset_id, client, debug=getattr(args, 'debug', False))


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


def _register_add_sample(subparsers):
    """Register the 'dataset add-sample' subcommand."""
    parser = subparsers.add_parser(
        'add-sample',
        help='Link a sample to a dataset',
        description='Associate a sample with a dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-sample DATASET_ID --sample SAMPLE_ID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('-s', '--sample', required=True, metavar='SAMPLE_ID', help='Sample ID')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_add_sample)


def _execute_add_sample(args):
    """Execute the 'dataset add-sample' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.add_sample(args.dataset_id, args.sample)

        logger.info(f"✓ Linked sample {args.sample} to dataset {args.dataset_id}")

    except Exception as e:
        logger.error(f"Error linking sample to dataset: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_remove_sample(subparsers):
    """Register the 'dataset remove-sample' subcommand."""
    parser = subparsers.add_parser(
        'remove-sample',
        help='Unlink a sample from a dataset',
        description='Remove the association between a dataset and a sample (requires admin)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset remove-sample DATASET_ID --sample SAMPLE_ID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('-s', '--sample', required=True, metavar='SAMPLE_ID', help='Sample ID to unlink')
    parser.set_defaults(func=_execute_remove_sample)


def _execute_remove_sample(args):
    """Execute the 'dataset remove-sample' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.remove_sample(args.dataset_id, args.sample)
        logger.info(f"✓ Unlinked sample {args.sample} from dataset {args.dataset_id}")
    except Exception as e:
        logger.error(f"Error unlinking sample from dataset: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_remove_child(subparsers):
    """Register the 'dataset remove-child' subcommand."""
    parser = subparsers.add_parser(
        'remove-child',
        help='Unlink a child dataset from a parent dataset',
        description='Remove the parent-child relationship between two datasets (requires admin)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset remove-child PARENT_ID --child CHILD_ID
"""
    )
    parser.add_argument('parent_id', metavar='PARENT_ID', help='Parent dataset unique ID')
    parser.add_argument('-c', '--child', required=True, metavar='CHILD_ID', help='Child dataset ID to unlink')
    parser.set_defaults(func=_execute_remove_child)


def _execute_remove_child(args):
    """Execute the 'dataset remove-child' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.remove_child(args.parent_id, args.child)
        logger.info(f"✓ Unlinked child dataset {args.child} from parent dataset {args.parent_id}")
    except Exception as e:
        logger.error(f"Error unlinking child dataset: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


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
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
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
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_children)


def _register_list_samples(subparsers):
    """Register the 'dataset list-samples' subcommand."""
    parser = subparsers.add_parser(
        'list-samples',
        help='List samples linked to a dataset',
        description='Show all samples associated with a given dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-samples DATASET_ID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_samples)


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

    # Only download CSV files
    crucible dataset download DATASET_ID --include "*.csv"

    # Download everything except raw files
    crucible dataset download DATASET_ID --exclude "*.raw"

    # Include multiple patterns
    crucible dataset download DATASET_ID --include "*.csv" --include "*.json"

    # Combine include and exclude
    crucible dataset download DATASET_ID --include "data/*" --exclude "*.tmp"

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
        '--include',
        action='append',
        metavar='PATTERN',
        help='Only download files matching this glob pattern (repeatable)'
    )

    parser.add_argument(
        '--exclude',
        action='append',
        metavar='PATTERN',
        help='Skip files matching this glob pattern (repeatable)'
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
            overwrite_existing=args.overwrite,
            include=args.include,
            exclude=args.exclude,
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
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_add_file(subparsers):
    """Register the 'dataset add-file' subcommand."""
    parser = subparsers.add_parser(
        'add-file',
        help='Upload file(s) to an existing dataset',
        description='Upload one or more files to an existing dataset without re-creating it',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Add a single file
    crucible dataset add-file DATASET_ID -i results.csv

    # Add multiple files
    crucible dataset add-file DATASET_ID -i file1.dat file2.dat

    # Add files matching a glob pattern
    crucible dataset add-file DATASET_ID -i *.csv
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
        '-i', '--input',
        nargs='+',
        required=True,
        metavar='FILE',
        help='File(s) to upload (supports glob patterns like *.csv)'
    )
    parser.set_defaults(func=_execute_add_file)


def _execute_add_file(args):
    """Execute the 'dataset add-file' subcommand."""
    import glob as _glob
    from crucible.client import CrucibleClient

    dsid = args.dataset_id

    # Expand glob patterns
    expanded = []
    for pattern in args.input:
        matches = sorted(_glob.glob(pattern))
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(pattern)  # keep as-is; validation below will catch missing files

    # Validate all files exist before starting any uploads
    files = []
    for f in expanded:
        p = Path(f)
        if not p.exists():
            logger.error(f"File not found: {f}")
            sys.exit(1)
        files.append(p)

    try:
        client = CrucibleClient()

        term.header(f"Add Files  {dsid}")
        rows = []
        for fpath in files:
            print(f"  Uploading {fpath.name} ...", flush=True)
            client.datasets.upload_file(dsid, str(fpath))
            rows.append((fpath.name, term.fmt_size(fpath.stat().st_size), '✓'))

        print()
        term.table(rows, ['File', 'Size', ''])

    except Exception as e:
        logger.error(f"Error uploading file(s): {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_list_files(subparsers):
    """Register the 'dataset list-files' subcommand."""
    parser = subparsers.add_parser(
        'list-files',
        help='List files in a dataset with download links',
        description='Show all files associated with a dataset. File names are '
                    'clickable download links (valid for 1 hour) in supporting terminals.',
    )
    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.set_defaults(func=_execute_list_files)


def _execute_list_files(args):
    """Execute the 'dataset list-files' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        dsid = args.dataset_id

        # Fetch metadata (size, hash) and signed download URLs in parallel
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_meta  = pool.submit(client.datasets.get_associated_files, dsid)
            f_links = pool.submit(client.datasets.get_download_links, dsid)
            meta_list  = f_meta.result()
            link_map   = f_links.result()   # {filepath: signed_url}

        links, meta_by_name = _normalize_file_paths(link_map, meta_list, dsid)

        # Only show files tracked in associated_files — filters out server-internal
        # files (ingest records, etc.) that appear in download_links but aren't
        # user files.
        all_names = sorted(meta_by_name)

        term.header(f"Files · {dsid} ({len(all_names)})")
        if not all_names:
            print(f"  {term.dim('No files found.')}")
            return

        rows = []
        for name in all_names:
            url   = links.get(name)
            size  = meta_by_name[name].get('size')
            label = term.hyperlink(term.cyan(name), url) if url else name
            rows.append((label, term.fmt_size(size) if size is not None else '—'))

        term.table(rows, ['File', 'Size'], max_widths=[60, 10])

        if links:
            print(f"\n  {term.dim('Download links are valid for 1 hour.')}")

    except Exception as e:
        logger.error(f"Error listing files: {e}")
        if getattr(args, 'debug', False):
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
        default=_config.default_limit,
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

        term.header(f"Search: {args.query} ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
        else:
            for r in results:
                mfid = r.get('dataset_mfid', '—')
                print(f"  {term.cyan(mfid)}")
                if args.verbose:
                    scimd = r.get('scientific_metadata', {})
                    for key, value in scimd.items():
                        if isinstance(value, dict):
                            print(f"    {term.dim(key + ':')} <dict, {len(value)} keys>")
                        elif isinstance(value, list):
                            print(f"    {term.dim(key + ':')} <list, {len(value)} items>")
                        else:
                            print(f"    {term.dim(key + ':')} {value}")

    except Exception as e:
        logger.error(f"Error searching datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_add_keyword(subparsers):
    """Register the 'dataset add-keyword' subcommand."""
    parser = subparsers.add_parser(
        'add-keyword',
        help='Add a keyword to a dataset',
        description='Associate a keyword tag with an existing dataset',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-keyword DATASET_ID silicon
    crucible dataset add-keyword DATASET_ID "in-situ TEM"
"""
    )

    parser.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
    parser.add_argument('keyword', metavar='KEYWORD', help='Keyword to add')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_add_keyword)


def _execute_add_keyword(args):
    """Execute the 'dataset add-keyword' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.add_keyword(args.dataset_id, args.keyword)

        logger.info(f"✓ Keyword '{args.keyword}' added to {args.dataset_id}")

    except Exception as e:
        logger.error(f"Error adding keyword: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_list_keywords(subparsers):
    """Register the 'dataset list-keywords' subcommand."""
    import argparse

    def _add_args(p):
        p.add_argument('dataset_id', metavar='DATASET_ID', help='Dataset unique ID')
        p.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    parser = subparsers.add_parser(
        'list-keywords',
        help='List keywords for a dataset',
        description='Show all keywords associated with a dataset',
    )
    _add_args(parser)
    parser.set_defaults(func=_execute_list_keywords)


def _execute_list_keywords(args):
    """Execute the 'dataset get-keywords' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        keywords = client.datasets.get_keywords(args.dataset_id)

        term.header(f"Keywords · {args.dataset_id} ({len(keywords)})")
        if not keywords:
            print(f"  {term.dim('No keywords found.')}")
            return
        for kw in keywords:
            word  = kw.get('keyword', kw) if isinstance(kw, dict) else kw
            count = kw.get('num_datasets') if isinstance(kw, dict) else None
            suffix = f"  {term.dim(f'({count} datasets)')}" if args.verbose and count is not None else ""
            print(f"  {word}{suffix}")

    except Exception as e:
        logger.error(f"Error retrieving keywords: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_parsers(subparsers):
    """Register the 'dataset parsers' subcommand."""
    parser = subparsers.add_parser(
        'parsers',
        help='List available dataset parsers',
        description='Show all available dataset parsers, including those installed via third-party packages',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
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
        import fnmatch
        client = CrucibleClient()
        datasets = client.datasets.list(project_id=project_id, limit=args.limit, **filters)

        # Client-side glob filtering on name
        if getattr(args, 'include', None):
            datasets = [ds for ds in datasets if any(
                fnmatch.fnmatch((ds.get('dataset_name') or '').lower(), p.lower())
                for p in args.include
            )]
        if getattr(args, 'exclude', None):
            datasets = [ds for ds in datasets if not any(
                fnmatch.fnmatch((ds.get('dataset_name') or '').lower(), p.lower())
                for p in args.exclude
            )]

        title = f"Datasets · {project_id} ({len(datasets)})" if project_id else f"Datasets ({len(datasets)})"
        term.header(title)
        if filters:
            logger.info(f"Filters: {', '.join(f'{k}={v}' for k, v in filters.items())}")

        if not datasets:
            print(f"  {term.dim('No datasets found.')}")
        else:
            try:
                from crucible.config import config as _cfg
                _base = _cfg.graph_explorer_url.rstrip('/')
            except Exception:
                _base = None

            _GROUP_FIELD = {
                'measurement': 'measurement',
                'session':     'session_name',
                'format':      'data_format',
                'instrument':  'instrument_name',
            }
            group_by_key = args.group_by or config.dataset_group_by or 'measurement'
            group_by = _GROUP_FIELD.get(group_by_key)

            def _make_row(ds):
                uid = ds.get('unique_id') or ''
                pid = ds.get('project_id') or project_id
                url = f"{_base}/{pid}/dataset/{uid}" if _base and uid and pid else None
                return (
                    ds.get('dataset_name') or '(unnamed)',
                    term.mfid_link(uid, url) if uid else '—',
                    ds.get('measurement') or '—',
                    ds.get('session_name') or '—',
                )

            _by_name = lambda ds: (ds.get('dataset_name') or '').lower()

            if not group_by:
                term.table([_make_row(ds) for ds in sorted(datasets, key=_by_name)],
                           ['Name', 'MFID', 'Measurement', 'Session'],
                           max_widths=[35, 26, 15, 20])
            else:
                from collections import defaultdict
                groups = defaultdict(list)
                for ds in datasets:
                    groups[ds.get(group_by) or None].append(ds)
                keys = sorted(k for k in groups if k) + ([None] if None in groups else [])
                for key in keys:
                    label = key or '(none)'
                    term.subheader(f"{label} ({len(groups[key])})")
                    term.table([_make_row(ds) for ds in sorted(groups[key], key=_by_name)],
                               ['Name', 'MFID', 'Measurement', 'Session'],
                               max_widths=[35, 26, 15, 20])

    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_get(args):
    """Execute the 'dataset get' subcommand."""
    from crucible.client import CrucibleClient
    output = getattr(args, 'output', None)
    include_metadata = output == 'json' or getattr(args, 'include_metadata', False)
    try:
        client = CrucibleClient()
        dataset = client.datasets.get(args.dataset_id, include_metadata=include_metadata)
        if dataset is None:
            logger.error(f"Dataset not found: {args.dataset_id}")
            sys.exit(1)
        if output == 'json':
            print(json.dumps(dataset, indent=2, default=str))
        else:
            _show_dataset(dataset, client,
                          verbose=getattr(args, 'verbose', False),
                          graph=getattr(args, 'graph', False),
                          include_metadata=include_metadata)
    except Exception as e:
        logger.error(f"Error retrieving dataset: {e}")
        if getattr(args, "debug", False):
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
            logger.error("Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    # Validate the project exists before doing any expensive work
    from crucible.client import CrucibleClient as _CC
    try:
        if _CC().projects.get(project_id) is None:
            logger.error(f"Project '{project_id}' not found.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error validating project: {e}")
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

    # Parse timestamp
    from crucible.utils import parse_timestamp as _parse_ts
    timestamp = None
    if args.timestamp:
        try:
            timestamp = _parse_ts(args.timestamp)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

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
            data_format=args.data_format,
            timestamp=timestamp,
        )
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # If a custom ingestor is used and the user didn't explicitly set -m,
    # clear the parser's default measurement so the server assigns it
    if args.ingestor != 'ApiUploadIngestor' and args.measurement is None:
        parser.measurement = None

    # Display dataset information
    _p = term.field_printer(14)

    term.header("Dataset")
    proj_label = f"{project_id} {term.dim('(from config)')}" if project_from_config else project_id
    _p("Project",     proj_label)
    _p("Parser",      ParserClass.__name__)
    _p("Name",        parser.dataset_name)
    _p("Measurement", parser.measurement or term.dim("(server assigns)"))
    _p("Data format", parser.data_format)
    _p("Session",     parser.session_name)
    _p("Timestamp",   parser.timestamp)
    _p("Public",      "yes" if parser.public else "no")
    _p("Instrument",  parser.instrument_name)
    _p("MFID",        dataset_mfid or term.dim("(server assigns)"))
    _p("Ingestor",    args.ingestor)

    if parser.files_to_upload:
        print(f"\n  {term.dim(f'Files ({len(parser.files_to_upload)})')}")
        for f in parser.files_to_upload:
            print(f"    {Path(f).name}")

    if parser.keywords:
        print(f"\n  {term.dim(f'Keywords ({len(parser.keywords)})')}")
        print(f"    {', '.join(parser.keywords)}")

    if parser.scientific_metadata:
        print(f"\n  {term.dim(f'Scientific Metadata ({len(parser.scientific_metadata)} fields)')}")
        for key, value in parser.scientific_metadata.items():
            if key == 'dump_files':
                print(f"    {key}: {len(value)} files")
            elif isinstance(value, (list, dict)) and len(str(value)) > 80:
                print(f"    {key}: <{type(value).__name__}, {len(value)} items>")
            else:
                print(f"    {key}: {value}")

    # Upload or dry run
    if args.dry_run:
        print("")
        logger.info("Dry run — not uploading. Remove --dry-run to upload.")
    else:
        print("")
        try:
            result = parser.upload_dataset(
                ingestor=args.ingestor,
                verbose=getattr(args, 'debug', False),
                wait_for_ingestion_response=True
            )

            logger.info("✓ Upload successful")
            created = result.get('created_record', {}) if result else {}
            if created:
                from crucible.client import CrucibleClient
                _show_dataset(created, CrucibleClient())

            if result and getattr(args, 'debug', False):
                logger.debug("Upload result details:")
                for key, value in result.items():
                    logger.debug(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"✗ Upload failed: {e}")
            if getattr(args, "debug", False):
                import traceback
                traceback.print_exc()
            sys.exit(1)


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


def _execute_link(args):
    """Execute the 'dataset link' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.link_parent_child(args.parent, args.child)

        logger.info(f"✓ Linked dataset {args.child} as child of {args.parent}")

    except Exception as e:
        logger.error(f"Error linking datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_parents(args):
    """Execute the 'dataset list-parents' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        parents = client.datasets.list_parents(args.dataset_id, limit=args.limit)

        term.header(f"Parent Datasets · {args.dataset_id} ({len(parents)})")
        if not parents:
            print(f"  {term.dim('No parent datasets found.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)', ds.get('unique_id') or '—',
                 ds.get('measurement') or '—') for ds in parents]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])

    except Exception as e:
        logger.error(f"Error listing parent datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_children(args):
    """Execute the 'dataset list-children' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        children = client.datasets.list_children(args.dataset_id, limit=args.limit)

        term.header(f"Child Datasets · {args.dataset_id} ({len(children)})")
        if not children:
            print(f"  {term.dim('No child datasets found.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)', ds.get('unique_id') or '—',
                 ds.get('measurement') or '—') for ds in children]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])

    except Exception as e:
        logger.error(f"Error listing child datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_samples(args):
    """Execute the 'dataset list-samples' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        samples = client.samples.list(dataset_id=args.dataset_id, limit=args.limit)

        term.header(f"Samples · {args.dataset_id} ({len(samples)})")
        if not samples:
            print(f"  {term.dim('No samples linked.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)', s.get('unique_id') or '—',
                 s.get('sample_type') or '—') for s in samples]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])

    except Exception as e:
        logger.error(f"Error listing samples: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_parsers(args):
    """Execute the 'dataset parsers' subcommand."""
    from crucible.parsers import PARSER_REGISTRY, get_all_parsers
    all_parsers = get_all_parsers()
    builtin_names = set(PARSER_REGISTRY.keys())

    term.header(f"Dataset Parsers ({len(all_parsers)})")
    if args.verbose:
        rows = [
            (
                name,
                "built-in" if name in builtin_names else "installed",
                getattr(cls, '_measurement', '—') or '—',
                getattr(cls, '_data_format', None) or '—',
            )
            for name, cls in sorted(all_parsers.items())
        ]
        term.table(rows, ['Name', 'Source', 'Measurement', 'Format'],
                   max_widths=[20, 10, 20, 15])
    else:
        rows = [
            (
                name,
                "built-in" if name in builtin_names else "installed",
                getattr(cls, '_measurement', '—') or '—',
            )
            for name, cls in sorted(all_parsers.items())
        ]
        term.table(rows, ['Name', 'Source', 'Measurement'], max_widths=[20, 10, 20])
    print(f"\n  {term.dim('Use with: crucible dataset create -i FILE -t TYPE ...')}")


def _register_ingestors(subparsers):
    """Register the 'dataset ingestors' subcommand."""
    parser = subparsers.add_parser(
        'ingestors',
        help='List available server-side ingestors',
        description='Show all known server-side ingestor classes',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
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

    title = f"Server-Side Ingestors ({len(ingestors)})"
    if args.filter:
        title += f"  [filter: {args.filter}]"
    term.header(title)
    if not ingestors:
        print(f"  {term.dim('No ingestors match the filter.')}")
    else:
        for name in ingestors:
            print(f"  {name}")
    print(f"\n  {term.dim('Use with: crucible dataset create -i FILE --ingestor INGESTOR_CLASS')}")
