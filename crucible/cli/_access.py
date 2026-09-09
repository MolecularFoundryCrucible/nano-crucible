#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared CLI wiring for the generic /resources/{mfid}/access/... ACL surface
(BaseResource.list_access/set_access/revoke_access/set_public/set_private).

Reused by dataset.py, sample.py, instrument.py, and project.py - each calls
register_access_commands() with its own subparsers and the CrucibleClient
attribute name for that resource type (e.g. 'datasets').
"""

from . import term
from .helpers import fail


def register_access_commands(subparsers, resource_ops_name, id_metavar='RESOURCE_MFID'):
    """Register access and public-visibility subcommands."""
    _register_access(subparsers, resource_ops_name, id_metavar)
    _register_set_public(subparsers, resource_ops_name, id_metavar)
    _register_set_private(subparsers, resource_ops_name, id_metavar)


def _register_access(subparsers, resource_ops_name, id_metavar):
    parser = subparsers.add_parser(
        'access',
        help='Manage direct ACL entries on a resource',
        description='List, grant, or revoke direct access grants',
        formatter_class=term.ColorHelpFormatter,
    )
    access_subparsers = parser.add_subparsers(dest='access_command', required=True)

    list_parser = access_subparsers.add_parser('list', help='List access grants')
    list_parser.add_argument('resource_id', metavar=id_metavar)
    list_parser.set_defaults(func=_execute_list, _resource_ops_name=resource_ops_name)

    grant_parser = access_subparsers.add_parser('grant', help='Grant access to a principal')
    grant_parser.add_argument('resource_id', metavar=id_metavar)
    grant_parser.add_argument('kind', choices=['users', 'projects'], help='Principal kind')
    grant_parser.add_argument('principal', help="Principal identifier (user reference or project ID)")
    grant_parser.add_argument(
        'permission',
        choices=['viewer', 'contributor', 'editor', 'admin'],
        help='Permission to grant',
    )
    grant_parser.set_defaults(func=_execute_grant, _resource_ops_name=resource_ops_name)

    revoke_parser = access_subparsers.add_parser('revoke', help='Revoke access from a principal')
    revoke_parser.add_argument('resource_id', metavar=id_metavar)
    revoke_parser.add_argument('kind', choices=['users', 'projects'], help='Principal kind')
    revoke_parser.add_argument('principal', help="Principal identifier (user reference or project ID)")
    revoke_parser.set_defaults(func=_execute_revoke, _resource_ops_name=resource_ops_name)


def _register_set_public(subparsers, resource_ops_name, id_metavar):
    parser = subparsers.add_parser(
        'set-public',
        help='Make a resource publicly viewable',
        description='Grant public viewer access (public standing is always viewer-level)',
        formatter_class=term.ColorHelpFormatter,
    )
    parser.add_argument('resource_id', metavar=id_metavar)
    parser.set_defaults(func=_execute_set_public, _resource_ops_name=resource_ops_name)


def _register_set_private(subparsers, resource_ops_name, id_metavar):
    parser = subparsers.add_parser(
        'set-private',
        help='Remove public access from a resource',
        description='Revoke public viewer access',
        formatter_class=term.ColorHelpFormatter,
    )
    parser.add_argument('resource_id', metavar=id_metavar)
    parser.set_defaults(func=_execute_set_private, _resource_ops_name=resource_ops_name)


def _ops(args):
    from crucible.client import CrucibleClient
    client = CrucibleClient()
    return getattr(client, args._resource_ops_name)


def _principal_link(grant):
    from .helpers import instrument_explorer_url, project_explorer_url, user_explorer_url

    principal_id = grant.principal_id
    if grant.principal_type == 'user':
        return term.navigation_link(principal_id, user_explorer_url(principal_id))
    if grant.principal_type == 'project' and grant.slug:
        return term.identifier_link(principal_id, project_explorer_url(grant.slug))
    if grant.principal_type == 'instrument':
        return term.identifier_link(principal_id, instrument_explorer_url(principal_id))
    return term.cyan(principal_id)


def _execute_list(args):
    try:
        ops = _ops(args)
        grants = ops.list_access(args.resource_id)
        term.header(f"Access · {args.resource_id} ({len(grants)})")
        if not grants:
            print(f"  {term.dim('No access grants found.')}")
        else:
            rows = [(_principal_link(g), g.principal_type,
                     term.permission_label(g.permission), g.display_name or '-')
                    for g in grants]
            term.table(rows, ['Principal', 'Kind', 'Permission', 'Name'], max_widths=[30, 16, 14, 30])
    except Exception as e:
        fail("listing access", e, args)


def _execute_grant(args):
    try:
        ops = _ops(args)
        grant = ops.set_access(args.resource_id, args.kind, args.principal, args.permission)
        term.success(
            f"Granted {grant.permission} to {grant.principal_id} "
            f"({grant.principal_type}) on {args.resource_id}", args)
    except Exception as e:
        fail("granting access", e, args)


def _execute_revoke(args):
    try:
        ops = _ops(args)
        ops.revoke_access(args.resource_id, args.kind, args.principal)
        term.success(f"Revoked access for {args.principal} ({args.kind}) on {args.resource_id}", args)
    except Exception as e:
        fail("revoking access", e, args)


def _execute_set_public(args):
    try:
        ops = _ops(args)
        ops.set_public(args.resource_id)
        term.success(f"{args.resource_id} is now publicly viewable", args)
    except Exception as e:
        fail("making resource public", e, args)


def _execute_set_private(args):
    try:
        ops = _ops(args)
        ops.set_private(args.resource_id)
        term.success(f"Public access removed from {args.resource_id}", args)
    except Exception as e:
        fail("making resource private", e, args)
