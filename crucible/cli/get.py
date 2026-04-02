#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Top-level get subcommand — retrieve any resource by MFID.

Automatically detects whether the ID refers to a dataset or sample
and delegates to the appropriate display function.
"""

import sys
import logging

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the top-level 'get' subcommand."""
    parser = subparsers.add_parser(
        'get',
        help='Get a resource by MFID (auto-detects type)',
        description='Retrieve a dataset or sample — resource type is detected automatically.',
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible get 0td7evvtg5wb90005k1j97ak94
    crucible get 0td7evvtg5wb90005k1j97ak94 -v
    crucible get 0td7evvtg5wb90005k1j97ak94 --graph
    crucible get 0td7evvtg5wb90005k1j97ak94 --include-metadata
"""
    )

    parser.add_argument(
        'resource_id',
        metavar='ID',
        help='Resource MFID (dataset or sample)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show all fields'
    )
    parser.add_argument(
        '--graph',
        action='store_true',
        help='Also show linked resources, parents, and children'
    )
    parser.add_argument(
        '--include-metadata',
        action='store_true',
        dest='include_metadata',
        help='Include scientific metadata (datasets only)'
    )

    parser.add_argument(
        '-o', '--output',
        dest='output',
        choices=['json'],
        default=None,
        metavar='FORMAT',
        help='Output format: json (always includes scientific metadata)'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the top-level get command."""
    import json
    from crucible.client import CrucibleClient
    output = getattr(args, 'output', None)
    verbose = getattr(args, 'verbose', False)
    graph = getattr(args, 'graph', False)
    include_metadata = output == 'json' or getattr(args, 'include_metadata', False)

    try:
        client   = CrucibleClient()
        resource = client.get(args.resource_id, include_metadata=include_metadata)
        if resource is None:
            logger.error(f"Resource not found: {args.resource_id}")
            sys.exit(1)

        resource_type = resource.get('resource_type')
        shell_state   = getattr(args, '_shell_state', None)

        if shell_state is not None:
            from concurrent.futures import ThreadPoolExecutor as _TPE
            _pool = _TPE(max_workers=1, thread_name_prefix='graph-prefetch')
            _graph_future = _pool.submit(client.graphs.get, args.resource_id, recursive=True)
            _pool.shutdown(wait=False)
            shell_state['last_resource'] = {
                'data': resource, 'type': resource_type, 'verbose': verbose,
                'graph': graph, 'include_metadata': include_metadata,
                '_graph_future': _graph_future,
            }

        if resource_type == 'dataset':
            from .dataset import _show_dataset
            if output == 'json':
                print(json.dumps(resource, indent=2, default=str))
            else:
                _show_dataset(resource, client, verbose=verbose, graph=graph,
                              include_metadata=include_metadata)

        elif resource_type == 'sample':
            from .sample import _show_sample
            if output == 'json':
                print(json.dumps(resource, indent=2, default=str))
            else:
                _show_sample(resource, client, verbose=verbose, graph=graph)

        else:
            logger.error(f"Unknown resource type '{resource_type}' for: {args.resource_id}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error retrieving {args.resource_id}: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
