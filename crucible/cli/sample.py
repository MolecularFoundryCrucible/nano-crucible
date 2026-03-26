#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample subcommand for Crucible CLI.

Provides sample-related operations: list, get, create, link, etc.
"""

import sys
import logging

logger = logging.getLogger(__name__)

from . import term

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
    _register_update(sample_subparsers)
    _register_edit(sample_subparsers)
    _register_link(sample_subparsers)
    _register_list_parents(sample_subparsers)
    _register_list_children(sample_subparsers)
    _register_list_datasets(sample_subparsers)
    _register_add_dataset(sample_subparsers)
    _register_remove_dataset(sample_subparsers)


def _register_list(subparsers):
    """Register the 'sample list' subcommand."""
    parser = subparsers.add_parser(
        'list',
        help='List samples',
        description='List samples, with optional filters',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample list -pid my-project
    crucible sample list -pid my-project -n "Silicon*"
    crucible sample list -pid my-project --type wafer
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
        help='Filter by sample type (exact match)'
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
        help='Show all sample fields'
    )

    parser.add_argument(
        '--graph',
        action='store_true',
        help='Also show linked datasets, parents, and children'
    )

    parser.set_defaults(func=_execute_get)


def _register_create(subparsers):
    """Register the 'sample create' subcommand."""
    parser = subparsers.add_parser(
        'create',
        help='Create a new sample',
        description='Create a new sample in Crucible',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
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


def _sample_updatable_fields():
    """Return sorted list of fields that can be updated on a sample (derived from Sample model)."""
    from ..models import Sample
    # Exclude server-managed / identifier fields
    _readonly = {'unique_id', 'owner_user_id', 'creation_time', 'modification_time'}
    return sorted(set(Sample.model_fields.keys()) - _readonly)


def _register_update(subparsers):
    """Register the 'sample update' subcommand."""
    fields = _sample_updatable_fields()
    parser = subparsers.add_parser(
        'update',
        help='Update sample fields',
        description='Update fields of an existing sample',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog=f"""
Updatable fields:
    {', '.join(fields)}

Examples:
    crucible sample update SAMPLE_ID --set sample_name="Silicon Wafer B"
    crucible sample update SAMPLE_ID --set description="Annealed at 900C"
    crucible sample update SAMPLE_ID --set sample_type=substrate --set project_id=my-project
"""
    )

    sample_id_arg = parser.add_argument(
        'sample_id',
        metavar='SAMPLE_ID',
        help='Sample unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()

    parser.add_argument(
        '--set', '-s',
        action='append',
        dest='set_fields',
        metavar='KEY=VALUE',
        required=True,
        help='Set a sample field (repeatable). Values are auto-cast to int, float, bool, or string.'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.set_defaults(func=_execute_update)


def _execute_update(args):
    """Execute the 'sample update' subcommand."""
    from crucible.client import CrucibleClient
    valid_fields = set(_sample_updatable_fields())
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
        updates[key] = value  # samples API expects strings; no cast needed

    try:
        client = CrucibleClient()
        result = client.samples.update(args.sample_id, **updates)

        logger.info(f"✓ Sample {args.sample_id} updated")
        if getattr(args, "debug", False):
            logger.debug(f"Updated fields: {list(updates.keys())}")

    except Exception as e:
        logger.error(f"Error updating sample: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_edit(subparsers):
    """Register the 'sample edit' subcommand."""
    parser = subparsers.add_parser(
        'edit',
        help='Edit sample fields interactively',
        description='Open sample fields in $EDITOR and update on save',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample edit SAMPLE_ID
    EDITOR=vim crucible sample edit SAMPLE_ID
"""
    )
    sample_id_arg = parser.add_argument(
        'sample_id',
        metavar='SAMPLE_ID',
        help='Sample unique ID'
    )
    if ARGCOMPLETE_AVAILABLE:
        sample_id_arg.completer = argcomplete.completers.SuppressCompleter()
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_edit)


def _execute_edit(args):
    """Execute the 'sample edit' subcommand."""
    from crucible.client import CrucibleClient

    try:
        client = CrucibleClient()
        sample = client.samples.get(args.sample_id)
    except Exception as e:
        logger.error(f"Error fetching sample: {e}")
        sys.exit(1)

    if sample is None:
        logger.error(f"Sample not found: {args.sample_id}")
        sys.exit(1)

    valid_fields = set(_sample_updatable_fields())
    original = {k: sample.get(k) for k in sorted(valid_fields)}

    try:
        edited = term.open_editor_json(original)
    except (RuntimeError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if edited is None:
        logger.info("No changes.")
        return

    changes = {k: v for k, v in edited.items() if k in valid_fields and v != original.get(k)}

    if not changes:
        logger.info("No changes.")
        return

    try:
        client.samples.update(args.sample_id, **changes)
        logger.info(f"✓ Sample updated")
        term.diff(original, changes)
    except Exception as e:
        logger.error(f"Error updating sample: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


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


def _register_add_dataset(subparsers):
    """Register the 'sample add-dataset' subcommand."""
    parser = subparsers.add_parser(
        'add-dataset',
        help='Link a sample to a dataset',
        description='Associate a dataset with a sample',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample add-dataset SAMPLE_ID --dataset DATASET_ID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_ID', help='Sample unique ID')
    parser.add_argument('-d', '--dataset', required=True, metavar='DATASET_ID', help='Dataset ID')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_link_dataset)


def _register_list_parents(subparsers):
    """Register the 'sample list-parents' subcommand."""
    parser = subparsers.add_parser(
        'list-parents',
        help='List parent samples',
        description='List parent samples of a given sample',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample list-parents SAMPLE_ID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_ID', help='Sample unique ID')
    parser.add_argument('--limit', type=int, default=100, metavar='N',
                        help='Maximum number of results (default: 100)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_parents)


def _register_list_children(subparsers):
    """Register the 'sample list-children' subcommand."""
    parser = subparsers.add_parser(
        'list-children',
        help='List child samples',
        description='List child samples derived from a given sample',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample list-children SAMPLE_ID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_ID', help='Sample unique ID')
    parser.add_argument('--limit', type=int, default=100, metavar='N',
                        help='Maximum number of results (default: 100)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_children)


def _register_list_datasets(subparsers):
    """Register the 'sample list-datasets' subcommand."""
    parser = subparsers.add_parser(
        'list-datasets',
        help='List datasets linked to a sample',
        description='Show all datasets associated with a given sample',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample list-datasets SAMPLE_ID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_ID', help='Sample unique ID')
    parser.add_argument('--limit', type=int, default=100, metavar='N',
                        help='Maximum number of results (default: 100)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.set_defaults(func=_execute_list_datasets)


def _execute_list(args):
    """Execute the 'sample list' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
    # Get project_id
    project_id = args.project_id
    if project_id is None:
        project_id = config.current_project
        if project_id is None:
            logger.error("Error: Project ID required. Specify with -pid or set current_project in config.")
            sys.exit(1)

    filters = {}
    if args.name:
        filters['sample_name'] = args.name
    if args.sample_type:
        filters['sample_type'] = args.sample_type

    try:
        client = CrucibleClient()
        samples = client.samples.list(project_id=project_id, limit=args.limit, **filters)

        title = f"Samples · {project_id} ({len(samples)})" if project_id else f"Samples ({len(samples)})"
        term.header(title)
        if filters:
            logger.info(f"Filters: {', '.join(f'{k}={v}' for k, v in filters.items())}")

        if not samples:
            print(f"  {term.dim('No samples found.')}")
        else:
            rows = [
                (
                    s.get('sample_name') or '(unnamed)',
                    s.get('unique_id') or '—',
                    s.get('sample_type') or '—',
                )
                for s in samples
            ]
            term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])

    except Exception as e:
        logger.error(f"Error listing samples: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _show_sample(sample, client, verbose=False, graph=False):
    """Display sample fields. Extracted for reuse by top-level 'crucible get'."""
    W = 14

    def _p(label, value):
        print(f"  {label:<{W}}{value if value not in (None, '') else '—'}")

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

    term.header("Sample")

    _p("Name",        sample.get('sample_name') or '(unnamed)')
    _p("MFID",        _s_link(sample))
    _p("Type",        sample.get('sample_type'))
    _p("Project",     sample.get('project_id'))
    _p("Timestamp",   term.fmt_ts(sample.get('timestamp')))
    _p("Description", sample.get('description'))

    if verbose or graph:
        term.subheader("Ownership")
        _p("Owner ORCID", term.orcid_link(sample.get('owner_orcid')))
        _p("Owner ID",    sample.get('owner_user_id'))

        term.subheader("Timing")
        _p("Created",  term.fmt_ts(sample.get('creation_time')))
        _p("Modified", term.fmt_ts(sample.get('modification_time')))

    if graph:
        sid = sample.get('unique_id')

        datasets = client.datasets.list(sample_id=sid)
        term.subheader(f"Linked Datasets ({len(datasets)})")
        for ds in datasets:
            name = ds.get('dataset_name') or '(unnamed)'
            meas = ds.get('measurement') or ''
            suffix = f"  {meas}" if meas else ''
            print(f"  {_ds_link(ds)}  {name}{suffix}")
        if not datasets:
            print(f"  {term.dim('(none)')}")

        parents = client.samples.list_parents(sid)
        term.subheader(f"Parents ({len(parents)})")
        for p in parents:
            print(f"  {_s_link(p)}  {p.get('sample_name') or '(unnamed)'}")
        if not parents:
            print(f"  {term.dim('(none)')}")

        children = client.samples.list_children(sid)
        term.subheader(f"Children ({len(children)})")
        for c in children:
            print(f"  {_s_link(c)}  {c.get('sample_name') or '(unnamed)'}")
        if not children:
            print(f"  {term.dim('(none)')}")


def _execute_get(args):
    """Execute the 'sample get' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        sample = client.samples.get(args.sample_id)
        if sample is None:
            logger.error(f"Sample not found: {args.sample_id}")
            sys.exit(1)
        _show_sample(sample, client,
                     verbose=getattr(args, 'verbose', False),
                     graph=getattr(args, 'graph', False))
    except Exception as e:
        logger.error(f"Error retrieving sample: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_create(args):
    """Execute the 'sample create' subcommand."""
    from crucible.config import config
    from crucible.client import CrucibleClient
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

        logger.info("✓ Sample created")
        _show_sample(result, client)

    except Exception as e:
        logger.error(f"Error creating sample: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_link(args):
    """Execute the 'sample link' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        result = client.samples.link(args.parent, args.child)

        logger.info(f"✓ Linked sample {args.child} as child of {args.parent}")

    except Exception as e:
        logger.error(f"Error linking samples: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_parents(args):
    """Execute the 'sample list-parents' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        parents = client.samples.list_parents(args.sample_id, limit=args.limit)
        term.header(f"Parent Samples · {args.sample_id} ({len(parents)})")
        if not parents:
            print(f"  {term.dim('No parent samples found.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)', s.get('unique_id') or '—',
                 s.get('sample_type') or '—') for s in parents]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])
    except Exception as e:
        logger.error(f"Error listing parent samples: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_children(args):
    """Execute the 'sample list-children' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        children = client.samples.list_children(args.sample_id, limit=args.limit)
        term.header(f"Child Samples · {args.sample_id} ({len(children)})")
        if not children:
            print(f"  {term.dim('No child samples found.')}")
            return
        rows = [(s.get('sample_name') or '(unnamed)', s.get('unique_id') or '—',
                 s.get('sample_type') or '—') for s in children]
        term.table(rows, ['Name', 'MFID', 'Type'], max_widths=[35, 26, 20])
    except Exception as e:
        logger.error(f"Error listing child samples: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_list_datasets(args):
    """Execute the 'sample list-datasets' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        datasets = client.datasets.list(sample_id=args.sample_id, limit=args.limit)
        term.header(f"Datasets · {args.sample_id} ({len(datasets)})")
        if not datasets:
            print(f"  {term.dim('No datasets linked.')}")
            return
        rows = [(ds.get('dataset_name') or '(unnamed)', ds.get('unique_id') or '—',
                 ds.get('measurement') or '—') for ds in datasets]
        term.table(rows, ['Name', 'MFID', 'Measurement'], max_widths=[35, 26, 15])
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _execute_link_dataset(args):
    """Execute the 'sample add-dataset' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        sample_id = args.sample_id
        result = client.samples.add_dataset(sample_id, args.dataset)

        logger.info(f"✓ Linked sample {sample_id} to dataset {args.dataset}")

    except Exception as e:
        logger.error(f"Error linking dataset to sample: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _register_remove_dataset(subparsers):
    """Register the 'sample remove-dataset' subcommand."""
    parser = subparsers.add_parser(
        'remove-dataset',
        help='Unlink a dataset from a sample',
        description='Remove the association between a sample and a dataset (requires admin)',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible sample remove-dataset SAMPLE_ID --dataset DATASET_ID
"""
    )
    parser.add_argument('sample_id', metavar='SAMPLE_ID', help='Sample unique ID')
    parser.add_argument('-d', '--dataset', required=True, metavar='DATASET_ID', help='Dataset ID to unlink')
    parser.set_defaults(func=_execute_remove_dataset)


def _execute_remove_dataset(args):
    """Execute the 'sample remove-dataset' subcommand."""
    from crucible.client import CrucibleClient
    try:
        client = CrucibleClient()
        client.samples.remove_dataset(args.sample_id, args.dataset)
        logger.info(f"✓ Unlinked sample {args.sample_id} from dataset {args.dataset}")
    except Exception as e:
        logger.error(f"Error unlinking dataset from sample: {e}")
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
