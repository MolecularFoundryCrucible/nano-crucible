#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample subcommand for Crucible CLI.

Provides sample-related operations: list, get, create, link, etc.
"""

import argparse
import sys
import json
import logging

logger = logging.getLogger(__name__)

from . import term

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

from ..config import config as _config
from ..constants import PROJECT_SCOPES


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
    _register_search(sample_subparsers)
    _register_search_metadata(sample_subparsers)
    _register_get(sample_subparsers)
    _register_create(sample_subparsers)
    _register_update(sample_subparsers)
    _register_edit(sample_subparsers)
    _register_reassign_project(sample_subparsers)
    _register_transfer_ownership(sample_subparsers)
    _register_link(sample_subparsers)
    _register_list_parents(sample_subparsers)
    _register_list_children(sample_subparsers)
    _register_list_datasets(sample_subparsers)
    _register_add_dataset(sample_subparsers)
    _register_remove_dataset(sample_subparsers)
    _register_remove_child(sample_subparsers)
    from ._access import register_access_commands
    register_access_commands(sample_subparsers, 'samples', id_metavar='SAMPLE_MFID')


def _register_list(subparsers):
    """Register the 'sample list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List samples',
        description='List samples, with optional filters',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample list --project-id my-project
    crucible sample list --project-id my-project --project-scope shared
    crucible sample list --project-mfid 0tkn2knjast3h0008nyq9zps2c --project-scope all
    crucible sample list --project-id my-project --type wafer
    crucible sample list --project-id my-project --group-by type
    crucible sample list --project-id my-project --include "Silicon*" "Wafer*"
    crucible sample list --project-id my-project --exclude "*test*" "*dummy*"
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
        '-n', '--name',
        default=None,
        metavar='NAME',
        help='Filter by sample name (exact match)'
    )

    parser.add_argument(
        '--type',
        default=None,
        dest='sample_type',
        metavar='TYPE',
        help='Filter by sample type (exact match, or use * / ? wildcards)'
    )

    parser.add_argument(
        '--group-by',
        dest='group_by',
        default=None,
        choices=['type', 'project'],
        metavar='FIELD',
        help='Group results by field: type, project (default from config, fallback: type)'
    )

    parser.add_argument(
        '--include',
        nargs='+',
        metavar='PATTERN',
        help='Only show samples whose name matches any glob pattern (e.g. "Silicon*", "wafer-??")'
    )

    parser.add_argument(
        '--exclude',
        nargs='+',
        metavar='PATTERN',
        help='Exclude samples whose name matches any glob pattern'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=_config.default_limit,
        metavar='N',
        help=f'Maximum number of results to return (default: {_config.default_limit})'
    )

    parser.add_argument(
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in results'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        default=False,
        help='Output as JSON array'
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
        metavar='SAMPLE_MFID',
        help='Sample MFID'
    )
    # Disable file completion for sample_id
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show all sample fields'
    )

    parser.add_argument(
        '--no-graph',
        action='store_false',
        dest='graph',
        help='Exclude linked datasets, parents, and children'
    )
    parser.set_defaults(graph=True)

    parser.add_argument(
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata in output'
    )

    parser.add_argument(
        '--json',
        dest='json',
        action='store_true',
        default=False,
        help='Output as JSON (always includes scientific metadata)'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'sample create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new sample',
        description='Create a new sample in Crucible',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    # Interactive mode (prompts for input)
    crucible sample create

    # Command-line mode
    crucible sample create -n "Silicon Wafer A" --project-id my-project
    crucible sample create -n "Sample 001" --project-id my-project --description "Test sample" --type substrate
"""
    )

    parser.add_argument(
        '-n', '--name',
        required=False,
        default=None,
        metavar='NAME',
        help='Sample name. If not provided, will prompt interactively.'
    )

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

    parser.add_argument(
        '--description',
        default=None,
        metavar='TEXT',
        help='Sample description (optional)'
    )

    parser.add_argument(
        '--type', '-t',
        dest='sample_type',
        default=None,
        metavar='TYPE',
        help='Sample type/category (optional)'
    )
    parser.add_argument(
        '--sample-type',
        action=DeprecatedAliasAction,
        deprecated_options={'--sample-type'},
        replacement='--type',
        dest='sample_type',
        default=argparse.SUPPRESS,
        metavar='TYPE',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '--timestamp',
        dest='timestamp',
        default=None,
        metavar='DATE',
        help="User-defined timestamp (flexible: 'today', '2024-01-15', '2024-01-15 10:30', ISO 8601, etc.)"
    )

    parser.add_argument(
        '--public',
        action='store_true',
        default=False,
        help='Make sample publicly visible (default: private)'
    )

    parser.add_argument(
        '--metadata',
        dest='metadata',
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
    )

    parser.set_defaults(func=_execute_create)


def _sample_updatable_fields():
    """Return ordered list of fields that can be updated on a sample."""
    from .schema import SAMPLE_FIELDS, editable_keys
    return editable_keys(SAMPLE_FIELDS)


def _register_update(subparsers):
    """Register the 'sample update' subcommand."""
    fields = _sample_updatable_fields()
    parser = subparsers.add_parser(
        'update',
        help='Update sample fields or scientific metadata',
        description='Update fields or scientific metadata of an existing sample',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample update SAMPLE_MFID --name "Silicon Wafer B"
    crucible sample update SAMPLE_MFID --description "Annealed at 900C" --type substrate
    crucible sample update SAMPLE_MFID --metadata '{"thickness_nm": 50}'
    crucible sample update SAMPLE_MFID --metadata metadata.json --overwrite
    crucible sample update SAMPLE_MFID --set session_name=run42

Use `sample set-public` or `sample set-private` to change public visibility.
Use `sample reassign-project` or `sample transfer-ownership` to change project or owner.
"""
    )

    sample_id_arg = parser.add_argument(
        'sample_id',
        metavar='SAMPLE_MFID',
        help='Sample MFID'
    )
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument('-n', '--name',        dest='sample_name',  metavar='NAME',    default=None, help='Sample name')
    parser.add_argument('-t', '--type',        dest='sample_type',  metavar='TYPE',    default=None, help='Sample type')
    parser.add_argument('--description',       dest='description',  metavar='TEXT',    default=None, help='Sample description')
    parser.add_argument('--timestamp',         dest='timestamp',    metavar='DATE',    default=None, help='User-defined timestamp')

    parser.add_argument(
        '--set', '-s',
        action='append',
        dest='set_fields',
        metavar='KEY=VALUE',
        help='Set any sample field by name (repeatable, for fields without a dedicated flag)'
    )

    parser.add_argument(
        '--metadata',
        default=None,
        metavar='JSON',
        help='Scientific metadata as JSON string or path to JSON file'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Replace all existing scientific metadata instead of merging (only with --metadata)'
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--public', dest='public', action='store_true', default=None, help=argparse.SUPPRESS)
    group.add_argument('--no-public', dest='public', action='store_false', help=argparse.SUPPRESS)

    parser.set_defaults(func=_execute_update, public=None)


def _execute_update(args):
    """Execute the 'sample update' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import cast_value

    has_set      = bool(getattr(args, 'set_fields', None))
    has_metadata = bool(getattr(args, 'metadata', None))
    has_public   = getattr(args, 'public', None) is not None

    if has_public:
        warning = term.yellow('Warning:', stream=sys.stderr)
        replacement = 'set-public' if args.public else 'set-private'
        option = '--public' if args.public else '--no-public'
        print(
            f"{warning} {option} is deprecated; use sample {replacement} instead.",
            file=sys.stderr,
        )

    named = {k: getattr(args, k) for k in
             ('sample_name', 'sample_type', 'description', 'timestamp')
             if getattr(args, k, None) is not None}

    if not has_set and not has_metadata and not has_public and not named:
        logger.error("Error: provide at least one field to update")
        sys.exit(1)

    updates = {}
    if has_set:
        valid_fields = set(_sample_updatable_fields())
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

        updates.update(named)

        if updates:
            client.samples.update(args.sample_id, **updates)
            term.success(f"Sample {args.sample_id} fields updated", args)

        if has_public:
            operation = client.samples.set_public if args.public else client.samples.set_private
            operation(args.sample_id)
            visibility = 'publicly viewable' if args.public else 'private'
            term.success(f"Sample {args.sample_id} is now {visibility}", args)

        if metadata_dict is not None:
            overwrite = getattr(args, 'overwrite', False)
            client.samples.update_scientific_metadata(args.sample_id, metadata_dict, overwrite=overwrite)
            action = "replaced" if overwrite else "updated"
            term.success(f"Scientific metadata {action} for sample {args.sample_id}", args)

    except Exception as e:
        from .helpers import fail
        fail("updating sample", e, args)


def _register_reassign_project(subparsers):
    """Register the 'sample reassign-project' subcommand."""
    parser = subparsers.add_parser(
        'reassign-project',
        help='Move a sample to a different project',
        description='Preview or execute a project reassignment (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample reassign-project SAMPLE_MFID new-project
    crucible sample reassign-project SAMPLE_MFID new-project --confirm
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('project_id', metavar='PROJECT_ID', help='Target project ID')
    parser.add_argument('--confirm', action='store_true', help='Execute the move (default: preview only)')
    parser.set_defaults(func=_execute_reassign_project)


def _execute_reassign_project(args):
    """Execute the 'sample reassign-project' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_reassign_project

    try:
        client = CrucibleClient()
        result = client.samples.reassign_project(args.sample_id, args.project_id, confirm=args.confirm)
        show_reassign_project(result, args.confirm)
    except Exception as e:
        fail("reassigning sample project", e, args)


def _register_transfer_ownership(subparsers):
    """Register the 'sample transfer-ownership' subcommand."""
    parser = subparsers.add_parser(
        'transfer-ownership',
        help='Transfer ownership of a sample',
        description='Preview or execute an ownership transfer (requires --confirm to execute)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample transfer-ownership SAMPLE_MFID newowner@example.com
    crucible sample transfer-ownership SAMPLE_MFID newowner@example.com --confirm
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('new_owner', metavar='NEW_OWNER', help='ORCID, MFID, username, or email of the new owner')
    parser.add_argument('--confirm', action='store_true', help='Execute the transfer (default: preview only)')
    parser.set_defaults(func=_execute_transfer_ownership)


def _execute_transfer_ownership(args):
    """Execute the 'sample transfer-ownership' subcommand."""
    from crucible.client import CrucibleClient
    from .helpers import fail, show_transfer_ownership

    try:
        client = CrucibleClient()
        result = client.samples.transfer_ownership(args.sample_id, args.new_owner, confirm=args.confirm)
        show_transfer_ownership(result, args.confirm)
    except Exception as e:
        fail("transferring sample ownership", e, args)


def _register_edit(subparsers):
    """Register the 'sample edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit sample fields interactively',
        description='Open sample fields in $EDITOR and update on save',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample edit SAMPLE_MFID
    EDITOR=vim crucible sample edit SAMPLE_MFID
"""
    )
    sample_id_arg = parser.add_argument(
        'sample_id',
        metavar='SAMPLE_MFID',
        help='Sample MFID'
    )
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.set_defaults(func=_execute_edit)


def _edit_sample(sid, client, debug=False):
    """Core edit logic for a sample — shared with the top-level 'crucible edit' command."""
    sample = client.samples.get(sid, include_metadata=True, include_datasets=False)
    if sample is None:
        logger.error(f"Sample not found: {sid}")
        sys.exit(1)

    from .schema import SAMPLE_FIELDS, ordered_dict
    valid_fields = set(_sample_updatable_fields())
    original_fields = ordered_dict(SAMPLE_FIELDS, sample, verbose=True, editable_only=True)
    original_meta = sample.get('scientific_metadata') or {}

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

    field_changes = {k: v for k, v in edited.items() if k in valid_fields and v != original_fields.get(k)}
    edited_meta = edited.get('scientific_metadata')
    meta_changed = isinstance(edited_meta, dict) and edited_meta != original_meta

    if not field_changes and not meta_changed:
        logger.info("No changes.")
        return

    try:
        if field_changes:
            client.samples.update(sid, **field_changes)
        if meta_changed:
            client.samples.update_scientific_metadata(sid, edited_meta, overwrite=True)

        diff_updated = dict(field_changes)
        if meta_changed:
            diff_updated['scientific_metadata'] = edited_meta
        term.header("Changes")
        term.diff(original, diff_updated)
    except Exception as e:
        from .helpers import fail
        fail("updating sample", e, debug)


def _execute_edit(args):
    """Execute the 'sample edit' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
    except Exception as e:
        from .helpers import fail
        fail("connecting", e)
    _edit_sample(args.sample_id, client, debug=getattr(args, 'debug', False))


def _register_link(subparsers):
    """Register the 'sample link' subcommand."""
    from crucible.constants import RELATIONSHIP_TYPES

    parser = subparsers.add_parser(
        'link',
        help='Link parent and child samples',
        description='Create a parent-child relationship between samples'
    )

    parser.add_argument(
        '-p', '--parent',
        required=True,
        metavar='PARENT_MFID',
        help='Parent sample MFID'
    )

    parser.add_argument(
        '-c', '--child',
        required=True,
        metavar='CHILD_MFID',
        help='Child sample MFID'
    )

    parser.add_argument(
        '--relationship-type',
        choices=RELATIONSHIP_TYPES,
        metavar='TYPE',
        help=f"Kind of link, describing the child relative to the parent "
             f"({', '.join(RELATIONSHIP_TYPES)}). Omit to leave it unspecified."
    )

    parser.set_defaults(func=_execute_link)


def _register_add_dataset(subparsers):
    """Register the 'sample add-dataset' subcommand."""
    parser = subparsers.add_parser(
        'add-dataset',
        help='Link a sample to a dataset',
        description='Associate a dataset with a sample',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample add-dataset SAMPLE_MFID --dataset DATASET_MFID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('-d', '--dataset', required=True, metavar='DATASET_MFID', help='Dataset MFID')
    parser.set_defaults(func=_execute_link_dataset)


def _register_list_parents(subparsers):
    """Register the 'sample list-parents' subcommand."""
    parser = subparsers.add_parser(
        'list-parents',
        help='List parent samples',
        description='List parent samples of a given sample',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample list-parents SAMPLE_MFID
    crucible sample list-parents SAMPLE_MFID --relationship-type is_part_of
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    from .helpers import add_relationship_type_filter
    add_relationship_type_filter(parser)
    parser.set_defaults(func=_execute_list_parents)


def _register_list_children(subparsers):
    """Register the 'sample list-children' subcommand."""
    parser = subparsers.add_parser(
        'list-children',
        help='List child samples',
        description='List child samples derived from a given sample',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample list-children SAMPLE_MFID
    crucible sample list-children SAMPLE_MFID --relationship-type is_derived_from
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    from .helpers import add_relationship_type_filter
    add_relationship_type_filter(parser)
    parser.set_defaults(func=_execute_list_children)


def _register_list_datasets(subparsers):
    """Register the 'sample list-datasets' subcommand."""
    parser = subparsers.add_parser(
        'list-datasets',
        help='List datasets linked to a sample',
        description='Show all datasets associated with a given sample',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample list-datasets SAMPLE_MFID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('--limit', type=int, default=_config.default_limit, metavar='N',
                        help=f'Maximum number of results (default: {_config.default_limit})')
    parser.set_defaults(func=_execute_list_datasets)


def _execute_list(args):
    """Execute the 'sample list' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    from .helpers import resolve_project_context
    project_id = args.project_id
    project_mfid = getattr(args, 'project_mfid', None)
    project_scope = getattr(args, 'project_scope', None)
    if project_id is not None and project_mfid is not None:
        logger.error("Error: Specify either --project-id or --project-mfid, not both.")
        sys.exit(1)
    if project_id is None and project_mfid is None:
        project_id, _ = resolve_project_context(args)
    if project_id is None and project_mfid is None:
        logger.error("Error: Project ID or project MFID required. Specify --project-id, --project-mfid, or set current_project in config.")
        sys.exit(1)

    filters = {}
    if args.name:
        filters['sample_name'] = args.name
    type_pattern = args.sample_type or None
    if type_pattern and not any(c in type_pattern for c in ('*', '?', '[')):
        filters['sample_type'] = type_pattern
        type_pattern = None  # exact match handled by API; no client-side filter needed
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
        samples = client.samples.list(limit=args.limit, **project_filters,
                                         include_metadata=getattr(args, 'include_metadata', False) or _config.include_metadata,
                                         **filters)

        # Client-side wildcard filtering on type
        if type_pattern:
            samples = [s for s in samples if fnmatch.fnmatch(
                (s.get('sample_type') or '').lower(), type_pattern.lower()
            )]

        # Client-side glob filtering on name
        if getattr(args, 'include', None):
            samples = [s for s in samples if any(
                fnmatch.fnmatch((s.get('sample_name') or '').lower(), p.lower())
                for p in args.include
            )]
        if getattr(args, 'exclude', None):
            samples = [s for s in samples if not any(
                fnmatch.fnmatch((s.get('sample_name') or '').lower(), p.lower())
                for p in args.exclude
            )]

        if getattr(args, 'json', False):
            import json
            print(json.dumps(samples, indent=2, default=str))
            return

        project_label = project_id or project_mfid
        scope_label = f" · {project_scope}" if project_scope else ''
        title = f"Samples · {project_label}{scope_label} ({len(samples)})" if project_label else f"Samples ({len(samples)})"
        term.header(title)
        if filters:
            logger.info(f"Filters: {', '.join(f'{k}={v}' for k, v in filters.items())}")

        if not samples:
            print(f"  {term.dim('No samples found.')}")
        else:
            from .helpers import explorer_url, project_reference

            _GROUP_FIELD = {'type': 'sample_type', 'project': 'project_id'}
            group_by_key = args.group_by or config.sample_group_by or 'type'
            group_by = _GROUP_FIELD.get(group_by_key)

            def _make_row(s):
                uid = s.get('unique_id') or ''
                _, referenced_project_id, _ = project_reference(s)
                pid = referenced_project_id or project_id
                row = (
                    s.get('sample_name') or '(unnamed)',
                    term.mfid_link(uid, explorer_url(uid, pid, 'sample')) if uid else '-',
                )
                if project_scope in ('shared', 'all'):
                    row += (
                        referenced_project_id or '-',
                        s.get('project_relation') or '-',
                    )
                return row + (s.get('sample_type') or '-',)

            contextual_headers = ['Name', 'MFID', 'Project', 'Relation', 'Type']
            standard_headers = ['Name', 'MFID', 'Type']
            headers = contextual_headers if project_scope in ('shared', 'all') else standard_headers
            contextual_max = [30, 26, 25, 8, 20]
            standard_max = [35, 26, 20]
            max_widths = contextual_max if project_scope in ('shared', 'all') else standard_max
            contextual_min = [4, 26, 7, 8, 4]
            standard_min = [4, 26, 4]
            min_widths = contextual_min if project_scope in ('shared', 'all') else standard_min

            _by_name = lambda s: (s.get('sample_name') or '').lower()

            if not group_by:
                term.table([_make_row(s) for s in sorted(samples, key=_by_name)],
                           headers, max_widths=max_widths,
                           min_widths=min_widths)
            else:
                from collections import defaultdict
                groups = defaultdict(list)
                for s in samples:
                    groups[s.get(group_by) or None].append(s)
                keys = sorted(k for k in groups if k) + ([None] if None in groups else [])
                for key in keys:
                    label = key or '(none)'
                    term.subheader(f"{label} ({len(groups[key])})")
                    term.table([_make_row(s) for s in sorted(groups[key], key=_by_name)],
                               headers, max_widths=max_widths,
                               min_widths=min_widths)

    except Exception as e:
        from .helpers import fail
        fail("listing samples", e, args)


def _show_sample(sample, client, verbose=False, graph=False, include_metadata=False, links=None):
    """Display sample fields. Extracted for reuse by top-level 'crucible get'."""
    _p = term.field_printer(14)

    from .helpers import explorer_url, format_relationship_type, project_reference

    def _s_link(r):
        u = r.get('unique_id')
        _, p, _ = project_reference(r)
        return term.mfid_link(u, explorer_url(u, p, 'sample'))

    term.header("Sample")

    dr = sample.get('deletion_request')
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

    project_title, project_id, project_url = project_reference(sample)
    _p("Name",        term.bold(sample.get('sample_name') or '(unnamed)'))
    _p("MFID",        _s_link(sample))
    _p("Type",        sample.get('sample_type'))
    _p("Description", sample.get('description'))

    if project_title or project_id:
        term.subheader("Project")
        if project_title:
            _p("Title", term.navigation_link(project_title, project_url))
        if project_id:
            _p("Project ID", project_id)

    term.subheader("Access")
    _p("Owner",  term.fmt_owner(sample))
    _p("Public", term.fmt_bool(sample.get('public')))

    timing = (
        ("Timestamp", sample.get('timestamp')),
        ("Created", sample.get('creation_time')),
        ("Modified", sample.get('modification_time')),
    )
    if any(value for _, value in timing):
        term.subheader("Timing")
        for label, value in timing:
            if value:
                _p(label, term.fmt_ts(value))

    if graph:
        sid  = sample.get('unique_id')
        _, proj, _ = project_reference(sample)
        proj = proj or ''

        links_list = links if links is not None else sample.get('links')
        if links_list is None:
            try:
                links_list = client.get_links(sid)
            except Exception:
                links_list = None
        if links_list is None:
            from .helpers import show_warning
            show_warning("Could not fetch links.")
            return

        # 'direction' is relative to this sample: links are stored
        # parent -> child, so a 'source' is one of its parents.
        linked_datasets = [l for l in links_list if l.get('direction') == 'undirected'
                           and l.get('resource_type') == 'dataset']
        parent_samples  = [l for l in links_list if l.get('direction') == 'source'
                           and l.get('resource_type') == 'sample']
        child_samples   = [l for l in links_list if l.get('direction') == 'target'
                           and l.get('resource_type') == 'sample']

        term.subheader(f"Linked Datasets ({len(linked_datasets)})")
        for ds in linked_datasets:
            uid = ds['unique_id']
            print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'dataset'))}  {ds.get('name') or '(unnamed)'}")
        if not linked_datasets:
            print(f"  {term.dim('(none)')}")

        term.subheader(f"Parents ({len(parent_samples)})")
        for p in parent_samples:
            uid = p['unique_id']
            print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'sample'))}  "
                  f"{p.get('name') or '(unnamed)'}  {format_relationship_type(p)}")
        if not parent_samples:
            print(f"  {term.dim('(none)')}")

        term.subheader(f"Children ({len(child_samples)})")
        for c in child_samples:
            uid = c['unique_id']
            print(f"  {term.mfid_link(uid, explorer_url(uid, proj, 'sample'))}  "
                  f"{c.get('name') or '(unnamed)'}  {format_relationship_type(c)}")
        if not child_samples:
            print(f"  {term.dim('(none)')}")

    if include_metadata:
        from .helpers import show_scientific_metadata
        show_scientific_metadata(sample.get('scientific_metadata'))


def _execute_get(args):
    """Execute the 'sample get' subcommand."""
    import json
    from crucible.client import CrucibleClient
    as_json = getattr(args, 'json', False)
    include_metadata = as_json or getattr(args, 'include_metadata', False) or _config.include_metadata
    try:
        graph  = getattr(args, 'graph', False)
        client = CrucibleClient()
        sample = client.samples.get(args.sample_id, include_links=graph or _config.include_links,
                                    include_metadata=include_metadata, include_owner=True,
                                    include_datasets=as_json)
        if sample is None:
            logger.error(f"Sample not found: {args.sample_id}")
            sys.exit(1)
        from .helpers import cache_resource
        cache_resource(getattr(args, '_shell_state', None), client, sample, 'sample',
                       args.sample_id, verbose=getattr(args, 'verbose', False),
                       graph=graph, include_metadata=include_metadata)
        if as_json:
            print(json.dumps(sample, indent=2, default=str))
        else:
            _show_sample(sample, client,
                         verbose=getattr(args, 'verbose', False),
                         graph=graph,
                         include_metadata=include_metadata)
    except Exception as e:
        from .helpers import fail
        fail("retrieving sample", e, args)


def _execute_create(args):
    """Execute the 'sample create' subcommand."""
    from crucible.client import CrucibleClient

    from ..utils import parse_timestamp
    from ..utils.identifiers import IdentifierNotFoundError, validate_slug
    from .helpers import fail, prompt_optional, prompt_required, resolve_project_context

    name        = args.name
    project_id  = args.project_id
    project_mfid = getattr(args, 'project_mfid', None)
    if project_id is None and project_mfid is None:
        default_project, _ = resolve_project_context(args)
        if default_project:
            project_id = default_project
    else:
        default_project = None
    description = args.description
    sample_type = args.sample_type
    timestamp   = None
    if args.timestamp:
        try:
            timestamp = parse_timestamp(args.timestamp)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    interactive = name is None or (project_id is None and project_mfid is None)
    if interactive:
        term.header("Create Sample")
        print("")

    try:
        client = CrucibleClient()
    except Exception as e:
        fail("connecting", e)

    def validate_project_id(value):
        value = validate_slug(value, 'project')
        try:
            project = client.projects.get(value)
        except IdentifierNotFoundError as error:
            raise ValueError(f"Project '{value}' was not found.") from error
        return project.get('project_id') or value

    if name is None:
        name = prompt_required("Sample name", option='--name')

    if project_id is None and project_mfid is None:
        if default_project:
            project_id = prompt_optional(
                "Project ID",
                default=default_project,
                validator=validate_project_id,
                option='--project-id',
            )
        else:
            project_id = prompt_required(
                "Project ID",
                validator=validate_project_id,
                option='--project-id',
            )
    elif project_id is not None and interactive:
        try:
            project_id = validate_project_id(project_id)
        except Exception as e:
            fail("validating sample project", e, args)

    if interactive:
        if sample_type is None:
            sample_type = prompt_optional("Sample type")

        if description is None:
            description = prompt_optional("Description")

        if timestamp is None:
            timestamp = prompt_optional(
                "Timestamp",
                validator=parse_timestamp,
                hint="today or YYYY-MM-DD HH:MM",
            )

    metadata_dict = None
    if getattr(args, 'metadata', None):
        from .helpers import load_metadata
        try:
            metadata_dict = load_metadata(args.metadata)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    try:
        from crucible.models import Sample
        result = client.samples.create(
            Sample(
                sample_name=name,
                project_id=project_id,
                project_mfid=project_mfid,
                description=description,
                sample_type=sample_type,
                timestamp=timestamp,
                public=True if args.public else None,
            ),
            scientific_metadata=metadata_dict,
        )

        term.success("Sample created", args)
        _show_sample(result, client)

    except Exception as e:
        from .helpers import fail
        fail("creating sample", e, args)


def _execute_link(args):
    """Execute the 'sample link' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.samples.link(args.parent, args.child, args.relationship_type)

        suffix = f" ({args.relationship_type})" if args.relationship_type else ""
        term.success(
            f"Linked sample {args.child} as child of {args.parent}{suffix}", args)

    except Exception as e:
        from .helpers import fail
        fail("linking samples", e, args)


def _execute_list_parents(args):
    """Execute the 'sample list-parents' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        parents = sorted(client.samples.list_parents(
            args.sample_id, limit=args.limit,
            relationship_type=args.relationship_type),
                         key=lambda s: (s.get('sample_name') or '').lower())
        term.header(f"Parent Samples · {args.sample_id} ({len(parents)})")
        if not parents:
            print(f"  {term.dim('No parent samples found.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)',
                 term.cyan(s.get('unique_id')) if s.get('unique_id') else '-',
                 s.get('sample_type') or '-') for s in parents]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])
    except Exception as e:
        from .helpers import fail
        fail("listing parent samples", e, args)


def _execute_list_children(args):
    """Execute the 'sample list-children' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        children = sorted(client.samples.list_children(
            args.sample_id, limit=args.limit,
            relationship_type=args.relationship_type),
                          key=lambda s: (s.get('sample_name') or '').lower())
        term.header(f"Child Samples · {args.sample_id} ({len(children)})")
        if not children:
            print(f"  {term.dim('No child samples found.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)',
                 term.cyan(s.get('unique_id')) if s.get('unique_id') else '-',
                 s.get('sample_type') or '-') for s in children]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])
    except Exception as e:
        from .helpers import fail
        fail("listing child samples", e, args)


def _execute_list_datasets(args):
    """Execute the 'sample list-datasets' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        datasets = sorted(client.datasets.list(sample_mfid=args.sample_id, limit=args.limit),
                          key=lambda ds: (ds.get('dataset_name') or '').lower())
        term.header(f"Datasets · {args.sample_id} ({len(datasets)})")
        if not datasets:
            print(f"  {term.dim('No datasets linked.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)',
                 term.cyan(ds.get('unique_id')) if ds.get('unique_id') else '-',
                 ds.get('measurement') or '-') for ds in datasets]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])
    except Exception as e:
        from .helpers import fail
        fail("listing datasets", e, args)


def _execute_link_dataset(args):
    """Execute the 'sample add-dataset' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        sample_id = args.sample_id
        client.samples.link_dataset(sample_id, args.dataset)

        term.success(f"Linked sample {sample_id} to dataset {args.dataset}", args)

    except Exception as e:
        from .helpers import fail
        fail("linking dataset to sample", e, args)


def _register_remove_child(subparsers):
    """Register the 'sample remove-child' subcommand."""
    parser = subparsers.add_parser(
        'remove-child',
        help='Unlink a child sample from a parent sample',
        description='Remove the parent-child relationship between two samples (requires admin)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample remove-child PARENT_MFID --child CHILD_MFID
"""
    )
    parser.add_argument('parent_id', metavar='PARENT_MFID', help='Parent sample MFID')
    parser.add_argument('-c', '--child', required=True, metavar='CHILD_MFID', help='Child sample MFID to unlink')
    parser.set_defaults(func=_execute_remove_child)


def _execute_remove_child(args):
    """Execute the 'sample remove-child' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.samples.unlink(args.parent_id, args.child)
        term.success(f"Unlinked child sample {args.child} from parent sample {args.parent_id}", args)
    except Exception as e:
        from .helpers import fail
        fail("unlinking child sample", e, args)


def _register_remove_dataset(subparsers):
    """Register the 'sample remove-dataset' subcommand."""
    parser = subparsers.add_parser(
        'remove-dataset',
        help='Unlink a dataset from a sample',
        description='Remove the association between a sample and a dataset (requires admin)',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample remove-dataset SAMPLE_MFID --dataset DATASET_MFID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_MFID', help='Sample MFID')
    parser.add_argument('-d', '--dataset', required=True, metavar='DATASET_MFID', help='Dataset MFID to unlink')
    parser.set_defaults(func=_execute_remove_dataset)


def _execute_remove_dataset(args):
    """Execute the 'sample remove-dataset' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.samples.unlink_dataset(args.sample_id, args.dataset)
        term.success(f"Unlinked sample {args.sample_id} from dataset {args.dataset}", args)
    except Exception as e:
        from .helpers import fail
        fail("unlinking dataset from sample", e, args)


def _register_search(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Fuzzy search samples by name',
        description='Fuzzy name search across samples you can read. '
                    'For scientific metadata search use search-metadata.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible sample search silicon
    crucible sample search "wafer" --project-id my-project
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
        fail("searching samples", ValueError("Search term must be at least 3 characters."), args)
    from crucible.client import CrucibleClient
    try:
        from .helpers import resolve_project_context
        client     = CrucibleClient()
        project_id, _ = resolve_project_context(args, args.project_id)
        results    = client.samples.search(args.query, project_id=project_id,
                                           limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Samples matching '{args.query}' ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        from .helpers import explorer_url, project_reference
        rows = []
        for r in results:
            uid = r.get('unique_id') or ''
            _, referenced_project_id, _ = project_reference(r)
            pid = referenced_project_id or project_id or ''
            rows.append((
                r.get('sample_name') or '(unnamed)',
                term.mfid_link(uid, explorer_url(uid, pid, 'sample')),
                r.get('sample_type') or '-',
            ))
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


def _register_search_metadata(subparsers):
    for name in ('search-metadata', 'search-md'):
        parser = subparsers.add_parser(
            name,
            help='Search samples by scientific metadata' if name == 'search-metadata' else None,
            description='Full-text search across scientific metadata of all accessible samples.',
            formatter_class=term.ColorHelpFormatter,
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
        results = client.samples.search_metadata(args.query, limit=args.limit)
        if getattr(args, 'json', False):
            print(json.dumps(results, indent=2, default=str))
            return
        term.header(f"Metadata search: {args.query} ({len(results)})")
        if not results:
            print(f"  {term.dim('No results found.')}")
            return
        for r in results:
            print(f"  {term.cyan(r.get('unique_id') or r.get('sample_mfid', '-'))}")
    except Exception as e:
        from .helpers import fail
        fail("", e, args)
