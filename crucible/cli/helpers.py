#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared CLI helper utilities.

Functions here are used across multiple CLI modules (dataset, sample, get,
shell, keybindings, etc.) and don't belong in term.py (display-only) or
shell.py (which would create circular imports).
"""

import argparse
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from ..utils.identifiers import MFID_PATTERN, classify_user_reference

logger = logging.getLogger(__name__)

_MFID_RE = MFID_PATTERN
_NO_DEFAULT = object()


class DeprecatedAliasAction(argparse.Action):
    """Store an option value and warn when a deprecated spelling was used."""

    def __init__(self, option_strings, dest, deprecated_options=(), replacement=None, **kwargs):
        self.deprecated_options = set(deprecated_options)
        self.replacement = replacement
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string in self.deprecated_options:
            from . import term

            label = term.yellow('Warning:', stream=sys.stderr)
            print(
                f"{label} {option_string} is deprecated; use {self.replacement} instead.",
                file=sys.stderr,
            )
        setattr(namespace, self.dest, values)


def _error_details(error):
    response = getattr(error, 'response', None)
    if response is None:
        return None, None, []

    status = getattr(response, 'status_code', None)
    reason = getattr(response, 'reason', None)
    detail = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get('detail') or payload.get('message') or payload.get('error')
        elif payload:
            detail = payload
    except (ValueError, AttributeError):
        text = getattr(response, 'text', '').strip()
        detail = text or None

    items = detail if isinstance(detail, list) else [detail] if detail is not None else []
    details = []
    for item in items:
        if isinstance(item, dict):
            location = item.get('loc') or []
            if isinstance(location, (str, int)):
                location = [location]
            location = [str(part) for part in location if part not in ('body', 'query', 'path')]
            entry = {'message': str(item.get('msg') or item.get('message') or item)}
            if location:
                entry['field'] = '.'.join(location)
            if item.get('type'):
                entry['type'] = str(item['type'])
            details.append(entry)
        else:
            details.append({'message': str(item)})
    return status, reason, details


def format_cli_error(action: str, error: Exception) -> dict:
    import requests

    status, reason, details = _error_details(error)
    if status is not None:
        error_type = 'http_error'
    elif isinstance(error, requests.exceptions.Timeout):
        error_type = 'timeout'
        reason = 'Request timed out'
    elif isinstance(error, requests.exceptions.ConnectionError):
        error_type = 'connection_error'
        reason = 'Connection failed'
    else:
        error_type = type(error).__name__

    if not details and str(error):
        details = [{'message': str(error)}]

    result = {
        'type': error_type,
        'message': f"Failed while {action}." if action else 'Command failed.',
        'details': details,
    }
    if status is not None:
        result['status'] = status
    if reason:
        result['reason'] = str(reason)
    return result


def print_cli_error(data: dict, as_json: bool = False) -> None:
    from . import term

    if as_json:
        print(json.dumps({'error': data}, default=str), file=sys.stderr)
        return

    title = 'Error'
    if data.get('status') is not None:
        title += f" {data['status']}"
    if data.get('reason'):
        title += f" {data['reason']}"
    print(term.red(title, stream=sys.stderr), file=sys.stderr)
    print(data['message'], file=sys.stderr)

    details = data.get('details') or []
    if details:
        print(file=sys.stderr)
        field_width = max((len(item.get('field', '')) for item in details), default=0)
        for item in details:
            field = item.get('field')
            message = item.get('message', '')
            if field:
                label = term.bold(field.ljust(field_width), stream=sys.stderr)
                print(f"  {label}  {message}", file=sys.stderr)
            else:
                print(f"  {message}", file=sys.stderr)


def show_warning(message) -> None:
    from . import term

    label = term.yellow('Warning:', stream=sys.stderr)
    print(f"{label} {message}", file=sys.stderr)


def add_relationship_type_filter(parser) -> None:
    """Add the --relationship-type filter to a parent/child listing command."""
    from ..constants import RELATIONSHIP_TYPES

    parser.add_argument(
        '--relationship-type',
        choices=RELATIONSHIP_TYPES,
        metavar='TYPE',
        help=f"Only show links of this kind ({', '.join(RELATIONSHIP_TYPES)}). "
             f"Untyped links are excluded when this is set."
    )


def add_scope_filters(parser, resource: str) -> None:
    """Add filters shared by '<resource> list' and '<resource> facets'.

    These narrow which records are considered, so both commands accept the
    same selection: project, visibility, ownership, time range, and the
    resource's own exact-match and empty-field filters.
    """
    from ..constants import PROJECT_SCOPES, VISIBILITIES

    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument(
        '--project-id', '-p', default=None, metavar='ID',
        help='Crucible project ID (uses the current project if one is set; '
             'otherwise every accessible project)'
    )
    project_group.add_argument(
        '--project-mfid', default=None, metavar='MFID',
        help='Canonical project MFID'
    )
    project_group.add_argument(
        '--all-projects', action='store_true', default=False,
        help='Ignore the current project and include every accessible project'
    )
    parser.add_argument(
        '-pid', action=DeprecatedAliasAction, deprecated_options={'-pid'},
        replacement='--project-id', dest='project_id', default=argparse.SUPPRESS,
        metavar='ID', help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--project-scope', choices=PROJECT_SCOPES, default=None, metavar='SCOPE',
        help=f"Project relationship to include: {', '.join(PROJECT_SCOPES)} "
             f"(default: assigned)"
    )
    parser.add_argument(
        '--visibility', choices=VISIBILITIES, default=None, metavar='LEVEL',
        help=f"Restrict results by visibility ({', '.join(VISIBILITIES)})"
    )
    parser.add_argument(
        '--mine', action='store_true', default=False,
        help=f'Only include {resource}s you own'
    )
    parser.add_argument(
        '--owner', default=None, dest='owner_id', metavar='USER',
        help='Only include records owned by this user (username, ORCID, or MFID)'
    )
    parser.add_argument(
        '--created-after', dest='creation_time_gte', default=None, metavar='WHEN',
        help='Created at or after this time (ISO 8601 or YYYY-MM-DD)'
    )
    parser.add_argument(
        '--created-before', dest='creation_time_lte', default=None, metavar='WHEN',
        help='Created at or before this time'
    )
    parser.add_argument(
        '--modified-after', dest='modification_time_gte', default=None, metavar='WHEN',
        help='Modified at or after this time'
    )
    parser.add_argument(
        '--modified-before', dest='modification_time_lte', default=None, metavar='WHEN',
        help='Modified at or before this time'
    )
    for flags, dest, metavar, text in _RESOURCE_FILTERS[resource]:
        parser.add_argument(*flags, dest=dest, default=None, metavar=metavar,
                            help=text)
    empty_fields = _EMPTY_FIELDS[resource]
    parser.add_argument(
        '--missing', dest='missing', action='append', default=None,
        choices=empty_fields, metavar='FIELD',
        help=f"Only include records with no value for FIELD "
             f"({', '.join(empty_fields)}); repeatable"
    )


# (flags, dest, metavar, help) for each resource's exact-match filters, shared
# by list and facets. dest is the API query parameter.
_RESOURCE_FILTERS = {
    'dataset': [
        (('-m', '--measurement'), 'measurement', 'TYPE',
         'Filter by measurement (exact match)'),
        (('--session',), 'session_name', 'NAME', 'Filter by session name (exact match)'),
        (('--data-format',), 'data_format', 'FORMAT', 'Filter by data format (exact match)'),
        (('--instrument-mfid',), 'instrument_mfid', 'MFID',
         'Filter by canonical instrument MFID'),
        (('--sample-mfid',), 'sample_mfid', 'MFID',
         'Only include datasets linked to this sample'),
    ],
    'sample': [
        (('--type',), 'sample_type', 'TYPE',
         'Filter by sample type (exact match, or use * / ? wildcards in list)'),
        (('--dataset-mfid',), 'dataset_mfid', 'MFID',
         'Only include samples linked to this dataset'),
    ],
}

# User-facing field name -> API *_is_null parameter.
_EMPTY_FIELDS = {
    'dataset': ('session', 'measurement', 'data_format', 'instrument',
                'project', 'owner'),
    'sample': ('sample_type', 'project', 'owner'),
}
_EMPTY_FIELD_PARAMS = {
    'session': 'session_name_is_null',
    'measurement': 'measurement_is_null',
    'data_format': 'data_format_is_null',
    'instrument': 'instrument_mfid_is_null',
    'project': 'project_mfid_is_null',
    'owner': 'owner_id_is_null',
    'sample_type': 'sample_type_is_null',
}


def add_listing_filters(parser) -> None:
    """Add the list-only ordering options."""
    from ..constants import RESOURCE_SORTS, SORT_DIRECTIONS

    parser.add_argument(
        '--sort',
        choices=RESOURCE_SORTS,
        default=None,
        metavar='FIELD',
        help=f"Order results by {', '.join(RESOURCE_SORTS)} (default: created, newest first)"
    )
    parser.add_argument(
        '--direction',
        choices=SORT_DIRECTIONS,
        default=None,
        metavar='DIR',
        help=f"Sort direction ({', '.join(SORT_DIRECTIONS)}, default: desc). Requires --sort."
    )


def resolve_list_project(args):
    """Return (project_id, project_mfid) for a list or facets command.

    An explicit --project-id or --project-mfid wins, --all-projects disables
    the current project, and otherwise the current project applies if one is
    set. An instrument filter also skips the current project, because
    instruments are shared across projects. Returning (None, None) means
    every accessible project.
    """
    project_id = getattr(args, 'project_id', None)
    project_mfid = getattr(args, 'project_mfid', None)
    if project_id or project_mfid or getattr(args, 'all_projects', False):
        return project_id, project_mfid
    if ((getattr(args, 'instrument_mfid', None) or getattr(args, 'instrument_id', None))
            and not getattr(args, 'project_scope', None)):
        return None, None
    project_id, _ = resolve_project_context(args)
    return project_id, None


def scope_filter_kwargs(args, client=None) -> dict:
    """Collect the shared selection filters into list() or facets() keywords.

    Includes the resolved project context. A --owner value that is not
    already a canonical ORCID or MFID is resolved through the API, so the
    request always carries the stable identifier.
    """
    kwargs = {}
    project_id, project_mfid = resolve_list_project(args)
    if project_id is not None:
        kwargs['project_id'] = project_id
    if project_mfid is not None:
        kwargs['project_mfid'] = project_mfid
    project_scope = getattr(args, 'project_scope', None)
    if project_scope is not None:
        if project_id is None and project_mfid is None:
            raise ValueError("--project-scope requires a project")
        kwargs['project_scope'] = project_scope
    names = ['visibility', 'creation_time_gte', 'creation_time_lte',
             'modification_time_gte', 'modification_time_lte']
    for filters in _RESOURCE_FILTERS.values():
        names.extend(dest for _, dest, _, _ in filters)
    for name in names:
        value = getattr(args, name, None)
        if value is not None:
            kwargs[name] = value
    owner = getattr(args, 'owner_id', None)
    if owner is not None:
        if client is None:
            from ..config import get_client
            client = get_client()
        kwargs['owner_id'] = resolve_user_id(client, owner)
    if getattr(args, 'mine', False):
        kwargs['affiliation'] = 'owner'
    for field in getattr(args, 'missing', None) or []:
        kwargs[_EMPTY_FIELD_PARAMS[field]] = True
    return kwargs


def listing_filter_kwargs(args) -> dict:
    """Collect the list-only ordering options into list() keywords.

    Without --sort, request newest-created first explicitly: the server's
    own default orders by MFID, which is not chronological for legacy
    records whose MFIDs predate the time-ordered scheme.
    """
    sort = getattr(args, 'sort', None)
    if sort is None:
        return {'sort': 'created', 'direction': 'desc'}
    kwargs = {'sort': sort}
    direction = getattr(args, 'direction', None)
    if direction is not None:
        kwargs['direction'] = direction
    return kwargs


def display_order(records: list, sort: str | None = None,
                  direction: str | None = None) -> list:
    """Order fetched records for a terminal table.

    The server returns the most relevant records first, newest by default,
    so --limit keeps the newest N. Reversing puts the newest row last, next
    to the prompt. An explicit ascending sort is already in reading order.
    """
    if sort is not None and direction == 'asc':
        return list(records)
    return list(reversed(records))


def group_records(records: list, field: str) -> list:
    """Split display-ordered records into (value, records) groups.

    Groups keep the records' order and are themselves ordered by the
    position of their last record, so the group holding the newest record
    is printed last.
    """
    groups = {}
    last_seen = {}
    for index, record in enumerate(records):
        key = record.get(field) or None
        groups.setdefault(key, []).append(record)
        last_seen[key] = index
    return [(key, groups[key]) for key in sorted(groups, key=last_seen.get)]


def register_facets_command(subparsers, resource: str, fields, examples: str):
    """Register a '<resource> facets FIELD' subcommand."""
    from . import term
    from ..constants import FACET_SORTS, SORT_DIRECTIONS

    parser = subparsers.add_parser(
        'facets',
        help=f'Count {resource}s grouped by a field',
        description=f'Group {resource}s into value buckets with counts, '
                    f'without fetching the records themselves',
        formatter_class=term.ColorHelpFormatter,
        epilog=examples,
    )
    parser.add_argument(
        'field',
        metavar='FIELD',
        choices=fields,
        help=f"Field to group by: {', '.join(fields)}"
    )
    parser.add_argument(
        '--sort', choices=FACET_SORTS, default=None, metavar='BY',
        help=f"Order buckets by {', '.join(FACET_SORTS)} (default: value)"
    )
    parser.add_argument(
        '--direction', choices=SORT_DIRECTIONS, default=None, metavar='DIR',
        help=f"Bucket ordering direction ({', '.join(SORT_DIRECTIONS)})"
    )
    parser.add_argument(
        '--limit', '-l', type=int, default=100, metavar='N',
        help='Maximum number of buckets to return (default: 100)'
    )
    add_scope_filters(parser, resource)
    parser.add_argument(
        '--json', action='store_true', default=False,
        help='Output as JSON'
    )
    return parser


def execute_facets_command(args, resource: str):
    """Execute a '<resource> facets FIELD' subcommand."""
    import json
    from . import term
    from ..config import get_client

    try:
        client = get_client()
        filters = scope_filter_kwargs(args, client)

        operations = getattr(client, f'{resource}s')
        response = operations.facets(
            args.field, limit=args.limit, sort=args.sort,
            direction=args.direction, **filters)

        if args.json:
            print(json.dumps(response, indent=2, default=str))
            return

        buckets = response.get('items') or []
        scope = filters.get('project_id') or filters.get('project_mfid')
        scope_label = f" · {scope}" if scope else ''
        term.header(f"{args.field}{scope_label} · {len(buckets)} values")
        if not buckets:
            print(f"  {term.dim(f'No {resource}s matched.')}")
            return

        rows = []
        for bucket in buckets:
            value, label = bucket.get('value'), bucket.get('label')
            if value is None:
                rows.append((term.dim('(none)'), '', bucket.get('count')))
            elif not str(value).strip():
                rows.append((term.dim('(empty)'), '', bucket.get('count')))
            else:
                rows.append((label or value,
                             value if label and label != value else '',
                             bucket.get('count')))
        if any(row[1] for row in rows):
            term.table(rows, ['VALUE', 'ID', 'COUNT'])
        else:
            term.table([(row[0], row[2]) for row in rows], ['VALUE', 'COUNT'])
        if response.get('next_cursor'):
            print(f"\n  {term.dim('More values available; raise --limit to see them.')}")

    except Exception as e:
        fail(f"retrieving {resource} facets", e, args)


def format_relationship_type(link) -> str:
    """Render a link's relationship_type as a dim trailing annotation.

    Links created before typing existed carry no type, so show a dim dash
    rather than dropping the column and making the rows ragged.
    """
    from . import term

    return term.dim(link.get('relationship_type') or '—')


def _interactive_stdin() -> bool:
    return hasattr(sys.stdin, 'isatty') and sys.stdin.isatty()


def _prompt_unavailable(label: str, option: str = None) -> None:
    from . import term

    message = f"Cannot prompt for {label.lower()} because stdin is not interactive."
    if option:
        message += f" Provide {option}."
    print(term.red('Error', stream=sys.stderr), file=sys.stderr)
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _prompt_value(label: str, *, optional: bool = False, default=_NO_DEFAULT,
                  validator=None, option: str = None, secret: bool = False,
                  hint: str = None):
    from . import term

    if not _interactive_stdin():
        if default is not _NO_DEFAULT:
            value = str(default)
            try:
                return validator(value) if validator else value
            except ValueError as error:
                print(term.red('Invalid value', stream=sys.stderr), file=sys.stderr)
                print(str(error), file=sys.stderr)
                if option:
                    print(f"Provide {option} to override the configured default.", file=sys.stderr)
                raise SystemExit(2)
        if optional:
            return None
        _prompt_unavailable(label, option)

    if default is not _NO_DEFAULT:
        suffix = term.dim(f" [{default}]")
    elif optional:
        detail = f"optional; {hint}" if hint else "optional"
        suffix = term.dim(f" ({detail})")
    else:
        suffix = term.dim(" (required)")
    if hint and not optional:
        suffix += term.dim(f" ({hint})")
    prompt = f"{term.bold(label)}{suffix}: "

    reader = input
    if secret:
        import getpass
        reader = getpass.getpass

    while True:
        try:
            value = reader(prompt).strip()
        except EOFError:
            _prompt_unavailable(label, option)
        if not value:
            if default is not _NO_DEFAULT:
                value = str(default)
            if optional:
                return None
            elif default is _NO_DEFAULT:
                error = ValueError(f"{label} is required.")
                print(term.red('Invalid value', stream=sys.stderr), file=sys.stderr)
                print(str(error), file=sys.stderr)
                continue
        if value:
            try:
                return validator(value) if validator else value
            except ValueError as validation_error:
                error = validation_error

        print(term.red('Invalid value', stream=sys.stderr), file=sys.stderr)
        print(str(error), file=sys.stderr)


def prompt_required(label: str, validator=None, option: str = None):
    return _prompt_value(label, validator=validator, option=option)


def prompt_optional(label: str, validator=None, default=_NO_DEFAULT,
                    option: str = None, hint: str = None):
    return _prompt_value(
        label,
        optional=default is _NO_DEFAULT,
        default=default,
        validator=validator,
        option=option,
        hint=hint,
    )


def prompt_secret(label: str, option: str = None) -> str:
    return _prompt_value(label, option=option, secret=True)


def prompt_choice(label: str, choices, default=_NO_DEFAULT, option: str = None) -> str:
    allowed = tuple(choices)

    def validate(value):
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"{label} must be one of: {', '.join(allowed)}.")
        return normalized

    return _prompt_value(
        label,
        default=default,
        validator=validate,
        option=option,
        hint='/'.join(allowed),
    )


def prompt_confirm(message: str, *, default: bool = False, option: str = None) -> bool:
    from . import term

    if not _interactive_stdin():
        _prompt_unavailable('confirmation', option)

    hint = '[Y/n]' if default else '[y/N]'
    prompt = f"{term.yellow(message)} {term.dim(hint)} "
    while True:
        try:
            response = input(prompt).strip().lower()
        except EOFError:
            _prompt_unavailable('confirmation', option)
        if not response:
            return default
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no'):
            return False
        print(term.red('Invalid response', stream=sys.stderr), file=sys.stderr)
        print("Enter 'yes' or 'no'.", file=sys.stderr)


def prompt_username(label: str = 'Username') -> str:
    from ..utils.identifiers import validate_username

    return prompt_required(label, validator=validate_username, option='--username')


def validate_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', email):
        raise ValueError("Email must be a valid address such as user@example.org.")
    return email


def validate_user_reference(value: str) -> str:
    _, normalized = classify_user_reference(value)
    return normalized


def validate_mfid(value: str) -> str:
    from ..utils.identifiers import validate_mfid as validate

    return validate(value)


def validate_orcid(value: str) -> str:
    from ..utils.identifiers import is_orcid

    if not is_orcid(value):
        raise ValueError("ORCID must use the canonical 0000-0000-0000-000X format.")
    return value


def validate_project_ids(value: str) -> str:
    from ..utils.identifiers import validate_slug

    project_ids = [item.strip() for item in value.split(',') if item.strip()]
    if not project_ids:
        raise ValueError("Provide at least one project ID.")
    for project_id in project_ids:
        validate_slug(project_id, 'project')
    return ','.join(project_ids)


def validate_http_url(value: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP or HTTPS URL.")
    return value.rstrip('/')


def install_warning_formatter() -> None:
    import warnings

    def showwarning(message, category, filename, lineno, file=None, line=None):
        show_warning(message)

    warnings.showwarning = showwarning


def fail(action: str, error: Exception, args=None) -> None:
    """Display a structured CLI error and exit with status 1."""
    data = format_cli_error(action, error)
    as_json = not isinstance(args, bool) and getattr(args, 'json', False)
    print_cli_error(data, as_json=as_json)
    debug = args if isinstance(args, bool) else getattr(args, 'debug', False)
    if debug:
        import traceback
        traceback.print_exc()
    sys.exit(1)


def require_capability(client, capability: str, action: str) -> None:
    """Exit early when the caller's account cannot perform an action.

    Checked before interactive prompts so the user is not asked to fill in a
    form the server will reject. An unreadable profile leaves capabilities
    empty, in which case the attempt proceeds and the API decides.
    """
    from . import term

    capabilities = getattr(client, 'capabilities', None)
    if getattr(capabilities, capability, None) is False:
        print(term.red('Not permitted', stream=sys.stderr), file=sys.stderr)
        print(f"Your account is not permitted to {action}.", file=sys.stderr)
        sys.exit(1)


def parse_user_ref(value: str) -> dict:
    """Sniff a user identifier's format and return a kwargs dict for users.get()/users.resolve().

    Uses the shared API-contract classifier. Canonical person and service-account
    identifiers are returned under the legacy ``orcid`` keyword for compatibility.
    """
    reference_kind, normalized = classify_user_reference(value)
    if reference_kind == 'unique_id':
        return {'orcid': normalized}
    return {reference_kind: normalized}


def parse_sa_ref(value: str) -> dict:
    """Sniff a service account identifier's format for service_accounts.get().

    Matches the MFID pattern (26-char Crockford base32) -> unique_id. Otherwise -> username.
    """
    if _MFID_RE.match(value):
        return {'unique_id': value}
    return {'username': value}


def add_user_reference_argument(parser) -> None:
    """Add the --user/-u option shared by member-management commands."""
    parser.add_argument('--user', '-u', metavar='USER', required=True,
                        help='ORCID, MFID, username, or email of the user')


def resolve_user_id(client, value: str) -> str:
    """Resolve a user reference to its canonical ORCID or MFID.

    Returns a canonical ORCID or MFID unchanged without an API call.
    Raises ValueError if the identifier doesn't resolve to a user.
    """
    reference_kind, normalized = classify_user_reference(value)
    if reference_kind == 'unique_id':
        return normalized
    user = client.users.get(normalized)
    return user.get('unique_id')


def resolve_sa_id(client, value: str) -> str:
    """Resolve a service account identifier (MFID or username) to its MFID.

    A username could coincidentally match the MFID shape (usernames allow the
    same charset), so an MFID-shaped value that isn't found is retried as a
    username before giving up.
    Raises ValueError if the identifier doesn't resolve to a service account.
    """
    ref = parse_sa_ref(value)
    sa = client.service_accounts.get(**ref)
    if sa is None and 'unique_id' in ref:
        sa = client.service_accounts.get(username=value)
    if sa is None:
        raise ValueError(f"Service account not found: {value}")
    return sa.get('unique_id')


def fetch_projects(client):
    """Return [(project_id, title), ...] for all accessible projects."""
    try:
        return [(p.get('project_id', ''), p.get('title') or '-')
                for p in client.projects.list() if p.get('project_id')]
    except Exception:
        return []


def fetch_deletions(client):
    """Return pending deletion requests, or None if the user lacks permission."""
    try:
        scope = 'reviewable' if client.can_elevate else None
        return client.deletions.list(status='pending', scope=scope)
    except Exception:
        return None


def fetch_join_requests(client):
    """Return pending join requests, or None if the user lacks permission."""
    try:
        return client.access_groups.list_join_requests(
            status='pending', privilege_mode=client._admin_mode())
    except Exception:
        return None


def fetch_service_accounts(client):
    """Return all service accounts, or None if the user lacks permission."""
    try:
        return client.service_accounts.list()
    except Exception:
        return None


def resolve_usernames(client, orcids):
    """Batch-resolve ORCIDs to usernames. Returns {orcid: username_or_orcid}."""
    orcids = sorted({o for o in orcids if o})
    if not orcids or client is None:
        return {}
    try:
        resolved = client.users.resolve(orcids=orcids)
    except Exception:
        return {}
    return {orcid: (info.get('username') or orcid) if info else orcid
            for orcid, info in resolved.items()}


def fetch_user_label(client, whoami_info=None):
    """Return a display name for the authenticated user.

    Pass whoami_info to skip a redundant API call when the caller already
    has the result of client.whoami().
    """
    from . import term
    try:
        info = whoami_info if whoami_info is not None else client.whoami()
        user = info.get('user_info', {})
        return term.fmt_name(user, default=info.get('user_unique_id') or '?')
    except Exception:
        return '?'


def fetch_current_project():
    """Return the current project ID from config."""
    try:
        from crucible.config import config
        return config.current_project or None
    except Exception:
        return None


def fetch_project_context():
    """Return the configured project ID and its source."""
    try:
        from crucible.config import config
        project_id = config.current_project or None
        return project_id, config.source('current_project') if project_id else None
    except Exception:
        return None, None


def resolve_project_context(args=None, project_id=None):
    """Return the effective CLI project ID and its source."""
    if project_id:
        return project_id, 'argument'
    shell_state = getattr(args, '_shell_state', None) if args is not None else None
    if shell_state is not None:
        shell_project = shell_state.get('project')
        if shell_project:
            return shell_project, shell_state.get('project_source') or 'config file'
    project_id, source = fetch_project_context()
    if project_id and source == 'environment':
        import warnings
        warnings.warn(
            "CRUCIBLE_CURRENT_PROJECT is deprecated because it can silently redirect operations. "
            "Use an explicit --project-id or save the current project with the interactive shell.",
            FutureWarning,
            stacklevel=2,
        )
    return project_id, source


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


def fetch_api_attention():
    """Return whether the configured API differs from the package default."""
    try:
        from crucible.config import config
        from crucible.config.config import Config
        return config.api_url.rstrip('/') != Config.DEFAULT_API_URL.rstrip('/')
    except Exception:
        return False


def explorer_url(resource_id: str, project_id: str, resource_type: str) -> str:
    """Build a graph explorer URL for a dataset or sample.

    Returns None if the graph_explorer_url is not configured or any argument is missing.
    """
    base = _graph_explorer_base()
    if not base or not resource_id or not project_id:
        return None
    dtype = 'samples' if resource_type == 'sample' else 'datasets'
    return f"{base}/{project_id}/{dtype}/{resource_id}"


def _graph_explorer_base():
    try:
        from crucible.config import config
        return (config.graph_explorer_url or '').rstrip('/') or None
    except Exception:
        return None


def project_explorer_url(project_id: str) -> str:
    """Build the Graph Explorer URL for a project."""
    base = _graph_explorer_base()
    if not base or not project_id:
        return None
    return f"{base}/{project_id}/"


def instrument_explorer_url(instrument_mfid: str) -> str:
    """Build the Graph Explorer URL for an instrument."""
    base = _graph_explorer_base()
    if not base or not instrument_mfid:
        return None
    return f"{base}/instrument/{instrument_mfid}"


def user_explorer_url(user_unique_id: str) -> str:
    """Build the Graph Explorer URL for a user."""
    base = _graph_explorer_base()
    if not base or not user_unique_id:
        return None
    return f"{base}/user/{user_unique_id}"


def project_reference(resource):
    """Return the display title, project ID, and Explorer URL for a resource."""
    reference = resource.get('project') or {}
    project_id = reference.get('project_id') or resource.get('project_id')
    return (
        reference.get('title'),
        project_id,
        project_explorer_url(project_id),
    )


def instrument_reference(resource):
    """Return the display name, instrument ID, and Explorer URL for a dataset."""
    reference = resource.get('instrument') or {}
    instrument_mfid = reference.get('unique_id')
    return (
        reference.get('instrument_name') or resource.get('instrument_name'),
        reference.get('instrument_id') or resource.get('instrument_id'),
        instrument_explorer_url(instrument_mfid),
    )


def cast_value(value: str):
    """Auto-cast a string value to int, float, bool, or string."""
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_metadata(value: str) -> dict:
    """Parse a metadata arg: JSON string or path to a JSON file.

    Args:
        value: Raw string from --metadata CLI argument.

    Returns:
        dict: Parsed metadata.

    Raises:
        ValueError: If the string is not valid JSON and no such file exists.
    """
    import json
    from pathlib import Path
    p = Path(value)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file {p}: {e}") from e
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        raise ValueError(f"'{value}' is not valid JSON and no such file exists.")


def show_scientific_metadata(sci_md):
    """Display scientific metadata dict under a subheader."""
    from . import term
    term.subheader(f"Scientific Metadata ({len(sci_md) if sci_md else 0} fields)")
    if not sci_md:
        print(f"  {term.dim('(none)')}")
        return
    max_key = max(len(k) for k in sci_md)
    for k, v in sorted(sci_md.items()):
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in sorted(v.items()):
                print(f"    {kk}: {vv}")
        elif isinstance(v, list) and len(v) > 8:
            print(f"  {k:<{max_key}}  <list with {len(v)} items>")
        else:
            print(f"  {k:<{max_key}}  {v}")


def cache_resource(shell_state, client, data, rtype, resource_id, **flags):
    """Cache a fetched resource in the shell state and start background prefetches.

    For datasets, prefetches links, keywords, associated files, and download
    links in parallel so Alt+V / Alt+G can re-render without extra API calls.
    For samples, only links are prefetched.

    Args:
        shell_state: The shell's mutable state dict (args._shell_state), or
                     None when running outside the interactive shell.
        client:      CrucibleClient instance.
        data:        The fetched resource dict.
        rtype:       Resource type string, 'dataset' or 'sample'.
        resource_id: MFID of the resource.
        **flags:     Additional keys stored in last_resource (verbose, graph,
                     include_metadata, etc.).
    """
    if shell_state is None:
        return

    # Track recently visited MFIDs for shell tab completion.
    recent = shell_state.get('recent_mfids')
    if recent is not None:
        name_key = {'dataset': 'dataset_name', 'sample': 'sample_name',
                    'instrument': 'instrument_name'}.get(rtype, 'name')
        name = data.get(name_key) or ''
        for i, (uid, _, _) in enumerate(recent):
            if uid == resource_id:
                del recent[i]
                break
        recent.appendleft((resource_id, name, rtype))

    if rtype == 'dataset':
        pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='prefetch')
        futures = {
            '_keywords_future': pool.submit(client.datasets.get_keywords, resource_id),
            '_files_future':    pool.submit(client.datasets.list_files, resource_id),
            '_dl_links_future': pool.submit(client.datasets.get_download_links, resource_id),
        }
        if not data.get('links'):
            futures['_links_future'] = pool.submit(client.get_links, resource_id)
    elif rtype == 'sample':
        futures = {}
        if not data.get('links'):
            pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='prefetch')
            futures['_links_future'] = pool.submit(client.get_links, resource_id)
    else:
        futures = {}

    if futures:
        pool.shutdown(wait=False)
    shell_state['last_resource'] = {
        'data': data, 'type': rtype, **futures, **flags
    }


def show_transfer_ownership(result, confirm: bool) -> None:
    """Print the preview or outcome of a BaseResource.transfer_ownership() call."""
    from . import term
    prev = result.previous_owner
    prev_name = term.fmt_name(prev.model_dump(), default=prev.unique_id) if prev else '-'
    new_name = term.fmt_name(result.new_owner.model_dump(), default=result.new_owner.unique_id)
    if confirm:
        term.success(f"Ownership of {result.resource_id} transferred: {prev_name} -> {new_name}")
    else:
        logger.info(f"Preview: ownership of {result.resource_id} would transfer from {prev_name} to {new_name}")
        logger.info("Re-run with --confirm to execute.")


_ROLE_RANK = {'owner': 5, 'admin': 4, 'editor': 3, 'contributor': 2, 'viewer': 1}


def sort_members(members) -> list:
    """Sort a list of ProjectMember objects (or user/role dicts) by role rank
    (owner first, per the VIEWER < CONTRIBUTOR < EDITOR < ADMIN < OWNER
    hierarchy), then alphabetically by name/username. Unrecognized roles sort last.
    """
    from . import term

    def key(m):
        d = m.model_dump() if hasattr(m, 'model_dump') else m
        rank = _ROLE_RANK.get((d.get('role') or '').lower(), 0)
        name = term.fmt_name(d, default='') or ''
        return (-rank, name.lower())

    return sorted(members, key=key)


def show_reassign_project(result, confirm: bool) -> None:
    """Print the preview or outcome of a BaseResource.reassign_project() call."""
    prev = result.previous_project_id or '-'
    if confirm:
        from . import term
        term.success(f"{result.resource_id} moved from project '{prev}' to '{result.new_project_id}'")
    else:
        logger.info(f"Preview: {result.resource_id} would move from project '{prev}' to '{result.new_project_id}'")
        logger.info("Re-run with --confirm to execute.")
