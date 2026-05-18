#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader for .crux files.

Parses multi-document YAML, collects entities (including inline children),
resolves cross-references, and returns a CastPlan ready for execution.
"""

import json
import re
import glob
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from .models import CastConfig, CastDataset, CastSample, CastPlan, Link

logger = logging.getLogger(__name__)

# Keys that define relationships, not entity properties
_RELATIONSHIP_KEYS = {'children', 'parents', 'samples', 'datasets'}


# ------------------------------------------------------------------
# Loader context (replaces threading individual collections as params)
# ------------------------------------------------------------------

@dataclass
class _LoaderContext:
    config: CastConfig
    base_dir: Path
    datasets: Dict[str, CastDataset] = field(default_factory=dict)
    samples:  Dict[str, CastSample]  = field(default_factory=dict)
    links:    List[Link]             = field(default_factory=list)
    seen_ids: Set[str]               = field(default_factory=set)
    prefilled: Dict[str, str]        = field(default_factory=dict)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    return slug.strip('_') or 'entity'


def _unique_id(base: str, seen: Set[str]) -> str:
    if base not in seen:
        return base
    i = 2
    while f"{base}_{i}" in seen:
        i += 1
    return f"{base}_{i}"


def _is_ref(d) -> bool:
    return isinstance(d, dict) and set(d.keys()) == {'ref'}


def _is_mfid(d) -> bool:
    return isinstance(d, dict) and set(d.keys()) == {'mfid'}


def _resolve_item(item, ctx: _LoaderContext) -> Optional[str]:
    """
    Resolve a relationship item to a local_id.

    - {ref: local_id}  -> returns the local_id
    - {mfid: server_id} -> registers in ctx.prefilled, returns server_id
    - inline dict       -> returns None (caller must recurse into _collect)
    """
    if _is_ref(item):
        return item['ref']
    if _is_mfid(item):
        server_id = item['mfid']
        ctx.prefilled[server_id] = server_id
        return server_id
    return None


def _resolve_globs(files: List[str], base_dir: Path) -> List[str]:
    resolved = []
    for pattern in files:
        if any(c in pattern for c in '*?['):
            matches = sorted(glob.glob(str(base_dir / pattern)))
            if not matches:
                logger.warning(f"Glob pattern matched no files: {pattern}")
            resolved.extend(matches)
        else:
            path = base_dir / pattern
            if not path.exists():
                logger.warning(f"File not found: {path}")
            resolved.append(str(path))
    return resolved


def _load_metadata(value, base_dir: Path) -> Dict:
    """Resolve metadata: accepts an inline dict or a path to a JSON file."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        path = base_dir / value
        if not path.exists():
            raise FileNotFoundError(f"Metadata file not found: {path}")
        with open(path) as f:
            return json.load(f)
    raise TypeError(f"metadata must be a dict or a path to a JSON file, got {type(value).__name__}")


def _collect_relationships(entity_type: str, body: dict, local_id: str, ctx: _LoaderContext):
    """
    Collect all relationship links for one entity.

    For both datasets and samples, the pattern is consistent:
      - children: local_id is the source (parent), resolved item is the target
      - parents:  resolved item is the source, local_id is the target (child)

    Inline items (no ref/mfid key) are recursively collected first.
    """
    if entity_type == 'dataset':
        child_kind  = 'dataset_child'
        child_type  = 'dataset'
        sample_kind = 'dataset_sample'

        for item in body.get('children', []):
            target = _resolve_item(item, ctx) or _collect('dataset', item, ctx)
            ctx.links.append(Link(child_kind, local_id, target))

        for item in body.get('parents', []):
            source = _resolve_item(item, ctx) or _collect('dataset', item, ctx)
            ctx.links.append(Link(child_kind, source, local_id))

        for item in body.get('samples', []):
            target = _resolve_item(item, ctx) or _collect('sample', item, ctx)
            ctx.links.append(Link(sample_kind, local_id, target))

    elif entity_type == 'sample':
        child_kind   = 'sample_child'
        dataset_kind = 'dataset_sample'

        for item in body.get('children', []):
            target = _resolve_item(item, ctx) or _collect('sample', item, ctx)
            ctx.links.append(Link(child_kind, local_id, target))

        for item in body.get('parents', []):
            source = _resolve_item(item, ctx) or _collect('sample', item, ctx)
            ctx.links.append(Link(child_kind, source, local_id))

        for item in body.get('datasets', []):
            source = _resolve_item(item, ctx) or _collect('dataset', item, ctx)
            ctx.links.append(Link(dataset_kind, source, local_id))


def _collect(entity_type: str, body: dict, ctx: _LoaderContext) -> str:
    """
    Collect one entity and its inline children into ctx.
    Returns the local_id assigned to this entity.
    """
    local_id = body.get('id')
    if local_id is None:
        local_id = _unique_id(_slugify(body.get('name', 'entity')), ctx.seen_ids)
    elif local_id in ctx.seen_ids:
        raise ValueError(f"Duplicate id '{local_id}' in .crux file")
    ctx.seen_ids.add(local_id)

    # Strip relationship keys; inherit project_id from config if not set
    entity_fields = {k: v for k, v in body.items() if k not in _RELATIONSHIP_KEYS}
    if not entity_fields.get('project_id') and ctx.config.project_id:
        entity_fields['project_id'] = ctx.config.project_id

    # Resolve metadata file path if a string was given
    if 'metadata' in entity_fields and isinstance(entity_fields['metadata'], str):
        entity_fields['metadata'] = _load_metadata(entity_fields['metadata'], ctx.base_dir)

    if entity_type == 'dataset':
        ctx.datasets[local_id] = CastDataset.model_validate(entity_fields)
    else:
        ctx.samples[local_id] = CastSample.model_validate(entity_fields)

    _collect_relationships(entity_type, body, local_id, ctx)

    return local_id


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def _validate_links(ctx: _LoaderContext):
    """Validate that all refs resolve and point to the correct entity type."""
    _expected = {
        'dataset_child':  ('dataset', 'dataset'),
        'dataset_sample': ('dataset', 'sample'),
        'sample_child':   ('sample',  'sample'),
    }
    for link in ctx.links:
        # mfid refs are trusted - their type is not tracked locally
        if link.source in ctx.prefilled or link.target in ctx.prefilled:
            continue

        src_type = 'dataset' if link.source in ctx.datasets else ('sample' if link.source in ctx.samples else None)
        tgt_type = 'dataset' if link.target in ctx.datasets else ('sample' if link.target in ctx.samples else None)

        if src_type is None:
            raise ValueError(f"Unresolved ref '{link.source}' - no entity with that id in .crux file")
        if tgt_type is None:
            raise ValueError(f"Unresolved ref '{link.target}' - no entity with that id in .crux file")

        exp_src, exp_tgt = _expected[link.kind]
        if src_type != exp_src:
            raise ValueError(
                f"Invalid ref '{link.source}' in {link.kind} link: expected a {exp_src}, got a {src_type}"
            )
        if tgt_type != exp_tgt:
            raise ValueError(
                f"Invalid ref '{link.target}' in {link.kind} link: expected a {exp_tgt}, got a {tgt_type}"
            )


def _check_cycles(links: List[Link]):
    """Raise ValueError if any hierarchical (parent-child) links form a cycle."""
    graph: Dict[str, List[str]] = {}
    for link in links:
        if link.kind in ('dataset_child', 'sample_child'):
            graph.setdefault(link.source, []).append(link.target)

    visited: Set[str] = set()
    in_stack: Set[str] = set()

    def dfs(node):
        visited.add(node)
        in_stack.add(node)
        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                dfs(neighbour)
            elif neighbour in in_stack:
                raise ValueError(
                    f"Circular dependency detected: '{neighbour}' is an ancestor of itself"
                )
        in_stack.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def load(crux_path) -> CastPlan:
    """
    Load and parse a .crux file, returning a CastPlan ready for execution.

    Args:
        crux_path: Path to the .crux file.

    Returns:
        CastPlan with all entities, links, and resolved globs.

    Raises:
        ValueError: On duplicate IDs, unknown document types, or unresolved refs.
        FileNotFoundError: If the .crux file does not exist.
    """
    crux_path = Path(crux_path)
    lock_path = crux_path.with_suffix(crux_path.suffix + '.lock')

    with open(crux_path) as f:
        docs = [d for d in yaml.safe_load_all(f) if d is not None]

    ctx = _LoaderContext(config=CastConfig(), base_dir=crux_path.parent)

    for doc in docs:
        keys = set(doc.keys())
        if 'config' in keys:
            ctx.config = CastConfig.model_validate(doc['config'])
        elif 'dataset' in keys:
            _collect('dataset', doc['dataset'], ctx)
        elif 'sample' in keys:
            _collect('sample', doc['sample'], ctx)
        else:
            raise ValueError(
                f"Unknown document type - expected 'config', 'dataset', or 'sample'. Got: {list(keys)}"
            )

    _validate_links(ctx)
    _check_cycles(ctx.links)

    # Deduplicate links (preserve order)
    ctx.links = list(dict.fromkeys(ctx.links))

    # Resolve glob patterns relative to the .crux file's directory
    for ds in ctx.datasets.values():
        ds.files = _resolve_globs(ds.files, ctx.base_dir)

    logger.info(
        f"Loaded {len(ctx.datasets)} dataset(s), {len(ctx.samples)} sample(s), "
        f"{len(ctx.links)} link(s), {len(ctx.prefilled)} existing resource(s)"
    )
    return CastPlan(
        config=ctx.config,
        datasets=ctx.datasets,
        samples=ctx.samples,
        links=ctx.links,
        lock_path=lock_path,
        base_dir=ctx.base_dir,
        prefilled=ctx.prefilled,
    )
