#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check API reachability, database health, and authentication."""

import itertools
import logging
import sys
import threading
import time

from . import term

logger = logging.getLogger(__name__)

_SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


def _readiness_details(health):
    details = {
        'detected': False,
        'status': None,
        'api_version': None,
        'git_commit': None,
        'branch': None,
        'database_status': None,
        'database_latency_ms': None,
        'schema_revisions': [],
    }
    if not isinstance(health, dict):
        return details

    details['status'] = health.get('status')
    database = health.get('database')
    if isinstance(database, dict):
        build = health.get('build')
        if isinstance(build, dict):
            details['api_version'] = build.get('api_version')
            details['git_commit'] = build.get('git_commit')
            details['branch'] = build.get('branch')
        revisions = database.get('schema_revisions')
        if isinstance(revisions, (list, tuple)):
            details['schema_revisions'] = [str(revision) for revision in revisions]
        details['database_status'] = database.get('status')
        details['database_latency_ms'] = database.get('latency_ms')
        details['detected'] = True
        return details

    if 'db' in health:
        details['api_version'] = health.get('version')
        details['git_commit'] = health.get('git_commit')
        details['branch'] = health.get('branch')
        revisions = health.get('schema_revisions')
        if isinstance(revisions, (list, tuple)):
            details['schema_revisions'] = [str(revision) for revision in revisions]
        details['database_status'] = health.get('db')
        details['database_latency_ms'] = health.get('db_ms')
        details['detected'] = True

    return details


def _readiness_fields(health):
    """Return version, database status, latency, and contract detection."""
    details = _readiness_details(health)
    return (
        details['api_version'],
        details['database_status'],
        details['database_latency_ms'],
        details['detected'],
    )


def _spin(stop_event, message):
    """Animate a spinner on the current line until stop_event is set."""
    for frame in itertools.cycle(_SPINNER_FRAMES):
        if stop_event.is_set():
            break
        sys.stdout.write(f'\r  {message}  {frame}')
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write('\r' + ' ' * (len(message) + 6) + '\r')
    sys.stdout.flush()


def _check(stop_event, is_tty, fn):
    """Run a function while optionally animating a spinner."""
    if is_tty:
        thread = threading.Thread(target=_spin, args=(stop_event, 'Checking...'), daemon=True)
        thread.start()
    started = time.monotonic()
    try:
        result = fn()
        elapsed = (time.monotonic() - started) * 1000
        return result, elapsed, None
    except Exception as error:
        elapsed = (time.monotonic() - started) * 1000
        return None, elapsed, error
    finally:
        stop_event.set()
        if is_tty:
            thread.join()
        stop_event.clear()


def register_subcommand(subparsers):
    """Register the status subcommand."""
    parser = subparsers.add_parser(
        'status',
        help='Check API connectivity, database health, and authentication',
        description='Show endpoint, deployment, database, and authentication status',
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the status command."""
    import requests
    from crucible.config import config

    api_url = config.api_url
    try:
        api_key = config.api_key
    except ValueError:
        api_key = None
    if not api_url:
        logger.error("API URL is not configured. Run: crucible config set api_url URL")
        sys.exit(1)

    endpoint = api_url.rstrip('/')
    is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    stop = threading.Event()
    printer = term.field_printer(16)

    term.header("Crucible Status")
    term.subheader("Endpoint")
    printer("URL", endpoint)
    printer("Project", config.current_project)
    printer("Project source", config.source('current_project'))

    def _health():
        return requests.get(
            f"{endpoint}/health/ready",
            timeout=(5, 15),
        )

    health_result, elapsed_ms, error = _check(stop, is_tty, _health)
    if error is not None:
        printer("Reachability", f'{term.status_marker("error")} unreachable')
        printer("Error", str(error))
        sys.exit(1)

    response = health_result
    http_status = response.status_code
    printer(
        "Reachability",
        f'{term.status_marker("success")} reachable  {term.dim(f"{elapsed_ms:.0f} ms")}',
    )

    try:
        health = response.json()
    except (TypeError, ValueError):
        health = None
    details = _readiness_details(health)

    if health is None:
        readiness_ok = False
        printer(
            "Readiness",
            f'{term.status_marker("error")} invalid response  {term.dim(f"HTTP {http_status}")}',
        )
    elif details['detected']:
        readiness_status = details['status']
        if not readiness_status:
            readiness_status = 'ok' if 200 <= http_status < 300 else 'degraded'
        readiness_ok = 200 <= http_status < 300 and readiness_status == 'ok'
        readiness_kind = 'success' if readiness_ok else 'error'
        readiness_label = 'ready' if readiness_ok else readiness_status
        printer(
            "Readiness",
            f'{term.status_marker(readiness_kind)} {readiness_label}  {term.dim(f"HTTP {http_status}")}',
        )
    else:
        readiness_ok = 200 <= http_status < 300
        readiness_kind = 'info' if readiness_ok else 'error'
        printer(
            "Readiness",
            f'{term.status_marker(readiness_kind)} unknown  {term.dim(f"HTTP {http_status}")}',
        )

    from crucible import __version__

    term.subheader("Deployment")
    printer("Client version", __version__)
    printer("API version", details['api_version'])
    printer("Branch", details['branch'])
    commit = details['git_commit']
    printer("Commit", str(commit)[:12] if commit else None)

    term.subheader("Database")
    if details['detected']:
        database_status = details['database_status'] or 'unknown'
        database_ok = database_status == 'ok'
        database_kind = 'success' if database_ok else 'error'
        database_label = 'available' if database_ok else 'unavailable'
        printer("Status", f'{term.status_marker(database_kind)} {database_label}')
        database_ms = details['database_latency_ms']
        latency = f'{database_ms:.1f} ms' if isinstance(database_ms, (int, float)) else None
        printer("Latency", latency)
        revisions = details['schema_revisions']
        printer("Schema", ', '.join(revisions) if revisions else None)
    else:
        database_ok = True
        printer("Status", f'{term.status_marker("info")} unavailable')

    term.subheader("Authentication")
    if not api_key:
        printer("Status", f'{term.status_marker("info")} not configured')
        printer("Action", "Run: crucible config set api_key KEY")
        print()
        sys.exit(0 if readiness_ok and database_ok else 1)

    def _whoami():
        from crucible.client import CrucibleClient
        return CrucibleClient().whoami()

    info, auth_ms, error = _check(stop, is_tty, _whoami)
    if error is not None:
        printer("Status", f'{term.status_marker("error")} failed')
        printer("Error", str(error))
        print()
        sys.exit(1)

    user = info.get('user_info', {})
    user_id = user.get('unique_id')
    name = term.fmt_name(user, fallback_username=False)
    username = user.get('username')
    identity = name or username or user.get('unique_id') or 'authenticated user'
    if username and username != identity:
        identity += f'  {term.dim(f"(@{username})")}'
    identity = term.user_link(identity, user_id)

    printer(
        "Status",
        f'{term.status_marker("success")} authenticated  {term.dim(f"{auth_ms:.0f} ms")}',
    )
    printer("User", identity)
    if user.get('is_service_account'):
        printer("Type", "service account")

    print()
    sys.exit(0 if readiness_ok and database_ok else 1)
