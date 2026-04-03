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
    """Cache a fetched resource in the shell state and start background prefetches.

    For datasets, prefetches graph, keywords, associated files, and download
    links in parallel so Alt+V / Alt+G can re-render without extra API calls.
    For samples, only the graph is prefetched.

    Args:
        shell_state: The shell's mutable state dict (args._shell_state), or
                     None when running outside the interactive shell.
        client:      CrucibleClient instance.
        data:        The fetched resource dict.
        rtype:       Resource type string — 'dataset' or 'sample'.
        resource_id: MFID of the resource.
        **flags:     Additional keys stored in last_resource (verbose, graph,
                     include_metadata, …).
    """
    if shell_state is None:
        return
    from concurrent.futures import ThreadPoolExecutor
    if rtype == 'dataset':
        pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='prefetch')
        futures = {
            '_graph_future':    pool.submit(client.graphs.get, resource_id, recursive=True),
            '_keywords_future': pool.submit(client.datasets.get_keywords, resource_id),
            '_files_future':    pool.submit(client.datasets.get_associated_files, resource_id),
            '_links_future':    pool.submit(client.datasets.get_download_links, resource_id),
        }
    else:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='prefetch')
        futures = {
            '_graph_future': pool.submit(client.graphs.get, resource_id, recursive=True),
        }
    pool.shutdown(wait=False)
    shell_state['last_resource'] = {
        'data': data, 'type': rtype, **futures, **flags
    }
