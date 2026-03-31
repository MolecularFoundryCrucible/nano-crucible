#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Status subcommand — check API reachability, authentication, and configuration.
"""

import sys
import time
import logging

logger = logging.getLogger(__name__)

from . import term


def register_subcommand(subparsers):
    """Register the status subcommand."""
    parser = subparsers.add_parser(
        'status',
        help='Check API connectivity, authentication, and config',
        description='Verify the API is reachable and the current API key is accepted',
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the status command."""
    from crucible.config import config

    _p = term.field_printer(20)

    # ── Config ──────────────────────────────────────────────────────────────
    term.header("Config")

    api_url = config.api_url
    api_key = config.api_key

    _p("API URL", api_url or term.dim("(not set)"))

    if api_key:
        masked = '****' + api_key[-4:] if len(api_key) > 4 else '****'
    else:
        masked = term.dim("(not set)")
    _p("API key", masked)

    _p("Project",  config.current_project or term.dim("(none)"))
    _p("Timeouts", f"{config.connect_timeout}s connect, {config.read_timeout}s read")

    if not api_url or not api_key:
        print()
        logger.error("Configure api_url and api_key first:")
        logger.error("  crucible config set api_url URL")
        logger.error("  crucible config set api_key KEY")
        sys.exit(1)

    # ── Connection ───────────────────────────────────────────────────────────
    print()
    term.header("Connection")

    try:
        from crucible.client import CrucibleClient
        client = CrucibleClient()
        t0 = time.monotonic()
        info = client.whoami()
        elapsed_ms = (time.monotonic() - t0) * 1000

        _p("✓ Reachable", term.dim(f"{elapsed_ms:.0f}ms"))

        user = info.get('user_info', {})
        first = user.get('first_name', '')
        last  = user.get('last_name', '')
        name  = f"{first} {last}".strip() or None
        _p("User",  name)
        _p("ORCID", term.orcid_link(user.get('orcid')))
        _p("Email", user.get('email'))

    except Exception as e:
        _p("✗ Unreachable", str(e))
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
