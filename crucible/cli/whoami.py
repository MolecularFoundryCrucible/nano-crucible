#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whoami subcommand — show current user info based on the active API key.
"""

import sys
import logging

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the whoami subcommand."""
    parser = subparsers.add_parser(
        'whoami',
        help='Show current user info for the active API key',
        description='Display account information associated with the configured API key',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show access group IDs'
    )
    parser.set_defaults(func=execute)


def execute(args):
    """Execute the whoami command."""
    from crucible.config import config
    try:
        info = config.client.whoami()

        user = info.get('user_info', {})
        access_group = info.get('access_group_name', 'N/A')

        logger.info("\n=== Current User ===")

        first = user.get('first_name', '')
        last = user.get('last_name', '')
        if first or last:
            logger.info(f"Name:       {first} {last}".strip())

        if user.get('orcid'):
            logger.info(f"ORCID:      {user['orcid']}")
        elif access_group:
            logger.info(f"Access group: {access_group}")

        if user.get('email'):
            logger.info(f"Email:      {user['email']}")
        if user.get('lbl_email') and user.get('lbl_email') != user.get('email'):
            logger.info(f"LBL Email:  {user['lbl_email']}")
        if user.get('id'):
            logger.info(f"ID:         {user['id']}")

        if getattr(args, 'verbose', False):
            ids = info.get('access_group_ids', [])
            logger.info(f"Access groups: {len(ids)} ({ids})")

    except Exception as e:
        logger.error(f"Error retrieving account info: {e}")
        if getattr(args, 'debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
