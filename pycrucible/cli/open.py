#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open subcommand for opening Crucible resources in the browser.

Opens the Graph Explorer home page or a specific resource by mfid.
"""

import sys
import webbrowser
import logging

logger = logging.getLogger(__name__)

def register_subcommand(subparsers):
    """Register the open subcommand."""
    parser = subparsers.add_parser(
        'open',
        help='Open a Crucible resource in the browser',
        description='Open the Graph Explorer or a specific resource by mfid',
        formatter_class=lambda prog: __import__('argparse').RawDescriptionHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    # Open the Graph Explorer home page
    crucible open

    # Open a specific resource by mfid
    crucible open 0tcbwt4cp9x1z000bazhkv5gkg

    # Just print the URL instead of opening
    crucible open 0tcbwt4cp9x1z000bazhkv5gkg --print-url
"""
    )

    # mfid (optional positional argument)
    parser.add_argument(
        'mfid',
        nargs='?',
        default=None,
        help='Unique identifier (mfid) of the resource to open (optional)'
    )

    # Print URL instead of opening
    parser.add_argument(
        '--print-url',
        action='store_true',
        help='Print the URL instead of opening in browser'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the open command."""
    from pycrucible.config import config

    mfid = args.mfid

    # Get graph explorer URL from config
    graph_explorer_url = config.graph_explorer_url.rstrip('/')

    # Build URL
    if mfid is None:
        # No mfid -> open root URL
        url = graph_explorer_url
    else:
        # mfid provided -> get resource with automatic type detection
        try:
            resource_type = config.client.get_resource_type(mfid)
            resource = config.client.get(mfid, resource_type=resource_type)
        except Exception as e:
            logger.error(f"Resource '{mfid}' not found: {e}")
            sys.exit(1)

        # Map resource type to URL path
        dtype = "sample-graph" if resource_type == "sample" else "dataset"

        # Extract project ID
        project_id = resource.get("project_id")
        if not project_id:
            logger.error(f"Resource '{mfid}' has no project_id")
            sys.exit(1)

        url = f"{graph_explorer_url}/{project_id}/{dtype}/{mfid}"

    if args.print_url:
        # Just print the URL for scripting
        print(url)
    else:
        # Open in browser
        logger.info(f"Opening: {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            logger.info(f"URL: {url}")
            sys.exit(1)
