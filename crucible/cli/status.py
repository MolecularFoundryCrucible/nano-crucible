#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Status subcommand — check API reachability and authentication.
"""

import sys
import time
import threading
import itertools
import logging

logger = logging.getLogger(__name__)

from . import term

_SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


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


def register_subcommand(subparsers):
    """Register the status subcommand."""
    parser = subparsers.add_parser(
        'status',
        help='Check API connectivity and authentication',
        description='Verify the API is reachable and the current API key is accepted',
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the status command."""
    from crucible.config import config

    api_url = config.api_url
    api_key = config.api_key

    if not api_url or not api_key:
        logger.error("API URL and key are not configured.")
        logger.error("  crucible config set api_url URL")
        logger.error("  crucible config set api_key KEY")
        sys.exit(1)

    from urllib.parse import urlparse
    host = urlparse(api_url).netloc or api_url

    is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    term.header("Status")
    print()

    stop = threading.Event()
    if is_tty:
        spin_thread = threading.Thread(
            target=_spin, args=(stop, f'Connecting to {host}...'), daemon=True
        )
        spin_thread.start()
    else:
        print(f'  Connecting to {host}...')

    try:
        from crucible.client import CrucibleClient
        t0 = time.monotonic()
        info = CrucibleClient().whoami()
        elapsed_ms = (time.monotonic() - t0) * 1000
    except Exception as e:
        stop.set()
        if is_tty:
            spin_thread.join()
        print(f'  ✗  {term.bold(host)}')
        print(f'\n     {e}')
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)

    stop.set()
    if is_tty:
        spin_thread.join()

    # ── Result ───────────────────────────────────────────────────────────────
    print(f'  ✓  {term.bold(host)}  {term.dim(f"{elapsed_ms:.0f}ms")}')
    print()

    user    = info.get('user_info', {})
    first   = user.get('first_name', '')
    last    = user.get('last_name', '')
    name    = f'{first} {last}'.strip() or None
    orcid   = user.get('orcid')
    email   = user.get('email')
    project = config.current_project

    W = 10

    def _pf(label, value):
        if value not in (None, ''):
            print(f'     {label:<{W}}{value}')

    _pf('Name',    name)
    _pf('ORCID',   term.orcid_link(orcid))
    _pf('Email',   email)
    _pf('Project', project)
