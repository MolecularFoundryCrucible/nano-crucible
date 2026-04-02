#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tree subcommand — display a resource and its full connected graph as a tree.

Layout:
  ↑ ancestor chains shown as breadcrumbs above the queried node
  ● queried node (green, bold)
  └── children rendered as an ASCII tree below

By default only nodes of the same type as the queried entity are shown
(edge contraction). Use --all to show every type.
"""

import sys
import logging
from collections import deque

logger = logging.getLogger(__name__)

from . import term

_TYPE_LABEL = {'sample': '[s] ', 'dataset': '[ds]'}


def register_subcommand(subparsers):
    parser = subparsers.add_parser(
        'tree',
        help='Show a resource and all its connections as a tree',
        description=(
            'Display ancestor chains and the full descendant tree of a dataset or sample. '
            'The queried entity is highlighted in green. Node IDs are clickable links to '
            'the Graph Explorer. By default only nodes of the same type are shown; '
            'use --all to mix types.'
        ),
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter,
        epilog="""
Examples:
    crucible tree mf-abc123
    crucible tree mf-abc123 --depth 3
    crucible tree mf-abc123 --all
""",
    )
    parser.add_argument('resource_id', metavar='ID',
                        help='MFID of any dataset or sample')
    parser.add_argument('--depth', '-d', type=int, default=None, metavar='N',
                        help='Maximum descendant depth (default: unlimited)')
    parser.add_argument('--all', '-a', action='store_true', default=False,
                        help='Show all node types mixed (default: same type only)')
    parser.set_defaults(func=execute)


# ── Graph helpers ──────────────────────────────────────────────────────────────

def _build_contracted_adj(nodes_by_id, raw_adj, filter_type):
    """Adjacency list keeping only filter_type nodes; other-type nodes are
    skipped and their children promoted to the nearest visible parent."""
    if filter_type is None:
        return {nid: list(kids) for nid, kids in raw_adj.items()}
    result = {}
    for node_id, node in nodes_by_id.items():
        if node.get('entity_type') != filter_type:
            result[node_id] = []
            continue
        visible, seen = [], set()
        queue = deque(raw_adj.get(node_id, []))
        while queue:
            child_id = queue.popleft()
            if child_id in seen:
                continue
            seen.add(child_id)
            child = nodes_by_id.get(child_id, {})
            if child.get('entity_type') == filter_type:
                visible.append(child_id)
            else:
                queue.extend(raw_adj.get(child_id, []))
        result[node_id] = visible
    return result


def _find_path(start, target, adj):
    """Return one path (list of IDs) from start to target via DFS, or None."""
    if start == target:
        return [start]
    stack = [(start, [start])]
    while stack:
        node, path = stack.pop()
        for child in adj.get(node, []):
            if child == target:
                return path + [child]
            if child not in path:
                stack.append((child, path + [child]))
    return None


def _explorer_url(base_url, project_id, entity_type, uid):
    if not (base_url and project_id and uid):
        return None
    dtype = 'sample-graph' if entity_type == 'sample' else 'dataset'
    return f"{base_url.rstrip('/')}/{project_id}/{dtype}/{uid}"


# ── Rendering ─────────────────────────────────────────────────────────────────

def _id_str(uid, entity_type, project_id, base_url, *, highlight=False):
    url = _explorer_url(base_url, project_id, entity_type, uid)
    if highlight:
        return term.hyperlink(term.bold(term.green(uid)), url)
    return term.hyperlink(term.cyan(uid), url)


def _print_node(node_id, nodes_by_id, adj, depth, max_depth, visited,
                project_id, base_url, prefix='', is_last=True):
    node = nodes_by_id.get(node_id)
    if not node:
        return
    if node_id in visited:
        return  # each resource shown once; silently skip duplicates

    connector = '└── ' if is_last else '├── '
    uid   = node['id']
    name  = node.get('name') or '(unnamed)'
    etype = node.get('entity_type', '')
    tag   = term.dim(_TYPE_LABEL.get(etype, '[?]'))

    print(f"{prefix}{connector}{tag} {_id_str(uid, etype, project_id, base_url)}  {name}")
    visited.add(node_id)

    kids = adj.get(node_id, [])
    if not kids:
        return
    ext = '    ' if is_last else '│   '
    if max_depth is not None and depth >= max_depth:
        print(f"{prefix}{ext}{term.dim('…')}")
        return
    for i, kid_id in enumerate(kids):
        _print_node(kid_id, nodes_by_id, adj, depth + 1, max_depth, visited,
                    project_id, base_url,
                    prefix=prefix + ext, is_last=(i == len(kids) - 1))


# ── Entry point ────────────────────────────────────────────────────────────────

def execute(args):
    from crucible.client import CrucibleClient
    from crucible.config import config as _cfg

    try:
        client     = CrucibleClient()
        graph_data = client.graphs.get(args.resource_id, recursive=True)
    except Exception as e:
        logger.error(f"Error fetching graph: {e}")
        if getattr(args, 'debug', False):
            import traceback; traceback.print_exc()
        sys.exit(1)

    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])
    if not nodes:
        logger.error(f"No graph data found for: {args.resource_id}")
        sys.exit(1)

    nodes_by_id = {n['id']: n for n in nodes}

    # Fetch root entity once for project_id (needed for explorer URLs)
    project_id = None
    try:
        root_ent   = client.get(args.resource_id)
        project_id = root_ent.get('project_id')
    except Exception:
        pass
    base_url = _cfg.graph_explorer_url if project_id else None

    # Raw adjacency + in-degree
    raw_adj   = {n['id']: [] for n in nodes}
    in_degree = {n['id']: 0  for n in nodes}
    for e in edges:
        s, t = e['source'], e['target']
        if s in raw_adj:
            raw_adj[s].append(t)
        if t in in_degree:
            in_degree[t] += 1

    root_node = nodes_by_id.get(args.resource_id, {})
    root_name = root_node.get('name') or args.resource_id
    root_type = root_node.get('entity_type', '')

    filter_type = None if getattr(args, 'all', False) else root_type
    adj = _build_contracted_adj(nodes_by_id, raw_adj, filter_type)

    # Contracted in-degree + visible set
    c_in = {nid: 0 for nid in nodes_by_id}
    for nid, kids in adj.items():
        for kid in kids:
            c_in[kid] = c_in.get(kid, 0) + 1

    visible = (
        set(nodes_by_id)
        if filter_type is None
        else {nid for nid, n in nodes_by_id.items() if n.get('entity_type') == filter_type}
    )

    # Reverse contracted adj (within visible)
    rev_adj = {nid: [] for nid in visible}
    for nid, kids in adj.items():
        if nid not in visible:
            continue
        for kid in kids:
            if kid in visible:
                rev_adj.setdefault(kid, []).append(nid)

    # Ancestors of queried node → roots are in-degree-0 ancestors
    anc = set()
    q = deque([args.resource_id])
    while q:
        nid = q.popleft()
        for p in rev_adj.get(nid, []):
            if p not in anc:
                anc.add(p)
                q.append(p)

    roots = [nid for nid in anc if c_in.get(nid, 0) == 0 and nid in visible]

    n_samples  = sum(1 for n in nodes if n.get('entity_type') == 'sample')
    n_datasets = sum(1 for n in nodes if n.get('entity_type') == 'dataset')
    term.header(f"Tree · {root_name}  ({n_samples}s / {n_datasets}ds)")

    # ── Ancestor breadcrumbs ───────────────────────────────────────────────────
    for root_id in roots:
        path = _find_path(root_id, args.resource_id, adj)
        if not path or len(path) <= 1:
            continue  # no ancestors to show
        parts = []
        for nid in path[:-1]:  # everything except the queried node
            n     = nodes_by_id.get(nid, {})
            etype = n.get('entity_type', '')
            name  = n.get('name') or nid
            tag   = term.dim(_TYPE_LABEL.get(etype, '[?]'))
            istr  = _id_str(nid, etype, project_id, base_url)
            parts.append(f"{tag}{istr}  {name}")
        arrow = term.dim(' > ')
        print(term.dim('↑ ') + arrow.join(parts))

    # ── Queried node ───────────────────────────────────────────────────────────
    tag = term.dim(_TYPE_LABEL.get(root_type, '[?]'))
    print(f"{tag} {_id_str(args.resource_id, root_type, project_id, base_url, highlight=True)}  {term.bold(root_name)}")

    # ── Descendant tree ────────────────────────────────────────────────────────
    visited = {args.resource_id}
    kids    = adj.get(args.resource_id, [])
    for i, kid_id in enumerate(kids):
        _print_node(kid_id, nodes_by_id, adj, depth=1, max_depth=args.depth,
                    visited=visited, project_id=project_id, base_url=base_url,
                    prefix='', is_last=(i == len(kids) - 1))
