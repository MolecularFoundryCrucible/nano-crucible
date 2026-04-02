#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared CLI helper utilities.

Functions here are used across multiple CLI modules (dataset, sample, get, …)
and don't belong in term.py (display-only) or shell.py (would create circular
imports since shell imports from dataset/sample).
"""


def cache_resource(shell_state, client, data, rtype, resource_id, **flags):
    """Cache a fetched resource in the shell state and start a graph prefetch.

    The graph is fetched in a background thread so Alt+G / Alt+V in the
    interactive shell can re-render without an extra API call.

    Args:
        shell_state: The shell's mutable state dict (args._shell_state), or
                     None when running outside the interactive shell.
        client:      CrucibleClient instance (used for the graph prefetch).
        data:        The fetched resource dict.
        rtype:       Resource type string — 'dataset' or 'sample'.
        resource_id: MFID of the resource (used for the graph API call).
        **flags:     Additional keys stored in last_resource (verbose, graph,
                     include_metadata, …).
    """
    if shell_state is None:
        return
    from concurrent.futures import ThreadPoolExecutor
    pool   = ThreadPoolExecutor(max_workers=1, thread_name_prefix='graph-prefetch')
    future = pool.submit(client.graphs.get, resource_id, recursive=True)
    pool.shutdown(wait=False)
    shell_state['last_resource'] = {
        'data': data, 'type': rtype, '_graph_future': future, **flags
    }
