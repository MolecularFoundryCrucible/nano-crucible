#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset subcommand for Crucible CLI.

Provides dataset-related operations: list, get, create, update-metadata, link, etc.
"""

import argparse
import sys
import json
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

from . import term


def _build_file_display(af_list, link_map, dsid):
    """Build display entries for a dataset's files.

    Returns list of dicts with keys: mfid, name, size, url (None if not ingested),
    ingested, backend ('gcs' unless the file is cataloged elsewhere).
    link_map is {mfid: signed_url} from get_download_links.
    """
    import os as _os
    prefix_sp = f'mf-storage-prod/{dsid}/'
    result = []
    for f in af_list:
        mfid         = f.get('mfid')
        storage_path = f.get('storage_path') or ''
        backend      = f.get('storage_backend') or 'gcs'
        if storage_path.startswith(prefix_sp):
            name     = storage_path[len(prefix_sp):]
            ingested = True
        else:
            staging  = f.get('filename') or ''
            name     = _os.path.basename(staging) or mfid
            ingested = False
        result.append({
            'mfid':     mfid,
            'name':     name,
            'size':     f.get('size'),
            'url':      link_map.get(mfid) if ingested else None,
            'ingested': ingested,
            'backend':  backend,
        })
    return result


def _format_file_label(item):
    name = item['name']
    backend = item['backend']
    if backend != 'gcs':
        return f"{name} {term.dim(f'({backend})')}"
    if item['ingested']:
        return term.navigation_link(name, item['url']) if item['url'] else name
    return f"{name} {term.yellow('(pending ingestion)')}"


def _show_scientific_metadata(sci_md):
    """Display scientific metadata. Delegates to helpers.show_scientific_metadata."""
    from .helpers import show_scientific_metadata
    show_scientific_metadata(sci_md)


def _show_dataset(dataset, client, verbose=False, graph=False, include_metadata=False, links=None, prefetched=None):
    """Display dataset fields. Extracted for reuse by top-level 'crucible get'."""
    _p = term.field_printer(14)

    from .helpers import (explorer_url, format_relationship_type,
                          instrument_reference, project_reference)

    def _ds_link(r):
        u = r.get('unique_id')
        _, p, _ = project_reference(r)
        return term.mfid_link(u, explorer_url(u, p, 'dataset'))

    term.header("Dataset")

    dr = dataset.get('deletion_request')
    if dr:
        status = dr.get('status', '')
        reason = dr.get('reason') or ''
        rid    = dr.get('id', '')
        color  = term.yellow if status == 'pending' else term.red
        msg    = color(f"Deletion {status}")
        if reason:
            msg += f'  "{reason}"'
        if rid:
            msg += '  ' + term.dim(f"(request #{rid})")
        print(f"  {msg}")

    project_title, project_id, project_url = project_reference(dataset)
    _p("Name",        term.bold(dataset.get('dataset_name') or '(unnamed)'))
    _p("MFID",        _ds_link(dataset))
    _p("Measurement", dataset.get('measurement'))
    _p("Data Type",   dataset.get('data_type'))
    _p("Session",     dataset.get('session_name'))
    _p("Description", dataset.get('description'))

    dsid = dataset.get('unique_id')

    if verbose:
        _p("Data Format", dataset.get('data_format'))
        _p("Size",        term.fmt_size(dataset.get('size')))

    if project_title or project_id:
        term.subheader("Project")
        if project_title:
            _p("Title", term.navigation_link(project_title, project_url))
        if project_id:
            _p("Project ID", project_id)

    instrument_name, instrument_id, instrument_url = instrument_reference(dataset)
    if instrument_name or instrument_id:
        term.subheader("Instrument")
        if instrument_name:
            _p("Name", term.navigation_link(instrument_name, instrument_url))
        if instrument_id:
            _p("Instrument ID", instrument_id)

    term.subheader("Access")
    _p("Owner",  term.fmt_owner(dataset))
    _p("Public", term.fmt_bool(dataset.get('public')))

    timing = (
        ("Timestamp", dataset.get('timestamp')),
        ("Created", dataset.get('creation_time')),
        ("Modified", dataset.get('modification_time')),
    )
    if any(value for _, value in timing):
        term.subheader("Timing")
        for label, value in timing:
            if value:
                _p(label, term.fmt_ts(value))

    if prefetched is not None:
        keywords = prefetched.get('keywords', [])
        af_list  = prefetched.get('af_list', [])
        link_map = prefetched.get('link_map', {})
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_kw    = pool.submit(client.datasets.get_keywords, dsid) if verbose else None
            f_meta  = pool.submit(client.datasets.list_files, dsid)
            f_links = pool.submit(client.datasets.get_download_links, dsid)
            if f_kw is not None:
                try:
                    keywords = f_kw.result()
                except Exception:
                    keywords = []
            else:
                keywords = []
            try:
                af_list = f_meta.result()
            except Exception:
                af_list = []
            try:
                link_map = f_links.result()
            except Exception:
                link_map = {}

    if verbose and keywords:
        words = [kw.get('keyword', kw) if isinstance(kw, dict) else kw for kw in keywords]
        term.subheader("Keywords")
        print(f"  {', '.join(words)}")

    file_display = _build_file_display(af_list, link_map, dsid)

    if file_display:
        term.subheader(f"Files ({len(file_display)})")
        rows = []
        for item in sorted(file_display, key=lambda x: x['name']):
            size    = term.fmt_size(item['size']) if item['size'] is not None else '-'
            rows.append((term.cyan(item['mfid']), _format_file_label(item), size))
        term.table(rows, ['MFID', 'File', 'Size'], max_widths=[26, 60, 10])

    if graph:
        links_list = links if links is not None else dataset.get('links')
        if not links_list:
            try:
                links_list = client.get_links(dsid)
            except Exception:
                links_list = None
        if links_list is None:
            from .helpers import show_warning
            show_warning("Could not fetch links.")
        else:
            _, proj, _ = project_reference(dataset)
            proj = proj or ''
            # 'direction' is relative to this dataset: links are stored
            # parent -> child, so a 'source' is one of its parents.
            linked_samples  = [l for l in links_list if l.get('direction') == 'undirected'
                               and l.get('resource_type') == 'sample']
            parent_datasets = [l for l in links_list if l.get('direction') == 'source'
                               and l.get('resource_type') == 'dataset']
            child_datasets  = [l for l in links_list if l.get('direction') == 'target'
                               and l.get('resource_type') == 'dataset']

            term.subheader(f"Linked Samples ({len(linked_samples)})")
            for s in linked_samples:
                uid = s['unique_id']
                print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'sample'))}  {s.get('name') or '(unnamed)'}")
            if not linked_samples:
                print(f"  {term.dim('(none)')}")

            term.subheader(f"Parents ({len(parent_datasets)})")
            for p in parent_datasets:
                uid = p['unique_id']
                print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'dataset'))}  "
                      f"{p.get('name') or '(unnamed)'}  {format_relationship_type(p)}")
            if not parent_datasets:
                print(f"  {term.dim('(none)')}")

            term.subheader(f"Children ({len(child_datasets)})")
            for c in child_datasets:
                uid = c['unique_id']
                print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'dataset'))}  "
                      f"{c.get('name') or '(unnamed)'}  {format_relationship_type(c)}")
            if not child_datasets:
                print(f"  {term.dim('(none)')}")

    if include_metadata:
        _show_scientific_metadata(dataset.get('scientific_metadata'))

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
from ..constants import PROJECT_SCOPES

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
    _register_reassign_project(dataset_subparsers)
    _register_transfer_ownership(dataset_subparsers)
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
    _register_add_thumbnail(dataset_subparsers)
    _register_list_files(dataset_subparsers)
    _register_ingestion(dataset_subparsers)
    _register_search(dataset_subparsers)
    _register_search_metadata(dataset_subparsers)
    _register_add_keyword(dataset_subparsers)
    _register_list_keywords(dataset_subparsers)
    _register_list_access_groups(dataset_subparsers)
    _register_add_access_group(dataset_subparsers)
    from ._access import register_access_commands
    register_access_commands(dataset_subparsers, 'datasets', id_metavar='DATASET_MFID')
    _register_parsers(dataset_subparsers)
    _register_ingestors(dataset_subparsers)


def _register_list(subparsers):
    """Register the 'dataset list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List datasets',
        description='List datasets, with optional filters',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list --project-id my-project
    crucible dataset list --project-id my-project --project-scope shared
    crucible dataset list --project-mfid 0tkn2knjast3h0008nyq9zps2c --project-scope all
    crucible dataset list --project-id my-project -m XRD
    crucible dataset list --project-id my-project -k silicon --limit 20
    crucible dataset list --instrument-mfid 0tkn2knjast3h0008nyq9zps2c
    crucible dataset list --session 2024-01-15-run
    crucible dataset list --project-id my-project --group-by measurement
    crucible dataset list --project-id my-project --include "run-*" "*XRD*"
    crucible dataset list --project-id my-project --exclude "*test*"
"""
    )

    from .helpers import DeprecatedAliasAction
    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument(
        '--project-id', '-p',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses the saved current project if omitted)'
    )
    project_group.add_argument(
        '--project-mfid',
        default=None,
        metavar='MFID',
        help='Canonical project MFID'
    )
    parser.add_argument(
        '-pid',
        action=DeprecatedAliasAction,
        deprecated_options={'-pid'},
        replacement='--project-id',
        dest='project_id',
        default=argparse.SUPPRESS,
        metavar='ID',
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--project-scope',
        choices=PROJECT_SCOPES,
        default=None,
        metavar='SCOPE',
        help='Project relationship to include: assigned, shared, or all (default: assigned)'
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
        '--data-type',
        default=None,
        dest='data_type',
        metavar='TYPE',
        help='Filter by data type (exact match)'
    )

    parser.add_argument(
        '--instrument',
        default=None,
        dest='instrument_name',
        metavar='NAME',
        help='Filter by instrument name (exact match)'
    )

    parser.add_argument(
        '--instrument-mfid',
        default=None,
        metavar='MFID',
        help='Filter by canonical instrument MFID across accessible projects'
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
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON array'
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
        metavar='DATASET_MFID',
        help='Dataset MFID'
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
        '--no-graph',
        action='store_false',
        dest='graph',
        help='Exclude linked samples, parents, and children'
    )
    parser.set_defaults(graph=True)

    parser.add_argument(
        '--json',
        dest='json',
        action='store_true',
        default=False,
        help='Output as JSON (always includes scientific metadata)'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'dataset create' subcommand."""
    from crucible.parsers import PARSER_REGISTRY

    parser = subparsers.add_parser(
        'create',
        help='Create a dataset, optionally attaching files',
        description='Create a dataset record and optionally parse, upload, or catalog files',
        formatter_class=lambda prog: term.ColorHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Create a dataset record without files
    crucible dataset create --project-id my-project --name "Planned experiment"

    # Preview what would be uploaded (dry run)
    crucible dataset create -i file1.dat --project-id my-project --dry-run

    # Generic upload (server assigns mfid)
    crucible dataset create -i file1.dat file2.csv --project-id my-project

    # Upload with locally generated mfid
    crucible dataset create -i data.csv --project-id my-project --mfid

    # Upload with explicit mfid (e.g., re-uploading same dataset)
    crucible dataset create -i data.csv --project-id my-project --mfid 0tcxz5xs5xr6q0002vmzmp3beg

    # Generic upload with metadata and keywords
    crucible dataset create -i data.csv --project-id my-project \\
        --metadata '{"temperature": 300, "pressure": 1.0}' \\
        --keywords "experiment,thermal" -m "thermal_analysis"

    # Upload multiple files using wildcards
    crucible dataset create -i *.dat --project-id my-project -m "raw_data"

    # Parse and upload LAMMPS simulation
    crucible dataset create -i input.lmp -t lammps --project-id my-project
"""
    )

    # Input file(s)
    input_arg = parser.add_argument(
        '-i', '--input',
        nargs='+',
        default=None,
        metavar='FILE',
        help='Optional input file(s) to upload or catalog (supports wildcards like *.dat)'
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
    from .helpers import DeprecatedAliasAction
    parser.add_argument(
        '--project-id', '-p',
        required=False,
        default=None,
        metavar='ID',
        help='Crucible project ID (uses the saved current project if omitted)'
    )
    parser.add_argument(
        '--project-mfid',
        required=False,
        default=None,
        metavar='MFID',
        help='Canonical project MFID (advanced; may accompany a matching --project-id)'
    )
    parser.add_argument(
        '-pid',
        action=DeprecatedAliasAction,
        deprecated_options={'-pid'},
        replacement='--project-id',
        dest='project_id',
        default=argparse.SUPPRESS,
        metavar='ID',
        help=argparse.SUPPRESS,
    )

    # Unique ID / mfid
    parser.add_argument(
        '--mfid', '--uuid', '--unique-id', '--id',
        dest='mfid',
        nargs='?',
        const=True,
        default=None,
        metavar='MFID',
        help='Dataset MFID. If omitted, the server assigns one. If the flag is provided without a value, the client generates one locally.'
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
    parser.add_argument(
        '--instrument-id',
        default=None,
        metavar='ID',
        help='Registered instrument ID (optional)'
    )
    parser.add_argument(
        '--instrument-mfid',
        default=None,
        metavar='MFID',
        help='Canonical registered instrument MFID (advanced; may accompany a matching --instrument-id)'
    )

    # Data format
    parser.add_argument(
        '--data-format',
        dest='data_format',
        default=None,
        metavar='FORMAT',
        help='Data format type (optional)'
    )

    # Data type
    parser.add_argument(
        '--data-type',
        dest='data_type',
        default=None,
        metavar='TYPE',
        help='Data type (optional)'
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
        default=None,
        metavar='CLASS',
        help='Server-side ingestor class to use (default: auto-detected from file format). '
             'Run "crucible dataset ingestors" to see all available options.'
    )
    if ARGCOMPLETE_AVAILABLE:
        ingestor_arg.completer = lambda **kwargs: AVAILABLE_INGESTORS

    # Dry run flag
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Show what would be created without making API changes'
    )

    # Catalog-only (non-GCS) files
    parser.add_argument(
        '--no-upload',
        action='store_true',
        dest='no_upload',
        help="Catalog the input file(s) by path instead of uploading them to GCS "
             "(e.g. files on Globus/NERSC/a shared filesystem). Only supported for "
             "generic uploads (no -t/--type). Files must exist at the given path."
    )
    parser.add_argument(
        '--backend',
        dest='backend',
        default=None,
        metavar='NAME',
        help="Storage backend name for --no-upload files (e.g. 'globus', 'nersc-perlmutter'). "
             "Default: 'local'."
    )
    parser.add_argument(
        '--access-note',
        dest='access_note',
        default=None,
        metavar='TEXT',
        help="Free-text note on how to access --no-upload files (e.g. 'request via NERSC allocation X')."
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
        did_arg = p.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
        if ARGCOMPLETE_AVAILABLE:
            did_arg.completer = argcomplete.completers.SuppressCompleter()
        p.add_argument('--set', '-s', action='append', dest='set_fields', metavar='KEY=VALUE',
                       help='Set a dataset field (repeatable). Values are auto-cast to int, float, bool, or string.')
        p.add_argument('--metadata', default=None, metavar='JSON',
                       help='Scientific metadata as JSON string or path to JSON file')
        p.add_argument('--overwrite', action='store_true',
                       help='Replace all existing scientific metadata instead of merging (only with --metadata)')

    parser = subparsers.add_parser(
        'update',
        help='Update dataset fields or scientific metadata',
        description='Update fields or scientific metadata of an existing dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog=f"""
Updatable fields (use --set):
    {', '.join(fields)}

Examples:
    crucible dataset update DATASET_MFID --set dataset_name="My Dataset"
    crucible dataset update DATASET_MFID --set measurement=XRD --set session_name=run-01
    crucible dataset update DATASET_MFID --metadata '{{"temperature": 300, "pressure": 1.0}}'
    crucible dataset update DATASET_MFID --metadata metadata.json
    crucible dataset update DATASET_MFID --set measurement=XRD --metadata '{{"temperature": 300}}'

Use `dataset set-public` or `dataset set-private` to change public visibility.
"""
    )
    _add_args(parser)
    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'dataset update' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import cast_value

    has_set = bool(getattr(args, 'set_fields', None))
    has_metadata = bool(getattr(args, 'metadata', None))

    if not has_set and not has_metadata:
        logger.error("Error: provide at least one of --set KEY=VALUE or --metadata JSON")
        sys.exit(1)

    # Parse --set for model field updates
    updates = {}
    public = None
    if has_set:
        valid_fields = set(_dataset_updatable_fields())
        for field in args.set_fields:
            if '=' not in field:
                logger.error(f"Error: --set requires KEY=VALUE format, got: '{field}'")
                sys.exit(1)
            key, _, value = field.partition('=')
            key = key.strip()
            if key == 'public':
                public = cast_value(value)
                if not isinstance(public, bool):
                    logger.error("Error: public must be true or false")
                    sys.exit(1)
                warning = term.yellow('Warning:', stream=sys.stderr)
                replacement = 'set-public' if public else 'set-private'
                print(
                    f"{warning} --set public=... is deprecated; use dataset {replacement} instead.",
                    file=sys.stderr,
                )
                continue
            if key not in valid_fields:
                logger.error(
                    f"Unknown field '{key}'.\n"
                    f"Valid fields: {', '.join(sorted(valid_fields))}"
                )
                sys.exit(1)
            updates[key] = cast_value(value)

    metadata_dict = None
    if has_metadata:
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)

    try:
        client = CrucibleClient()

        if updates:
            client.datasets.update(args.dataset_id, **updates)
            term.success(f"Dataset {args.dataset_id} fields updated", args)
            if getattr(args, "debug", False):
                logger.debug(f"Updated fields: {list(updates.keys())}")

        if public is not None:
            operation = client.datasets.set_public if public else client.datasets.set_private
            operation(args.dataset_id)
            visibility = 'publicly viewable' if public else 'private'
            term.success(f"Dataset {args.dataset_id} is now {visibility}", args)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.datasets.update_scientific_metadata(
                args.dataset_id, metadata_dict, overwrite=overwrite
            )
            action = "replaced" if overwrite else "updated"
            term.success(f"Scientific metadata {action} for dataset {args.dataset_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("updating dataset", e, args)


def _register_reassign_project(subparsers):
    """Register the 'dataset reassign-project' subcommand."""
    parser = subparsers.add_parser(
        'reassign-project',
        help='Move a dataset to a different project',
        description='Preview or execute a project reassignment (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset reassign-project DATASET_MFID new-project
    crucible dataset reassign-project DATASET_MFID new-project --confirm
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Target project ID')
    parser.add_argument('--confirm', action='store_true', help='Execute the move (default: preview only)')
    parser.set_defaults(func=_execute_reassign_project)


def _execute_reassign_project(args):
    """Execute the 'dataset reassign-project' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_reassign_project

    try:
        client = CrucibleClient()
        result = client.datasets.reassign_project(args.dataset_id, args.project_id, confirm=args.confirm)
        show_reassign_project(result, args.confirm)
    except Exception as e:
        fail("reassigning dataset project", e, args)


def _register_transfer_ownership(subparsers):
    """Register the 'dataset transfer-ownership' subcommand."""
    parser = subparsers.add_parser(
        'transfer-ownership',
        help='Transfer ownership of a dataset',
        description='Preview or execute an ownership transfer (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset transfer-ownership DATASET_MFID newowner@example.com
    crucible dataset transfer-ownership DATASET_MFID newowner@example.com --confirm
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('new_owner', metavar='NEW_OWNER', help='ORCID, MFID, username, or email of the new owner')
    parser.add_argument('--confirm', action='store_true', help='Execute the transfer (default: preview only)')
    parser.set_defaults(func=_execute_transfer_ownership)


def _execute_transfer_ownership(args):
    """Execute the 'dataset transfer-ownership' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_transfer_ownership

    try:
        client = CrucibleClient()
        result = client.datasets.transfer_ownership(args.dataset_id, args.new_owner, confirm=args.confirm)
        show_transfer_ownership(result, args.confirm)
    except Exception as e:
        fail("transferring dataset ownership", e, args)


def _register_delete(subparsers):
    """Register the 'dataset delete' subcommand."""
    parser = subparsers.add_parser(
        'delete',
        help='Delete a dataset',
        description='Permanently delete a dataset (irreversible). Prompts for confirmation unless -y is given.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset delete DATASET_MFID
    crucible dataset delete DATASET_MFID -y
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID to delete')
    parser.add_argument('-y', '--yes', action='store_true', help='Confirm deletion without prompting')
    parser.set_defaults(func=_execute_delete)


def _execute_delete(args):
    """Execute the 'dataset delete' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import prompt_confirm
    confirmed = args.yes or prompt_confirm(
        f"Delete dataset {args.dataset_id}? This cannot be undone.",
        option='--yes',
    )
    if not confirmed:
        print("Aborted.")
        return
    try:
        client = CrucibleClient()
        client.datasets.delete(args.dataset_id)
        term.success(f"Deleted dataset {args.dataset_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("deleting dataset", e, args)


def _register_edit(subparsers):
    """Register the 'dataset edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit dataset fields interactively',
        description='Open dataset fields in $EDITOR and update on save. Scientific metadata is included as a top-level key.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset edit DATASET_MFID
    EDITOR=vim crucible dataset edit DATASET_MFID
"""
    )
    did_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_MFID',
        help='Dataset MFID'
    )
    if ARGCOMPLETE_AVAILABLE:
        did_arg.completer = argcomplete.completers.SuppressCompleter()
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
        from .helpers import fail
        fail("updating dataset", e, debug)


def _execute_edit(args):
    """Execute the 'dataset edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)
    _edit_dataset(args.dataset_id, client, debug=getattr(args, 'debug', False))


def _register_link(subparsers):
    """Register the 'dataset link' subcommand."""
    from crucible.constants import RELATIONSHIP_TYPES

    parser = subparsers.add_parser(
        'link',
        help='Link parent and child datasets',
        description='Create a parent-child relationship between datasets'
    )

    parser.add_argument(
        '-p', '--parent',
        required=True,
        metavar='PARENT_MFID',
        help='Parent dataset MFID'
    )

    parser.add_argument(
        '-c', '--child',
        required=True,
        metavar='CHILD_MFID',
        help='Child dataset MFID'
    )

    parser.add_argument(
        '--relationship-type',
        choices=RELATIONSHIP_TYPES,
        metavar='TYPE',
        help=f"Kind of link, describing the child relative to the parent "
             f"({', '.join(RELATIONSHIP_TYPES)}). Omit to leave it unspecified."
    )

    parser.set_defaults(func=_execute_link)


def _register_add_sample(subparsers):
    """Register the 'dataset add-sample' subcommand."""
    parser = subparsers.add_parser(
        'add-sample',
        help='Link a sample to a dataset',
        description='Associate a sample with a dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-sample DATASET_MFID --sample SAMPLE_MFID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('-s', '--sample', required=True, metavar='SAMPLE_MFID', help='Sample MFID')
    parser.set_defaults(func=_execute_add_sample)


def _execute_add_sample(args):
    """Execute the 'dataset add-sample' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.link_sample(args.dataset_id, args.sample)

        term.success(f"Linked sample {args.sample} to dataset {args.dataset_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("linking sample to dataset", e, args)


def _register_remove_sample(subparsers):
    """Register the 'dataset remove-sample' subcommand."""
    parser = subparsers.add_parser(
        'remove-sample',
        help='Unlink a sample from a dataset',
        description='Remove the association between a dataset and a sample (requires admin)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset remove-sample DATASET_MFID --sample SAMPLE_MFID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('-s', '--sample', required=True, metavar='SAMPLE_MFID', help='Sample MFID to unlink')
    parser.set_defaults(func=_execute_remove_sample)


def _execute_remove_sample(args):
    """Execute the 'dataset remove-sample' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.unlink_sample(args.dataset_id, args.sample)
        term.success(f"Unlinked sample {args.sample} from dataset {args.dataset_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("unlinking sample from dataset", e, args)


def _register_remove_child(subparsers):
    """Register the 'dataset remove-child' subcommand."""
    parser = subparsers.add_parser(
        'remove-child',
        help='Unlink a child dataset from a parent dataset',
        description='Remove the parent-child relationship between two datasets (requires admin)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset remove-child PARENT_MFID --child CHILD_MFID
"""
    )
    parser.add_argument('parent_id', metavar='PARENT_MFID', help='Parent dataset MFID')
    parser.add_argument('-c', '--child', required=True, metavar='CHILD_MFID', help='Child dataset MFID to unlink')
    parser.set_defaults(func=_execute_remove_child)


def _execute_remove_child(args):
    """Execute the 'dataset remove-child' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.unlink(args.parent_id, args.child)
        term.success(f"Unlinked child dataset {args.child} from parent dataset {args.parent_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("unlinking child dataset", e, args)


def _register_list_parents(subparsers):
    """Register the 'dataset list-parents' subcommand."""
    parser = subparsers.add_parser(
        'list-parents',
        help='List parent datasets',
        description='List parent datasets of a given dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-parents DATASET_MFID
    crucible dataset list-parents DATASET_MFID --limit 20
    crucible dataset list-parents DATASET_MFID --relationship-type is_part_of
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    from .helpers import add_relationship_type_filter
    add_relationship_type_filter(parser)
    parser.set_defaults(func=_execute_list_parents)


def _register_list_children(subparsers):
    """Register the 'dataset list-children' subcommand."""
    parser = subparsers.add_parser(
        'list-children',
        help='List child datasets',
        description='List child datasets derived from a given dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-children DATASET_MFID
    crucible dataset list-children DATASET_MFID --limit 20
    crucible dataset list-children DATASET_MFID --relationship-type is_derived_from
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    from .helpers import add_relationship_type_filter
    add_relationship_type_filter(parser)
    parser.set_defaults(func=_execute_list_children)


def _register_list_samples(subparsers):
    """Register the 'dataset list-samples' subcommand."""
    parser = subparsers.add_parser(
        'list-samples',
        help='List samples linked to a dataset',
        description='Show all samples associated with a given dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-samples DATASET_MFID
"""
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    parser.set_defaults(func=_execute_list_samples)


def _register_download(subparsers):
    """Register the 'dataset download' subcommand."""
    parser = subparsers.add_parser(
        'download',
        help='Download dataset files',
        description='Download files from a Crucible dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Download all files into ./crucible-downloads/<dataset_id>/
    crucible dataset download DATASET_MFID

    # Download to a specific directory
    crucible dataset download DATASET_MFID -o my_data/

    # Download a single file
    crucible dataset download DATASET_MFID -f results.csv

    # Only download CSV files
    crucible dataset download DATASET_MFID --include "*.csv"

    # Download everything except raw files
    crucible dataset download DATASET_MFID --exclude "*.raw"

    # Include multiple patterns
    crucible dataset download DATASET_MFID --include "*.csv" --include "*.json"

    # Combine include and exclude
    crucible dataset download DATASET_MFID --include "data/*" --exclude "*.tmp"

    # Force re-download of files that already exist locally
    crucible dataset download DATASET_MFID --overwrite
"""
    )

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_MFID',
        help='Dataset MFID'
    )
    if ARGCOMPLETE_AVAILABLE:
        dataset_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '-o', '--output-dir',
        dest='output_dir',
        default=None,
        metavar='DIR',
        help='Directory to save downloaded files (default: crucible-downloads/DATASET_MFID/)'
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
            term.success(f"Downloaded {len(downloaded)} file(s)", args)
            for path in downloaded:
                logger.info(f"  {path}")

    except Exception as e:
        from .helpers import fail
        fail("downloading dataset", e, args)


def _register_add_file(subparsers):
    """Register the 'dataset add-file' subcommand."""
    parser = subparsers.add_parser(
        'add-file',
        help='Upload file(s) to an existing dataset',
        description='Upload one or more files to an existing dataset without re-creating it',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Add a single file
    crucible dataset add-file DATASET_MFID -i results.csv

    # Add multiple files
    crucible dataset add-file DATASET_MFID -i file1.dat file2.dat

    # Add files matching a glob pattern
    crucible dataset add-file DATASET_MFID -i *.csv
"""
    )

    dataset_id_arg = parser.add_argument(
        'dataset_id',
        metavar='DATASET_MFID',
        help='Dataset MFID'
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
    parser.add_argument(
        '--ingestor',
        default=None,
        metavar='CLASS',
        help='Ingestion class to use (default: auto-detected from file format)'
    )
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait for ingestion to complete before returning'
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

        ingestor = getattr(args, 'ingestor', None)
        wait     = getattr(args, 'wait', False)

        term.header(f"Add Files  {dsid}")
        rows = []
        for fpath in files:
            print(f"  Uploading {fpath.name} ...", flush=True)
            client.datasets.add_file(dsid, str(fpath),
                                                ingestion_class=ingestor,
                                                wait_for_ingestion_response=wait)
            rows.append((fpath.name, term.fmt_size(fpath.stat().st_size),
                         term.status_marker('success')))

        print()
        term.table(rows, ['File', 'Size', ''], max_widths=[60, 10, 4])

    except Exception as e:
        from .helpers import fail
        fail("uploading file(s)", e, args)


def _register_add_thumbnail(subparsers):
    """Register the 'dataset add-thumbnail' subcommand."""
    parser = subparsers.add_parser(
        'add-thumbnail',
        help='Add a thumbnail to an existing dataset',
        description='Encode a local image and add it as a dataset thumbnail',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-thumbnail DATASET_MFID preview.png
    crucible dataset add-thumbnail DATASET_MFID preview.png --name overview.png
""",
    )
    dataset_mfid_arg = parser.add_argument(
        'dataset_mfid',
        metavar='DATASET_MFID',
        help='Dataset MFID',
    )
    if ARGCOMPLETE_AVAILABLE:
        dataset_mfid_arg.completer = argcomplete.completers.SuppressCompleter()
    image_arg = parser.add_argument(
        'image',
        metavar='IMAGE',
        help='Path to the local thumbnail image',
    )
    if ARGCOMPLETE_AVAILABLE:
        image_arg.completer = FilesCompleter()
    parser.add_argument(
        '--name',
        metavar='NAME',
        help='Thumbnail name stored by the API (default: local filename)',
    )
    parser.set_defaults(func=_execute_add_thumbnail)


def _execute_add_thumbnail(args):
    """Execute the 'dataset add-thumbnail' subcommand."""
    from crucible.client import CrucibleClient

    try:
        image_path = Path(args.image).expanduser()
        if not image_path.is_file():
            raise FileNotFoundError(f"Thumbnail image not found: {image_path}")

        client = CrucibleClient()
        client.datasets.add_thumbnail(
            args.dataset_mfid,
            str(image_path),
            thumbnail_name=args.name,
        )
        thumbnail_name = args.name or image_path.name
        term.success(
            f"Added thumbnail {thumbnail_name} to dataset {args.dataset_mfid}",
            args,
        )
    except Exception as e:
        from .helpers import fail
        fail("adding dataset thumbnail", e, args)


def _register_list_files(subparsers):
    """Register the 'dataset list-files' subcommand."""
    parser = subparsers.add_parser(
        'list-files',
        help='List files in a dataset with download links',
        description='Show all files associated with a dataset. File names are '
                    'clickable download links (valid for 1 hour) in supporting terminals.',
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
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
            f_meta  = pool.submit(client.datasets.list_files, dsid)
            f_links = pool.submit(client.datasets.get_download_links, dsid)
            meta_list  = f_meta.result()
            link_map   = f_links.result()   # {filepath: signed_url}

        file_display = _build_file_display(meta_list, link_map, dsid)

        term.header(f"Files · {dsid} ({len(file_display)})")
        if not file_display:
            print(f"  {term.dim('No files found.')}")
            return

        rows = []
        for item in sorted(file_display, key=lambda x: x['name']):
            size    = term.fmt_size(item['size']) if item['size'] is not None else '-'
            rows.append((term.cyan(item['mfid']), _format_file_label(item), size))

        term.table(rows, ['MFID', 'File', 'Size'], max_widths=[26, 60, 10])

        if any(item['ingested'] for item in file_display):
            print(f"\n  {term.dim('Download links are valid for 1 hour.')}")

    except Exception as e:
        from .helpers import fail
        fail("listing files", e, args)


def _register_ingestion(subparsers):
    parser = subparsers.add_parser(
        'ingestion',
        help='Show ingestion requests for a dataset',
        description='List ingestion requests for all files in a dataset.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset ingestion DATASET_MFID
""",
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.set_defaults(func=_execute_ingestion)


def _execute_ingestion(args):
    """Execute 'crucible dataset ingestion'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        reqs = client.ingestions.list(dsid=args.dataset_id)

        term.header(f"Ingestion Requests · {args.dataset_id} ({len(reqs)})")
        if not reqs:
            print(f"  {term.dim('No ingestion requests found.')}")
            return

        rows = []
        for r in reqs:
            rows.append((
                str(r.get('id', '-')),
                term.status_label(r.get('status')),
                r.get('ingestion_class') or '-',
                term.cyan(r.get('file_id')) if r.get('file_id') else '-',
                term.fmt_ts(r.get('created_at') or r.get('creation_time')) or '-',
            ))
        term.table(rows, ['ID', 'Status', 'Class', 'File MFID', 'Created'],
                   max_widths=[8, 12, 25, 30, 20])

    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_search(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Fuzzy search datasets by name',
        description='Fuzzy name search across datasets you can read. '
                    'For scientific metadata search use search-metadata.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset search perovskite
    crucible dataset search "silicon wafer" --project-id my-project
    crucible dataset search XRD --limit 10
""",
    )
    parser.add_argument('query', metavar='QUERY', help='Search term (min 3 chars)')
    from .helpers import DeprecatedAliasAction
    parser.add_argument(
        '--project-id', '-p',
        dest='project_id',
        default=None,
        metavar='ID',
        help='Scope to a project (uses the saved current project if omitted)',
    )
    parser.add_argument(
        '--project', '-pid',
        action=DeprecatedAliasAction,
        deprecated_options={'--project', '-pid'},
        replacement='--project-id',
        dest='project_id',
        default=argparse.SUPPRESS,
        metavar='ID',
        help=argparse.SUPPRESS,
    )
    parser.add_argument('--limit', '-l', type=int, default=20, metavar='N',
                        help='Maximum results (default: 20, max: 50)')
    parser.add_argument('--json', action='store_true', default=False,
                        help='Output as JSON array')
    parser.set_defaults(func=_execute_search)


def _execute_search(args):
    if len(args.query) < 3:
        from .helpers import fail
        fail("searching datasets", ValueError("Search term must be at least 3 characters."), args)
    from crucible.client import CrucibleClient
    try:
        from .helpers import resolve_project_context
        client     = CrucibleClient()
        project_id, _ = resolve_project_context(args, args.project_id)
        results    = client.datasets.search(args.query, project_id=project_id,
                                            limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Datasets matching '{args.query}' ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        from .helpers import explorer_url, project_reference
        rows = []
        for r in results:
            uid  = r.get('unique_id') or ''
            _, referenced_project_id, _ = project_reference(r)
            pid = referenced_project_id or project_id or ''
            rows.append((
                r.get('dataset_name') or '(unnamed)',
                term.mfid_link(uid, explorer_url(uid, pid, 'dataset')),
                r.get('measurement') or '-',
            ))
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 20])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_search_metadata(subparsers):
    for name in ('search-metadata', 'search-md'):
        parser = subparsers.add_parser(
            name,
            help='Search datasets by scientific metadata' if name == 'search-metadata' else None,
            description='Full-text search across scientific metadata of all accessible datasets.',
            formatter_class=term.ColorHelpFormatter,
            epilog="""
Examples:
    crucible dataset search-metadata "thermal conductivity"
    crucible dataset search-md "silicon XRD 300K"
""",
        )
        parser.add_argument('query', metavar='QUERY', help='Search query string')
        parser.add_argument('--limit', '-l', type=int, default=50, metavar='N',
                            help='Maximum results (default: 50)')
        parser.add_argument('--json', action='store_true', default=False,
                            help='Output as JSON array')
        parser.set_defaults(func=_execute_search_metadata)


def _execute_search_metadata(args):
    from crucible.client import CrucibleClient
    try:
        client  = CrucibleClient()
        results = client.datasets.search_metadata(args.query, limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Metadata search: {args.query} ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        for r in results:
            mfid  = r.get('unique_id') or r.get('dataset_mfid', '-')
            print(f"  {term.cyan(mfid)}")
            scimd = r.get('scientific_metadata') or {}
            for key, value in scimd.items():
                if isinstance(value, dict):
                    print(f"    {term.dim(key + ':')} <dict, {len(value)} keys>")
                elif isinstance(value, list):
                    print(f"    {term.dim(key + ':')} <list, {len(value)} items>")
                else:
                    print(f"    {term.dim(key + ':')} {value}")
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_add_keyword(subparsers):
    """Register the 'dataset add-keyword' subcommand."""
    parser = subparsers.add_parser(
        'add-keyword',
        help='Add a keyword to a dataset',
        description='Associate a keyword tag with an existing dataset',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-keyword DATASET_MFID silicon
    crucible dataset add-keyword DATASET_MFID "in-situ TEM"
"""
    )

    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('keyword', metavar='KEYWORD', help='Keyword to add')
    parser.set_defaults(func=_execute_add_keyword)


def _execute_add_keyword(args):
    """Execute the 'dataset add-keyword' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.add_keyword(args.dataset_id, args.keyword)

        term.success(f"Keyword '{args.keyword}' added to {args.dataset_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("adding keyword", e, args)


def _register_list_keywords(subparsers):
    """Register the 'dataset list-keywords' subcommand."""
    import argparse

    def _add_args(p):
        p.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')

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
            suffix = f"  {term.dim(f'({count} datasets)')}" if getattr(args, 'verbose', False) and count is not None else ""
            print(f"  {word}{suffix}")

    except Exception as e:
        from .helpers import fail
        fail("retrieving keywords", e, args)


def _register_list_access_groups(subparsers):
    parser = subparsers.add_parser(
        'list-access-groups',
        help='Deprecated: use dataset access list',
        description='Deprecated compatibility command. Use dataset access list.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-access-groups DATASET_MFID
""",
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.set_defaults(func=_execute_list_access_groups)


def _execute_list_access_groups(args):
    """Execute 'crucible dataset list-access-groups'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        groups = client.datasets.get_access_groups(args.dataset_id)
        term.header(f"Access Groups · {args.dataset_id} ({len(groups)})")
        if not groups:
            print(f"  {term.dim('No access groups found.')}")
        else:
            for g in groups:
                print(f"  {g}")
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_add_access_group(subparsers):
    parser = subparsers.add_parser(
        'add-access-group',
        help='Deprecated: use dataset access grant',
        description='Deprecated compatibility command. Use dataset access grant.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset add-access-group DATASET_MFID my-group
    crucible dataset add-access-group DATASET_MFID my-group --write
""",
    )
    parser.add_argument('dataset_id', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('group_name', metavar='GROUP',      help='Access group name')
    parser.add_argument('--write', action='store_true', default=False,
                        help='Also grant write access (read access is always granted)')
    parser.set_defaults(func=_execute_add_access_group)


def _execute_add_access_group(args):
    """Execute 'crucible dataset add-access-group'."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.add_access_group(args.dataset_id, args.group_name,
                                         read=True, write=args.write)
        perms = 'read+write' if args.write else 'read'
        term.success(f"Access group '{args.group_name}' added to {args.dataset_id} ({perms})", args)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_parsers(subparsers):
    """Register the 'dataset parsers' subcommand."""
    parser = subparsers.add_parser(
        'parsers',
        help='List available dataset parsers',
        description='Show all available dataset parsers, including those installed via third-party packages',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset parsers
    crucible dataset parsers -v
"""
    )

    parser.set_defaults(func=_execute_parsers)


def _execute_list(args):
    """Execute the 'dataset list' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    from .helpers import resolve_project_context
    project_id = args.project_id
    project_mfid = getattr(args, 'project_mfid', None)
    project_scope = getattr(args, 'project_scope', None)
    instrument_mfid = getattr(args, 'instrument_mfid', None)
    if project_id is not None and project_mfid is not None:
        logger.error("Error: Specify either --project-id or --project-mfid, not both.")
        sys.exit(1)
    if (project_id is None and project_mfid is None and
            (instrument_mfid is None or project_scope is not None)):
        project_id, _ = resolve_project_context(args)
    if project_scope is not None and project_id is None and project_mfid is None:
        logger.error("Error: --project-scope requires --project-id, --project-mfid, or a saved current project.")
        sys.exit(1)
    if project_id is None and project_mfid is None and instrument_mfid is None:
        logger.error(
            "Error: Project ID, project MFID, or instrument MFID required. Specify "
            "--project-id, --project-mfid, --instrument-mfid, or set current_project in config.")
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
    if args.data_type:
        filters['data_type'] = args.data_type
    if args.instrument_name:
        filters['instrument_name'] = args.instrument_name
    if instrument_mfid:
        filters['instrument_mfid'] = instrument_mfid
    project_filters = {}
    if project_id is not None:
        project_filters['project_id'] = project_id
    if project_mfid is not None:
        project_filters['project_mfid'] = project_mfid
    if project_scope is not None:
        project_filters['project_scope'] = project_scope

    try:
        import fnmatch
        client = CrucibleClient()
        datasets = client.datasets.list(limit=args.limit, **project_filters, **filters)

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

        if getattr(args, 'json', False):
            print(json.dumps(datasets, indent=2, default=str))
            return

        project_label = project_id or project_mfid
        if project_label:
            scope_label = f" · {project_scope}" if project_scope else ''
            title = f"Datasets · {project_label}{scope_label} ({len(datasets)})"
        elif instrument_mfid:
            title = f"Datasets · instrument {instrument_mfid} ({len(datasets)})"
        else:
            title = f"Datasets ({len(datasets)})"
        term.header(title)
        if filters:
            logger.info(f"Filters: {', '.join(f'{k}={v}' for k, v in filters.items())}")

        if not datasets:
            print(f"  {term.dim('No datasets found.')}")
        else:
            from .helpers import explorer_url, project_reference

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
                _, referenced_project_id, _ = project_reference(ds)
                pid = referenced_project_id or project_id
                row = (
                    ds.get('dataset_name') or '(unnamed)',
                    term.mfid_link(uid, explorer_url(uid, pid, 'dataset')) if uid else '-',
                )
                if project_scope in ('shared', 'all'):
                    row += (
                        referenced_project_id or '-',
                        ds.get('project_relation') or '-',
                    )
                return row + (
                    ds.get('measurement') or '-',
                    ds.get('session_name') or '-',
                )

            contextual_headers = ['Name', 'MFID', 'Project', 'Relation', 'Measurement', 'Session']
            standard_headers = ['Name', 'MFID', 'Measurement', 'Session']
            headers = contextual_headers if project_scope in ('shared', 'all') else standard_headers
            contextual_max = [25, 26, 25, 8, 15, 18]
            standard_max = [35, 26, 15, 20]
            max_widths = contextual_max if project_scope in ('shared', 'all') else standard_max
            contextual_min = [4, 26, 7, 8, 11, 7]
            standard_min = [4, 26, 11, 7]
            min_widths = contextual_min if project_scope in ('shared', 'all') else standard_min

            _by_name = lambda ds: (ds.get('dataset_name') or '').lower()

            if not group_by:
                term.table([_make_row(ds) for ds in sorted(datasets, key=_by_name)],
                           headers, max_widths=max_widths,
                           min_widths=min_widths)
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
                               headers, max_widths=max_widths,
                               min_widths=min_widths)

    except Exception as e:
        from .helpers import fail
        fail("listing datasets", e, args)


def _execute_get(args):
    """Execute the 'dataset get' subcommand."""
    from crucible.client import CrucibleClient
    as_json = getattr(args, 'json', False)
    include_metadata = as_json or getattr(args, 'include_metadata', False) or _config.include_metadata
    try:
        client = CrucibleClient()
        graph   = getattr(args, 'graph', False)
        dataset = client.datasets.get(args.dataset_id, include_metadata=include_metadata,
                                      include_links=graph or _config.include_links,
                                      include_owner=True)
        if dataset is None:
            logger.error(f"Dataset not found: {args.dataset_id}")
            sys.exit(1)
        from .helpers import cache_resource
        cache_resource(getattr(args, '_shell_state', None), client, dataset, 'dataset',
                       args.dataset_id, verbose=getattr(args, 'verbose', False),
                       graph=getattr(args, 'graph', False), include_metadata=include_metadata)
        if as_json:
            print(json.dumps(dataset, indent=2, default=str))
        else:
            _show_dataset(dataset, client,
                          verbose=getattr(args, 'verbose', False),
                          graph=graph,
                          include_metadata=include_metadata)
    except Exception as e:
        from .helpers import fail
        fail("retrieving dataset", e, args)


def _execute_create(args):
    """Execute the 'dataset create' subcommand."""
    from crucible.parsers import get_parser, BaseParser
    from .helpers import resolve_project_context

    if not args.input:
        file_options = [
            option for option, enabled in (
                ('--type', args.dataset_type is not None),
                ('--ingestor', args.ingestor is not None),
                ('--no-upload', args.no_upload),
                ('--backend', args.backend is not None),
                ('--access-note', args.access_note is not None),
            )
            if enabled
        ]
        if file_options:
            logger.error(f"{', '.join(file_options)} require --input FILE.")
            sys.exit(1)

    project_id = args.project_id
    project_mfid = getattr(args, 'project_mfid', None)
    instrument_id = getattr(args, 'instrument_id', None)
    instrument_mfid = getattr(args, 'instrument_mfid', None)
    if project_id is None and project_mfid is None:
        project_id, project_source = resolve_project_context(args)
    else:
        project_source = 'argument'
    if project_id is None and project_mfid is None:
        logger.error("Project required. Specify --project-id or --project-mfid, or set the current project.")
        sys.exit(1)

    # Expand wildcards in input files
    import glob
    expanded_files = []
    for pattern in args.input or []:
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

    if args.no_upload and args.dataset_type is not None:
        logger.error("--no-upload is only supported for generic uploads (omit -t/--type).")
        sys.exit(1)

    parser = None
    if input_files:
        if args.dataset_type is None:
            from crucible.parsers import get_all_parsers
            all_parsers = get_all_parsers()
            non_base = sorted(k for k in all_parsers if k != 'base')
            if non_base:
                logger.info("Tip: No parser type specified (-t). Using generic upload (BaseParser).")
                logger.info(f"     Available parsers: {', '.join(non_base)}")
                logger.info("     Run 'crucible dataset parsers' to see all options.\n")
            ParserClass = BaseParser
        else:
            try:
                ParserClass = get_parser(args.dataset_type)
            except ValueError as e:
                logger.error(f"Error: {e}")
                sys.exit(1)

        try:
            parser = ParserClass(
                files_to_upload=[str(f) for f in input_files],
                project_id=project_id,
                project_mfid=project_mfid,
                metadata=metadata_dict,
                keywords=keywords_list,
                mfid=dataset_mfid,
                measurement=args.measurement,
                dataset_name=args.dataset_name,
                session_name=args.session_name,
                public=args.public,
                instrument_name=args.instrument_name,
                instrument_id=instrument_id,
                instrument_mfid=instrument_mfid,
                data_format=args.data_format,
                data_type=args.data_type,
                timestamp=timestamp,
            )
        except Exception as e:
            from .helpers import fail
            fail("parsing file", e, args)

        if args.ingestor is not None and args.measurement is None:
            parser.measurement = None

        dataset_record = parser.to_dataset()
        record_metadata = parser.scientific_metadata
        record_keywords = parser.keywords
    else:
        from crucible.models import Dataset
        dataset_record = Dataset(
            unique_id=dataset_mfid,
            measurement=args.measurement,
            project_id=project_id,
            project_mfid=project_mfid,
            dataset_name=args.dataset_name,
            session_name=args.session_name,
            timestamp=timestamp,
            public=args.public,
            instrument_name=args.instrument_name,
            instrument_id=instrument_id,
            instrument_mfid=instrument_mfid,
            data_format=args.data_format,
            data_type=args.data_type,
        )
        record_metadata = metadata_dict or {}
        record_keywords = keywords_list or []

    # Display dataset information
    _p = term.field_printer(14)

    term.header("Dataset")
    project_context = {
        'environment': 'from environment',
        'config file': 'current project',
    }.get(project_source)
    project_selector = project_id or project_mfid
    proj_label = f"{project_selector} {term.dim(f'({project_context})')}" if project_context else project_selector
    _p("Project",     proj_label)
    if parser is not None:
        _p("Parser", ParserClass.__name__)
    _p("Name",        dataset_record.dataset_name)
    _p("Measurement", dataset_record.measurement or term.dim("(server assigns)"))
    _p("Data format", dataset_record.data_format)
    _p("Data type",   dataset_record.data_type)
    _p("Session",     dataset_record.session_name)
    _p("Timestamp",   dataset_record.timestamp)
    _p("Public",      term.fmt_bool(dataset_record.public))
    _p("Instrument",  dataset_record.instrument_id or dataset_record.instrument_mfid or dataset_record.instrument_name)
    _p("MFID",        dataset_mfid or term.dim("(server assigns)"))
    if input_files and args.no_upload:
        _p("Backend", args.backend or 'local')
        if args.access_note:
            _p("Access note", args.access_note)
    elif input_files:
        _p("Ingestor", args.ingestor or term.dim("(server detects)"))

    if parser is not None and parser.files_to_upload:
        label = 'Files (cataloged, not uploaded)' if args.no_upload else 'Files'
        print(f"\n  {term.dim(f'{label} ({len(parser.files_to_upload)})')}")
        for f in parser.files_to_upload:
            print(f"    {Path(f).name}")

    if record_keywords:
        print(f"\n  {term.dim(f'Keywords ({len(record_keywords)})')}")
        print(f"    {', '.join(record_keywords)}")

    if record_metadata:
        print(f"\n  {term.dim(f'Scientific Metadata ({len(record_metadata)} fields)')}")
        for key, value in record_metadata.items():
            if key == 'dump_files':
                print(f"    {key}: {len(value)} files")
            elif isinstance(value, (list, dict)) and len(str(value)) > 80:
                print(f"    {key}: <{type(value).__name__}, {len(value)} items>")
            else:
                print(f"    {key}: {value}")

    # Upload or dry run
    if args.dry_run:
        print("")
        logger.info("Dry run - dataset not created. Remove --dry-run to create it.")
    else:
        print("")
        try:
            if args.no_upload:
                from crucible.client import CrucibleClient
                from crucible.models import AssociatedFile
                remote_files = [
                    AssociatedFile(
                        filename=Path(f).name,
                        storage_path=str(Path(f).resolve()),
                        storage_backend=args.backend or 'local',
                        access_note=args.access_note,
                    )
                    for f in parser.files_to_upload
                ]
                result = CrucibleClient().datasets.create(
                    parser.to_dataset(),
                    scientific_metadata=parser.scientific_metadata,
                    keywords=parser.keywords,
                    files=remote_files,
                )
            else:
                if parser is None:
                    from crucible.client import CrucibleClient
                    result = CrucibleClient().datasets.create(
                        dataset_record,
                        scientific_metadata=record_metadata,
                        keywords=record_keywords,
                        files=[],
                    )
                else:
                    result = parser.upload_dataset(
                        ingestor=args.ingestor,
                        verbose=getattr(args, 'debug', False),
                        wait_for_ingestion_response=True
                    )

            term.success("Dataset created" if parser is None else "Upload completed", args)
            created = result.get('created_record', {}) if result else {}
            if created:
                from crucible.client import CrucibleClient
                _show_dataset(created, CrucibleClient())

            if result and getattr(args, 'debug', False):
                logger.debug("Upload result details:")
                for key, value in result.items():
                    logger.debug(f"  {key}: {value}")

        except Exception as e:
            from .helpers import fail
            fail("uploading dataset", e, args)


def _execute_link(args):
    """Execute the 'dataset link' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.datasets.link(
            args.parent, args.child, args.relationship_type)


        suffix = f" ({args.relationship_type})" if args.relationship_type else ""
        term.success(
            f"Linked dataset {args.child} as child of {args.parent}{suffix}", args)

    except Exception as e:
        from .helpers import fail
        fail("linking datasets", e, args)


def _execute_list_parents(args):
    """Execute the 'dataset list-parents' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        parents = sorted(client.datasets.list_parents(
            args.dataset_id, limit=args.limit,
            relationship_type=args.relationship_type),
                         key=lambda ds: (ds.get('dataset_name') or '').lower())

        term.header(f"Parent Datasets · {args.dataset_id} ({len(parents)})")
        if not parents:
            print(f"  {term.dim('No parent datasets found.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)',
                 term.cyan(ds.get('unique_id')) if ds.get('unique_id') else '-',
                 ds.get('measurement') or '-') for ds in parents]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])

    except Exception as e:
        from .helpers import fail
        fail("listing parent datasets", e, args)


def _execute_list_children(args):
    """Execute the 'dataset list-children' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        children = sorted(client.datasets.list_children(
            args.dataset_id, limit=args.limit,
            relationship_type=args.relationship_type),
                          key=lambda ds: (ds.get('dataset_name') or '').lower())

        term.header(f"Child Datasets · {args.dataset_id} ({len(children)})")
        if not children:
            print(f"  {term.dim('No child datasets found.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)',
                 term.cyan(ds.get('unique_id')) if ds.get('unique_id') else '-',
                 ds.get('measurement') or '-') for ds in children]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])

    except Exception as e:
        from .helpers import fail
        fail("listing child datasets", e, args)


def _execute_list_samples(args):
    """Execute the 'dataset list-samples' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        samples = sorted(client.samples.list(dataset_mfid=args.dataset_id, limit=args.limit),
                         key=lambda s: (s.get('sample_name') or '').lower())

        term.header(f"Samples · {args.dataset_id} ({len(samples)})")
        if not samples:
            print(f"  {term.dim('No samples linked.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)',
                 term.cyan(s.get('unique_id')) if s.get('unique_id') else '-',
                 s.get('sample_type') or '-') for s in samples]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])

    except Exception as e:
        from .helpers import fail
        fail("listing samples", e, args)


def _execute_parsers(args):
    """Execute the 'dataset parsers' subcommand."""
    from crucible.parsers import PARSER_REGISTRY, get_all_parsers
    all_parsers = get_all_parsers()
    builtin_names = set(PARSER_REGISTRY.keys())

    term.header(f"Dataset Parsers ({len(all_parsers)})")
    if getattr(args, 'verbose', False):
        rows = [
            (
                name,
                "built-in" if name in builtin_names else "installed",
                getattr(cls, '_measurement', '-') or '-',
                getattr(cls, '_data_format', None) or '-',
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
                getattr(cls, '_measurement', '-') or '-',
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
        formatter_class=term.ColorHelpFormatter,
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
