#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache management subcommand — inspect and clean the local dataset cache.
"""

import os
import shutil
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    parser = subparsers.add_parser(
        'cache',
        help='Manage the local dataset cache',
        description='Inspect and clean the local Crucible dataset cache',
    )
    sub = parser.add_subparsers(dest='cache_action')

    # --- show ---
    show_p = sub.add_parser('show', help='Show cache location and disk usage')
    show_p.add_argument(
        '--top', type=int, default=10, metavar='N',
        help='Show the N largest cached datasets (default: 10)'
    )
    show_p.set_defaults(func=_execute_show)

    # --- clear ---
    clear_p = sub.add_parser('clear', help='Delete cached files')
    clear_p.add_argument(
        '--older-than', type=int, default=None, metavar='DAYS',
        help='Only remove dataset entries not accessed in the last N days'
    )
    clear_p.add_argument(
        '--dataset', metavar='ID', default=None,
        help='Remove a single dataset from the cache'
    )
    clear_p.add_argument(
        '-y', '--yes', action='store_true',
        help='Skip confirmation prompt'
    )
    clear_p.set_defaults(func=_execute_clear)

    parser.set_defaults(func=lambda args: parser.print_help())


# ── helpers ──────────────────────────────────────────────────────────────────

def _dir_size(path):
    """Return total size of a directory tree in bytes."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def _last_access(path):
    """Return the most recent atime of any file under path."""
    latest = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                latest = max(latest, os.path.getatime(fp))
            except OSError:
                pass
    return latest


def _human(size):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# ── show ─────────────────────────────────────────────────────────────────────

def _execute_show(args):
    from crucible.config import config
    cache_dir = config.cache_dir
    datasets_dir = os.path.join(cache_dir, 'datasets')

    W = 12
    def _p(label, value):
        print(f"  {label:<{W}}{value}")

    term.header("Cache")
    _p("Location", cache_dir)
    _p("Total size", _human(_dir_size(cache_dir)))

    try:
        entries = sorted(os.scandir(cache_dir), key=lambda e: e.name)
    except OSError:
        return

    term.subheader("Breakdown")
    for entry in entries:
        if entry.is_dir():
            print(f"  {entry.name}/  {_human(_dir_size(entry.path))}")

    if not os.path.isdir(datasets_dir):
        return

    dataset_entries = []
    for entry in os.scandir(datasets_dir):
        if entry.is_dir():
            dataset_entries.append((entry.name, _dir_size(entry.path)))
    dataset_entries.sort(key=lambda x: x[1], reverse=True)

    n = min(args.top, len(dataset_entries))
    if n:
        term.subheader(f"Top {n} Largest Cached Datasets")

        # Look up each dataset in parallel to get project_id for the link URL.
        # Falls back to an unlinked MFID if the API call fails.
        from crucible.client import CrucibleClient
        from concurrent.futures import ThreadPoolExecutor

        try:
            _base = config.graph_explorer_url.rstrip('/')
        except Exception:
            _base = None

        top_entries = dataset_entries[:n]

        def _lookup(dsid):
            try:
                ds = CrucibleClient().datasets.get(dsid)
                pid = ds.get('project_id') if ds else None
                url = f"{_base}/{pid}/dataset/{dsid}" if _base and pid else None
            except Exception:
                url = None
            return dsid, url

        urls = {}
        with ThreadPoolExecutor(max_workers=min(n, 8)) as pool:
            for dsid, url in pool.map(lambda e: _lookup(e[0]), top_entries):
                urls[dsid] = url

        rows = [
            (term.mfid_link(dsid, urls.get(dsid)) or dsid, _human(size))
            for dsid, size in top_entries
        ]
        term.table(rows, ['MFID', 'Size'], max_widths=[36, 10])

    print(f"\n  {term.dim(f'{len(dataset_entries)} dataset(s) cached in total.')}")


# ── clear ────────────────────────────────────────────────────────────────────

def _execute_clear(args):
    from crucible.config import config
    cache_dir = config.cache_dir
    datasets_dir = os.path.join(cache_dir, 'datasets')

    # --- single dataset ---
    if args.dataset:
        target = os.path.join(datasets_dir, args.dataset)
        if not os.path.isdir(target):
            logger.error(f"Dataset '{args.dataset}' not found in cache.")
            return
        size = _dir_size(target)
        if not args.yes:
            confirm = input(f"Remove {args.dataset} ({_human(size)}) from cache? [y/N] ")
            if confirm.strip().lower() != 'y':
                logger.info("Aborted.")
                return
        shutil.rmtree(target)
        logger.info(f"✓ Removed {args.dataset} ({_human(size)})")
        return

    # --- older-than filter ---
    if args.older_than is not None:
        if not os.path.isdir(datasets_dir):
            logger.info("Cache is empty.")
            return
        cutoff = datetime.now(timezone.utc).timestamp() - args.older_than * 86400
        targets = [
            e for e in os.scandir(datasets_dir)
            if e.is_dir() and _last_access(e.path) < cutoff
        ]
        if not targets:
            logger.info(f"No cached datasets older than {args.older_than} day(s).")
            return
        total = sum(_dir_size(e.path) for e in targets)
        if not args.yes:
            confirm = input(
                f"Remove {len(targets)} dataset(s) not accessed in {args.older_than}+ days "
                f"({_human(total)})? [y/N] "
            )
            if confirm.strip().lower() != 'y':
                logger.info("Aborted.")
                return
        for entry in targets:
            shutil.rmtree(entry.path)
        logger.info(f"✓ Removed {len(targets)} dataset(s) ({_human(total)})")
        return

    # --- clear everything ---
    total = _dir_size(cache_dir)
    if not args.yes:
        confirm = input(f"Clear entire cache at {cache_dir} ({_human(total)})? [y/N] ")
        if confirm.strip().lower() != 'y':
            logger.info("Aborted.")
            return
    shutil.rmtree(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"✓ Cache cleared ({_human(total)} freed)")
