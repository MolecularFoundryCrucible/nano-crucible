#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared CLI helper utilities.

Functions here are used across multiple CLI modules (dataset, sample, get,
shell, keybindings, …) and don't belong in term.py (display-only) or
shell.py (which would create circular imports).
"""


def fetch_projects(client):
    """Return [(project_id, title), ...] for all accessible projects."""
    try:
        return [(p.get('project_id', ''), p.get('title') or '-')
                for p in client.projects.list() if p.get('project_id')]
    except Exception:
        return []


def fetch_deletions(client):
    """Return pending deletion requests for autocomplete."""
    try:
        return client.deletions.list(status='pending')
    except Exception:
        return []


def fetch_user_label(client):
    """Return a display name for the authenticated user."""
    try:
        info = client.whoami()
        user = info.get('user_info', {})
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return name or info.get('access_group_name') or '?'
    except Exception:
        return '?'


def fetch_current_project():
    """Return the current project ID from config, or a placeholder."""
    try:
        from crucible.config import config
        return config.current_project or '(no project set)'
    except Exception:
        return '?'


def fetch_current_session():
    """Return the current session name from config, or empty string."""
    try:
        from crucible.config import config
        return config.current_session or ''
    except Exception:
        return ''


def fetch_api_label():
    """Return 'api: <last-path-segment>' derived from the configured api_url."""
    try:
        from urllib.parse import urlparse
        from crucible.config import config
        parsed = urlparse(config.api_url or '')
        parts  = [p for p in parsed.path.split('/') if p]
        label  = parts[-1] if parts else (parsed.netloc or '?')
        return f"api: {label}"
    except Exception:
        return 'api: ?'


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
