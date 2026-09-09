#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

import argparse
import os
import sys
import re as _re
import time
import html as _html
import shlex
import shutil
import threading
import itertools
import logging
from collections import deque
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from . import term

logger = logging.getLogger(__name__)

_PROMPT = "crucible> "
_BRAND_DARK_BLUE = '#031e2d'
_BRAND_LIGHT_BLUE = '#a8c4cd'
_BRAND_ORANGE = '#ff6600'
_BRAND_OFF_WHITE = '#eeeeee'
_BANNER_MIN_WIDTH = 16
_BANNER_PIXEL_COLORS = {
    '_': _BRAND_LIGHT_BLUE,
    '%': _BRAND_DARK_BLUE,
    '=': _BRAND_ORANGE,
    '.': _BRAND_OFF_WHITE,
}


def _get_subparser_map(parser):
    """Return {name: subparser} for a parser's subcommands, or {} if none."""
    for action in parser._actions:
        if hasattr(action, 'choices') and isinstance(action.choices, dict):
            return action.choices or {}
    return {}


def _vlen(s):
    """Visual (terminal column) width of s; falls back to len() if wcwidth unavailable."""
    try:
        from wcwidth import wcswidth
        w = wcswidth(s)
        return w if w >= 0 else len(s)
    except ImportError:
        return len(s)


_ENTITY_ICONS = {
    'dataset':    '<ansibrightblack><b>[ds]</b></ansibrightblack>',
    'sample':     '<ansibrightblack><b>[s]</b></ansibrightblack>',
    'instrument': '<ansibrightblack><b>[i]</b></ansibrightblack>',
}


try:
    from prompt_toolkit.completion     import Completer, Completion
    from prompt_toolkit.formatted_text import HTML as _HTML

    def _shell_html(markup):
        if not term.color_enabled():
            markup = _re.sub(r'</?[^>]+>', '', markup)
        return _HTML(markup)

    def _shell_style_rules():
        if not term.color_enabled():
            return {
                'bottom-toolbar':      'noinherit',
                'bottom-toolbar.text': 'noinherit',
                'tb-project':          'noinherit',
                'tb-separator':        'noinherit',
                'tb-api':              'noinherit',
                'tb-api-attention':    'noinherit',
                'tb-clock':            'noinherit',
                'tb-debug':            'noinherit',
            }
        return {
            'bottom-toolbar':      f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_LIGHT_BLUE}',
            'bottom-toolbar.text': f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_LIGHT_BLUE}',
            'tb-project':          f'noinherit bg:{_BRAND_LIGHT_BLUE} fg:{_BRAND_DARK_BLUE}',
            'tb-separator':        f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_ORANGE}',
            'tb-api':              f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_LIGHT_BLUE}',
            'tb-api-attention':    f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_ORANGE} bold',
            'tb-clock':            f'noinherit bg:{_BRAND_DARK_BLUE} fg:{_BRAND_LIGHT_BLUE}',
            'tb-debug':            f'noinherit bg:{_BRAND_ORANGE} fg:{_BRAND_DARK_BLUE} bold',
        }

    def _shell_color_depth():
        from prompt_toolkit.output import ColorDepth

        if not term.color_enabled():
            return ColorDepth.DEPTH_1_BIT
        configured = ColorDepth.from_env()
        if configured is not None:
            return configured
        if os.environ.get('COLORTERM', '').lower() in ('truecolor', '24bit'):
            return ColorDepth.DEPTH_24_BIT
        return None

    def _load_shell_banner():
        try:
            from importlib.resources import files
        except ImportError:
            from importlib.resources import read_text
            return read_text('crucible.cli', 'crucible_ascii.txt').rstrip('\n')
        return files('crucible.cli').joinpath('crucible_ascii.txt').read_text().rstrip('\n')

    def _shell_banner_rows(banner):
        lines = banner.splitlines()
        width = max(map(len, lines), default=0)
        return [line.ljust(width, '_') for line in lines]

    def _shell_banner_row_pairs(banner):
        rows = _shell_banner_rows(banner)
        if len(rows) % 2:
            rows.append('_' * len(rows[0]))
        return zip(rows[::2], rows[1::2])

    def _shell_banner_panel(banner):
        visible_pixels = frozenset('%=')
        return '\n'.join(
            ''.join(
                '█' if upper in visible_pixels and lower in visible_pixels
                else '▀' if upper in visible_pixels
                else '▄' if lower in visible_pixels
                else ' '
                for upper, lower in zip(upper_row, lower_row)
            )
            for upper_row, lower_row in _shell_banner_row_pairs(banner)
        )

    def _shell_banner_left_margin(panel, columns):
        width = max((_vlen(line) for line in panel.splitlines()), default=0)
        return max((columns - width) // 2, 0)

    def _shell_banner_fragments(banner, left_margin=0):
        from prompt_toolkit.formatted_text import FormattedText

        fragments = []
        pairs = list(_shell_banner_row_pairs(banner))
        for row_index, (upper_row, lower_row) in enumerate(pairs):
            if left_margin:
                fragments.append(('', ' ' * left_margin))
            for upper, lower in zip(upper_row, lower_row):
                upper_color = _BANNER_PIXEL_COLORS[upper]
                lower_color = _BANNER_PIXEL_COLORS[lower]
                if upper_color == lower_color:
                    style = f'bg:{lower_color}'
                    text = ' '
                else:
                    style = f'fg:{upper_color} bg:{lower_color}'
                    text = '▀'
                if fragments and fragments[-1][0] == style:
                    previous_style, previous_text = fragments[-1]
                    fragments[-1] = (previous_style, previous_text + text)
                else:
                    fragments.append((style, text))
            if row_index < len(pairs) - 1:
                fragments.append(('', '\n'))
        return FormattedText(fragments)

    def _print_shell_banner(columns):
        if columns < _BANNER_MIN_WIDTH:
            return False
        banner = _load_shell_banner()
        panel = _shell_banner_panel(banner)
        left_margin = _shell_banner_left_margin(panel, columns)
        if not term.color_enabled():
            prefix = ' ' * left_margin
            print('\n'.join(f'{prefix}{line}' for line in panel.splitlines()))
            return True
        from prompt_toolkit import print_formatted_text
        print_formatted_text(
            _shell_banner_fragments(banner, left_margin=left_margin),
            color_depth=_shell_color_depth(),
        )
        return True

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource -> subcommand -> flags."""

        def __init__(self, parser, client=None, projects=None, deletions=None,
                     join_requests=None, service_accounts=None, state=None):
            self._top               = _get_subparser_map(parser)
            self._client            = client
            self._projects          = projects  or []
            self._deletions         = deletions or []
            self._join_requests     = join_requests or []
            self._service_accounts  = service_accounts or []
            self._unlink_cache      = {}  # mfid -> [(uid, name, entity_type), ...]
            self._user_search_cache = {}  # query -> [(username, name, orcid), ...]
            self._entity_search_cache = {}  # (entity_type, project_id, query) -> [(uid, name), ...]
            self._project_search_cache = {}
            self._instrument_search_cache = {}
            self._state             = state or {}

        def _lazy_projects(self):
            if not self._projects and self._client is not None:
                from .helpers import fetch_projects
                self._projects = fetch_projects(self._client)
            return self._projects

        def _search_users(self, query):
            """Search users by name/username via the public search endpoint (no admin required).

            Cached per exact query string for the session — cheap and avoids
            re-hitting the API on every keystroke once a prefix was searched.

            Returns [(identifier, name, orcid), ...] where identifier is the
            username if set, else the ORCID (always present, server-assigned) —
            so a matched user is never silently dropped just for lacking a
            username. Callers can tell which case they're in: identifier ==
            orcid means there's no username.
            """
            if query in self._user_search_cache:
                return self._user_search_cache[query]
            results = []
            if self._client is not None:
                try:
                    for u in self._client.users.search(query):
                        orcid = u.get('unique_id') or ''
                        if not orcid:
                            continue
                        identifier = u.get('username') or orcid
                        name = term.fmt_name(u, default='', fallback_username=False)
                        results.append((identifier, name, orcid))
                except Exception:
                    pass
            self._user_search_cache[query] = results
            return results

        def _yield_user_completions(self, prefix):
            """Yield completions for a user-identifier argument: username where
            set, ORCID as a fallback for users without one.

            Requires 3+ characters (matches the `crucible user search` minimum)
            since this hits the live search endpoint rather than a local cache.
            The API does fuzzy/typo-tolerant matching server-side (e.g. "faber"
            -> "roncofaber"), so results aren't re-filtered by prefix here.
            """
            if len(prefix) < 3:
                return
            for identifier, name, orcid in self._search_users(prefix):
                meta = f'{name}  ' if name else ''
                # Only show the ORCID as metadata when it's not already the
                # completion value itself (i.e. the user has a real username).
                meta_orcid = orcid if identifier != orcid else ''
                yield Completion(
                    identifier + ' ',
                    start_position=-len(prefix),
                    display=_shell_html(f'<b>{_html.escape(identifier)}</b>'),
                    display_meta=_shell_html(f'<ansibrightblack>{_html.escape(meta)}{_html.escape(meta_orcid)}</ansibrightblack>'),
                )

        def _search_projects(self, query):
            if query in self._project_search_cache:
                return self._project_search_cache[query]
            results = []
            if self._client is not None:
                try:
                    for project in self._client.projects.search(query, limit=20):
                        project_id = project.get('project_id') or ''
                        if project_id:
                            results.append((
                                project_id,
                                project.get('title') or '-',
                                project.get('unique_id') or '',
                            ))
                except Exception:
                    pass
            self._project_search_cache[query] = results
            return results

        def _yield_project_completions(self, prefix, use_search=True, use_mfid=False):
            if use_mfid and len(prefix) < 3:
                return
            if (use_search or use_mfid) and len(prefix) >= 3:
                candidates = self._search_projects(prefix)
            else:
                prefix_lower = prefix.lower()
                candidates = [
                    (project_id, title, '')
                    for project_id, title in self._lazy_projects()
                    if project_id.lower().startswith(prefix_lower)
                ]
            for project_id, title, unique_id in candidates:
                value = unique_id if use_mfid else project_id
                if not value:
                    continue
                metadata_id = project_id if use_mfid else unique_id
                metadata = f'{title}  {metadata_id}' if metadata_id else title
                yield Completion(
                    value + ' ',
                    start_position=-len(prefix),
                    display=_shell_html(f'<b>{_html.escape(value)}</b>'),
                    display_meta=_shell_html(
                        f'<ansibrightblack>{_html.escape(metadata)}</ansibrightblack>'
                    ),
                )

        def _search_instruments(self, query):
            if query in self._instrument_search_cache:
                return self._instrument_search_cache[query]
            results = []
            if self._client is not None:
                try:
                    for instrument in self._client.instruments.search(query, limit=20):
                        unique_id = instrument.get('unique_id') or ''
                        instrument_id = instrument.get('instrument_id') or ''
                        if unique_id and instrument_id:
                            results.append((
                                instrument_id,
                                instrument.get('instrument_name') or '-',
                                unique_id,
                            ))
                except Exception:
                    pass
            self._instrument_search_cache[query] = results
            return results

        def _yield_instrument_completions(self, prefix, use_mfid=False):
            if len(prefix) < 3:
                return
            for instrument_id, name, unique_id in self._search_instruments(prefix):
                value = unique_id if use_mfid else instrument_id
                metadata = f'{name}  {instrument_id if use_mfid else unique_id}'
                yield Completion(
                    value + ' ',
                    start_position=-len(prefix),
                    display=_shell_html(f'<b>{_html.escape(value)}</b>'),
                    display_meta=_shell_html(
                        f'<ansibrightblack>{_html.escape(metadata)}</ansibrightblack>'
                    ),
                )

        def _search_entities(self, entity_type, query, project_id=None):
            """Search datasets or samples by name via the public search endpoint.

            Cached per (entity_type, project_id, query) for the session.
            Returns [(unique_id, name), ...].
            """
            key = (entity_type, project_id, query)
            if key in self._entity_search_cache:
                return self._entity_search_cache[key]
            results = []
            if self._client is not None:
                try:
                    resource   = getattr(self._client, entity_type)  # 'datasets' or 'samples'
                    name_field = 'dataset_name' if entity_type == 'datasets' else 'sample_name'
                    for r in resource.search(query, project_id=project_id):
                        uid = r.get('unique_id') or ''
                        if uid:
                            results.append((uid, r.get(name_field) or '(unnamed)'))
                except Exception:
                    pass
            self._entity_search_cache[key] = results
            return results

        def _yield_entity_completions(self, entity_type, arg_text, query, icon):
            """Yield MFID completions (displayed by name) for a dataset/sample name argument.

            Below the 3-char search minimum, falls back to recently-viewed
            entities of this type from session history instead of live search.
            """
            if len(query) < 3:
                for uid, name, rtype in self._state.get('recent_mfids', []):
                    if rtype == entity_type.rstrip('s') and query.lower() in name.lower():
                        yield Completion(
                            uid + ' ',
                            start_position=-len(arg_text),
                            display=_shell_html(f'<b>{_html.escape(uid)}</b>'),
                            display_meta=_shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                        )
                return
            project_id = self._state.get('project')
            for uid, name in self._search_entities(entity_type, query, project_id=project_id):
                yield Completion(
                    uid + ' ',
                    start_position=-len(arg_text),
                    display=_shell_html(f'<b>{_html.escape(uid)}</b>'),
                    display_meta=_shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                )

        @staticmethod
        def _multiword_arg(text, num_preceding_words):
            """Extract the raw text typed for a positional argument that may
            contain spaces (e.g. an instrument or dataset name), given the
            number of complete words before it (resource + subcommand, etc).

            Returns (arg_text, query): arg_text is the exact trailing text
            (used for start_position so a Completion replaces it precisely),
            query is arg_text with trailing whitespace stripped (what to
            search for). Returns None if that argument hasn't been reached
            yet, or if a flag (a token starting with '-') appears in it,
            meaning the positional was already completed and a flag started.
            """
            parts = text.split(' ', num_preceding_words)
            if len(parts) <= num_preceding_words:
                return None
            arg_text = parts[num_preceding_words]
            if any(tok.startswith('-') for tok in arg_text.split(' ') if tok):
                return None
            return arg_text, arg_text.rstrip()

        def _unlink_neighbors(self, mfid):
            """Return [(uid, name, entity_type)] of entities directly linked to mfid (cached)."""
            if mfid in self._unlink_cache:
                return self._unlink_cache[mfid]
            try:
                graph  = self._client.graphs.get(mfid, recursive=False)
                result = [
                    (node['id'], node.get('name') or '', node.get('entity_type') or '')
                    for node in graph.get('nodes', [])
                    if node.get('id') != mfid
                ]
                self._unlink_cache[mfid] = result
            except Exception:
                result = []
            return result

        # Dispatch table for get_completions(): resource name(s) -> handler method
        # name. Each handler is a generator that yields Completions and returns
        # True if it fully handled the request, or False to fall through to the
        # next matching handler and eventually the generic subcommand/flag
        # completion in _complete_generic(). Order matters only in that a
        # resource name should appear in exactly one entry (verified: no overlaps).
        _RESOURCE_HANDLERS = {
            'debug':           '_complete_debug',
            'use':             '_complete_use',
            'deletion':        '_complete_deletion',
            'ag':              '_complete_access_group',
            'access-group':    '_complete_access_group',
            'sa':              '_complete_service_account',
            'service-account': '_complete_service_account',
            'unlink':          '_complete_unlink',
            'get':             '_complete_recent_mfid',
            'edit':            '_complete_recent_mfid',
            'open':            '_complete_recent_mfid',
            'tree':            '_complete_recent_mfid',
            'user':            '_complete_user',
            'project':         '_complete_project',
            'instrument':      '_complete_instrument',
            'dataset':         '_complete_dataset_or_sample',
            'sample':          '_complete_dataset_or_sample',
            'cast':            '_complete_path',
            'cd':              '_complete_path',
            'ls':              '_complete_path',
        }

        def get_completions(self, document, complete_event):
            text           = document.text_before_cursor
            words          = text.split()
            trailing_space = text.endswith(' ')

            if not words or (len(words) == 1 and not trailing_space):
                prefix = words[0] if words else ''
                candidates = list(self._top) + ['use', 'unuse', 'refresh', 'reload', 'debug', 'cd', 'ls', 'pwd']
                for name in candidates:
                    if name.startswith(prefix):
                        yield Completion(name + ' ', start_position=-len(prefix))
                return

            resource = words[0]
            ctx = (text, words, trailing_space, resource)

            handler_name = self._RESOURCE_HANDLERS.get(resource)
            if handler_name:
                handled = yield from getattr(self, handler_name)(ctx)
                if handled:
                    return

            yield from self._complete_generic(ctx)

        def _complete_debug(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) > 2:
                return True
            prefix = words[1] if len(words) == 2 and not trailing_space else ''
            for choice in ('on', 'off'):
                if choice.startswith(prefix):
                    yield Completion(choice + ' ', start_position=-len(prefix))
            return True

        def _complete_use(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) > 2 or (trailing_space and len(words) == 2):
                return True
            prefix = words[1] if len(words) == 2 else ''
            yield from self._yield_project_completions(prefix, use_search=False)
            return True

        def _complete_deletion(self, ctx):
            text, words, trailing_space, resource = ctx
            if not (len(words) >= 2 and words[1] in ('approve', 'reject', 'get')):
                return False
            already = set(words[2:]) if trailing_space else set(words[2:-1])
            prefix  = '' if trailing_space else words[-1]
            for d in self._deletions:
                did = str(d.get('id', ''))
                if did in already or not did.startswith(prefix):
                    continue
                rtype  = d.get('resource_type') or ''
                name   = (d.get('resource_name') or '')[:15]
                reason = (d.get('reason') or '')[:24]
                parts  = []
                if rtype:
                    parts.append(f'{rtype}')
                if name:
                    parts.append(f'<b>{_html.escape(name)}</b>')
                if reason:
                    parts.append(f'<ansibrightblack>{_html.escape(reason)}</ansibrightblack>')
                yield Completion(
                    did + ' ',
                    start_position=-len(prefix),
                    display=_shell_html(f'<b>{did}</b>'),
                    display_meta=_shell_html(' | '.join(parts)),
                )
            return True

        def _complete_access_group(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) >= 2 and words[1] in ('approve', 'reject', 'get'):
                already = set(words[2:]) if trailing_space else set(words[2:-1])
                prefix  = '' if trailing_space else words[-1]
                for jr in self._join_requests:
                    jid = str(jr.get('id', ''))
                    if jid in already or not jid.startswith(prefix):
                        continue
                    group  = jr.get('group_name') or ''
                    reason = (jr.get('reason') or '')[:24]
                    parts  = []
                    if group:
                        parts.append(f'<b>{_html.escape(group)}</b>')
                    if reason:
                        parts.append(f'<ansibrightblack>{_html.escape(reason)}</ansibrightblack>')
                    yield Completion(
                        jid + ' ',
                        start_position=-len(prefix),
                        display=_shell_html(f'<b>{jid}</b>'),
                        display_meta=_shell_html(' | '.join(parts)),
                    )
                return True

            if len(words) >= 2 and words[1] == 'request':
                # Complete the GROUP positional (currently always a project_id).
                if trailing_space and len(words) == 2:
                    prefix = ''
                elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                    prefix = words[2]
                else:
                    return True  # GROUP already filled
                yield from self._yield_project_completions(prefix)
                return True

            return False

        def _complete_service_account(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) < 2:
                return False
            # Complete the SA positional (MFID or username) for subcommands that take one.
            _SA_SUBS = {'get', 'rotate-key', 'edit', 'update', 'list-access-groups',
                        'add-access-group', 'remove-access-group'}
            if words[1] not in _SA_SUBS:
                return False
            if trailing_space and len(words) == 2:
                prefix = ''
            elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                prefix = words[2]
            else:
                return False
            yield from self._yield_service_account_completions(prefix)
            return True

        def _yield_service_account_completions(self, prefix):
            prefix_lower = prefix.lower()
            for sa in self._service_accounts:
                username = sa.get('username') or ''
                if not username.lower().startswith(prefix_lower):
                    continue
                name = term.fmt_name(sa, default='', fallback_username=False)
                yield Completion(
                    username + ' ',
                    start_position=-len(prefix),
                    display=_shell_html(f'<b>{_html.escape(username)}</b>'),
                    display_meta=_shell_html(f'<ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                )

        def _complete_unlink(self, ctx):
            text, words, trailing_space, resource = ctx
            if self._client is None:
                return False
            # Positional form: unlink MFID1 MFID2
            # Complete MFID2 from the graph neighbors of MFID1.
            first = None
            prefix = ''
            if trailing_space and len(words) == 2 and not words[1].startswith('-'):
                first, prefix = words[1], ''
            elif not trailing_space and len(words) == 3 \
                    and not words[1].startswith('-') and not words[2].startswith('-'):
                first, prefix = words[1], words[2]
            if not first:
                return False
            for uid, name, etype in self._unlink_neighbors(first):
                if uid.startswith(prefix):
                    icon_html = _ENTITY_ICONS.get(etype, '<ansibrightblack>[?]</ansibrightblack>')
                    meta = f'{icon_html} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'
                    yield Completion(
                        uid + ' ',
                        start_position=-len(prefix),
                        display=_shell_html(f'<b>{_html.escape(uid)}</b>'),
                        display_meta=_shell_html(meta),
                    )
            return True

        def _complete_recent_mfid(self, ctx):
            text, words, trailing_space, resource = ctx
            # Complete the first positional MFID from recently visited resources.
            if trailing_space and len(words) == 1:
                prefix = ''
                for uid, name, rtype in self._state.get('recent_mfids', []):
                    if uid.startswith(prefix):
                        icon = _ENTITY_ICONS.get(rtype, '<ansibrightblack>[?]</ansibrightblack>')
                        yield Completion(
                            uid + ' ',
                            start_position=-len(prefix),
                            display=_shell_html(f'<b>{_html.escape(uid)}</b>'),
                            display_meta=_shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                        )
                return True
            elif not trailing_space and len(words) == 2 and not words[1].startswith('-'):
                prefix = words[1]
                for uid, name, rtype in self._state.get('recent_mfids', []):
                    if uid.startswith(prefix):
                        icon = _ENTITY_ICONS.get(rtype, '<ansibrightblack>[?]</ansibrightblack>')
                        yield Completion(
                            uid + ' ',
                            start_position=-len(prefix),
                            display=_shell_html(f'<b>{_html.escape(uid)}</b>'),
                            display_meta=_shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                        )
                return True
            # ID already filled — complete flags from the top-level parser
            parser = self._top.get(resource)
            if parser:
                current_word = '' if trailing_space else words[-1]
                for flag in parser._option_string_actions:
                    if flag.startswith(current_word):
                        yield Completion(flag + ' ', start_position=-len(current_word))
            return True

        def _complete_user(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) < 2:
                return False
            # Complete the USER positional (ORCID/username/email) by username search.
            # 'search' is included too — TERM is free text, but showing live
            # matches while typing is useful preview, not just identifier lookup.
            _USER_SUBS = {'get', 'update', 'edit', 'add-access-group', 'remove-access-group',
                          'list-datasets', 'check-access', 'list-access-groups', 'list-projects',
                          'search'}
            if words[1] not in _USER_SUBS:
                return False
            if trailing_space and len(words) == 2:
                prefix = ''
            elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                prefix = words[2]
            else:
                return False
            yield from self._yield_user_completions(prefix)
            return True

        def _complete_project(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) < 2:
                return False
            # Complete the PROJECT_ID positional for subcommands that take one.
            _PID_SUBS = {
                'get', 'update', 'list-users', 'add-user', 'remove-user',
                'update-user-role', 'transfer-ownership', 'request-join',
                'list-join-requests',
            }
            if words[1] not in _PID_SUBS:
                return False
            subcommand = words[1]
            if trailing_space and len(words) == 2:
                prefix = ''
            elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                prefix = words[2]
            else:
                if subcommand in {'transfer-ownership', 'update-user-role'}:
                    if not trailing_space and len(words) == 4:
                        yield from self._yield_user_completions(words[3])
                        return True
                    if subcommand == 'update-user-role':
                        roles = ('viewer', 'contributor', 'editor', 'admin')
                        if trailing_space and len(words) == 4:
                            for role in roles:
                                yield Completion(role + ' ', start_position=0)
                            return True
                        if not trailing_space and len(words) == 5:
                            for role in roles:
                                if role.startswith(words[4]):
                                    yield Completion(
                                        role + ' ', start_position=-len(words[4]))
                            return True
                return False
            yield from self._yield_project_completions(prefix)
            return True

        def _complete_instrument(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) < 2:
                return False
            subcommand = words[1]
            mfid_subcommands = {
                'update', 'edit', 'transfer-ownership', 'set-status',
                'list-service-accounts', 'bind-sa', 'unbind-sa',
            }
            if subcommand == 'get':
                span = self._multiword_arg(text, 2)
                if span is None:
                    return False
                _, query = span
                yield from self._yield_instrument_completions(query)
                return True
            if subcommand not in mfid_subcommands:
                return False
            if trailing_space and len(words) == 2:
                yield from self._yield_instrument_completions('', use_mfid=True)
                return True
            if not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                yield from self._yield_instrument_completions(words[2], use_mfid=True)
                return True
            if subcommand == 'transfer-ownership' and not trailing_space and len(words) == 4:
                yield from self._yield_user_completions(words[3])
                return True
            if subcommand in {'bind-sa', 'unbind-sa'}:
                if trailing_space and len(words) == 3:
                    yield from self._yield_service_account_completions('')
                    return True
                if not trailing_space and len(words) == 4:
                    yield from self._yield_service_account_completions(words[3])
                    return True
            if subcommand == 'set-status':
                statuses = ('active', 'maintenance', 'decommissioned')
                if trailing_space and len(words) == 3:
                    for status in statuses:
                        yield Completion(status + ' ', start_position=0)
                    return True
                if not trailing_space and len(words) == 4:
                    for status in statuses:
                        if status.startswith(words[3]):
                            yield Completion(
                                status + ' ', start_position=-len(words[3]))
                    return True
            return False

        def _complete_dataset_or_sample(self, ctx):
            text, words, trailing_space, resource = ctx
            if len(words) < 2:
                return False
            # Complete the ID positional (by name, resolving to MFID) for
            # every subcommand except the handful that don't take one.
            _NO_ID_SUBS = {
                'list', 'create', 'search', 'search-metadata', 'search-md',
                'link', 'parsers', 'ingestors',
            }
            if words[1] in _NO_ID_SUBS:
                return False
            from ..utils.identifiers import is_mfid
            subcommand = words[1]
            if len(words) >= 3 and is_mfid(words[2]):
                if subcommand == 'reassign-project':
                    if trailing_space and len(words) == 3:
                        yield from self._yield_project_completions('')
                        return True
                    if not trailing_space and len(words) == 4:
                        yield from self._yield_project_completions(words[3])
                        return True
                if subcommand == 'transfer-ownership':
                    if not trailing_space and len(words) == 4:
                        yield from self._yield_user_completions(words[3])
                        return True
                return False
            span = self._multiword_arg(text, 2)
            if span is None:
                # Positional already filled (a flag followed) — fall through
                # to flag completion in _complete_generic().
                return False
            arg_text, query = span
            entity_type = 'datasets' if resource == 'dataset' else 'samples'
            icon = _ENTITY_ICONS.get(resource, '')
            yield from self._yield_entity_completions(entity_type, arg_text, query, icon)
            return True

        def _complete_path(self, ctx):
            text, words, trailing_space, resource = ctx
            current = (words[1] if len(words) == 2 and not trailing_space else
                       '' if trailing_space and len(words) == 1 else None)
            if current is not None and not current.startswith('-'):
                expanded   = os.path.expanduser(current)
                search_dir = os.path.dirname(expanded) or '.'
                prefix     = os.path.basename(expanded)

                results = []

                # For cd: always offer '..' when at a directory boundary
                if resource == 'cd' and '..'.startswith(prefix):
                    remaining = '..'[len(prefix):]
                    results.append((False, '', Completion(
                        remaining + '/',
                        start_position=0,
                        display=_shell_html('<ansicyan><b>../</b></ansicyan>'),
                    )))

                try:
                    scan = os.scandir(search_dir)
                except (PermissionError, FileNotFoundError):
                    return True

                with scan:
                    for entry in scan:
                        if not entry.name.startswith(prefix):
                            continue
                        is_dir    = entry.is_dir(follow_symlinks=True)
                        is_hidden = entry.name.startswith('.')
                        is_crux   = entry.name.endswith('.crux')

                        if resource == 'cd'   and not is_dir:   continue
                        if resource == 'cast' and not (is_dir or is_crux): continue

                        display_name    = entry.name + ('/' if is_dir else '')
                        completion_text = entry.name[len(prefix):] + ('/' if is_dir else '')
                        esc = _html.escape(display_name)

                        if is_dir:
                            disp = f'<ansicyan><b>{esc}</b></ansicyan>'
                        elif is_crux:
                            disp = f'<b>{esc}</b>'
                        elif is_hidden:
                            disp = f'<ansibrightblack>{esc}</ansibrightblack>'
                        else:
                            disp = esc

                        results.append((is_hidden, display_name.lower(), Completion(
                            completion_text,
                            start_position=0,
                            display=_shell_html(disp),
                        )))

                results.sort(key=lambda x: (x[0], x[1]))
                yield from (c for _, _, c in results)
                return True

            # Flag completion for cast
            if resource == 'cast':
                current_word = '' if trailing_space else words[-1]
                if current_word.startswith('-'):
                    cast_parser = self._top.get('cast')
                    if cast_parser:
                        for flag in cast_parser._option_string_actions:
                            if flag.startswith(current_word):
                                yield Completion(flag + ' ', start_position=-len(current_word))
            return True

        def _complete_generic(self, ctx):
            """Fallback completion shared by every resource: subcommand names,
            then (for dataset/sample/user flag values) dynamic flag values,
            then plain flag names from the matched subparser.
            """
            text, words, trailing_space, resource = ctx

            sub_map = _get_subparser_map(self._top.get(resource)) \
                      if resource in self._top else {}

            if len(words) == 1 or (len(words) == 2 and not trailing_space):
                prefix = words[1] if len(words) == 2 else ''
                for name in sub_map:
                    if name.startswith(prefix):
                        yield Completion(name + ' ', start_position=-len(prefix))
                return

            subcommand = words[1]

            if resource == 'config' and subcommand == 'set':
                try:
                    from crucible.config.config import Config as _Cfg
                    config_keys = list(_Cfg._CONFIG_MAP)
                except Exception:
                    return
                if not (len(words) == 3 and trailing_space) and len(words) <= 3:
                    prefix = words[2] if len(words) == 3 else ''
                    for key in config_keys:
                        if key.startswith(prefix):
                            yield Completion(key + ' ', start_position=-len(prefix))
                elif len(words) >= 3 and words[2] == 'current_project':
                    prefix = words[3] if len(words) == 4 and not trailing_space else ''
                    yield from self._yield_project_completions(prefix, use_search=False)
                return

            sub_parser  = sub_map.get(subcommand)
            if sub_parser is None:
                return

            current_word = '' if trailing_space else words[-1]
            prev = (words[-1] if trailing_space else words[-2]) if len(words) >= 2 else ''

            _PROJECT_FLAGS = ('--project-id', '--project', '-pid')
            _PROJECT_MFID_FLAGS = ('--project-mfid',)
            if subcommand in {'list', 'create', 'search'}:
                _PROJECT_FLAGS += ('-p',)
            _USER_FLAGS = ('--user', '-u', '--owner', '--lead', '-e', '--orcid')
            _INSTRUMENT_FLAGS = ('--instrument-id',)
            _INSTRUMENT_MFID_FLAGS = ('--instrument-mfid',)
            # Flags whose value is a dataset or sample MFID, by resource context.
            # Values here can't contain unquoted spaces (argparse flag values are
            # single tokens), so completion is a plain prefix/substring search
            # rather than the multi-word span logic used for positionals.
            _ENTITY_FLAGS = {
                ('dataset', 'link'): {
                    '-p': 'datasets', '--parent': 'datasets',
                    '-c': 'datasets', '--child': 'datasets',
                },
                ('dataset', 'add-sample'): {
                    '-s': 'samples', '--sample': 'samples',
                },
                ('dataset', 'remove-sample'): {
                    '-s': 'samples', '--sample': 'samples',
                },
                ('dataset', 'remove-child'): {
                    '-c': 'datasets', '--child': 'datasets',
                },
                ('sample', 'link'): {
                    '-p': 'samples', '--parent': 'samples',
                    '-c': 'samples', '--child': 'samples',
                },
                ('sample', 'add-dataset'): {
                    '-d': 'datasets', '--dataset': 'datasets',
                },
                ('sample', 'remove-dataset'): {
                    '-d': 'datasets', '--dataset': 'datasets',
                },
                ('sample', 'remove-child'): {
                    '-c': 'samples', '--child': 'samples',
                },
            }.get((resource, subcommand), {})

            if current_word and not current_word.startswith('-'):
                # Mid-typing a flag value.
                if prev in _USER_FLAGS:
                    yield from self._yield_user_completions(current_word)
                elif prev in _PROJECT_FLAGS:
                    yield from self._yield_project_completions(current_word)
                elif prev in _PROJECT_MFID_FLAGS:
                    yield from self._yield_project_completions(current_word, use_mfid=True)
                elif prev in _INSTRUMENT_FLAGS:
                    yield from self._yield_instrument_completions(current_word)
                elif prev in _INSTRUMENT_MFID_FLAGS:
                    yield from self._yield_instrument_completions(current_word, use_mfid=True)
                elif prev in _ENTITY_FLAGS:
                    entity_type = _ENTITY_FLAGS[prev]
                    icon = _ENTITY_ICONS.get(entity_type.rstrip('s'), '')
                    yield from self._yield_entity_completions(entity_type, current_word, current_word, icon)
                else:
                    action = sub_parser._option_string_actions.get(prev)
                    if action is not None and action.choices:
                        for choice in action.choices:
                            choice = str(choice)
                            if choice.startswith(current_word):
                                yield Completion(
                                    choice + ' ', start_position=-len(current_word))
                return

            if not current_word and prev in _USER_FLAGS:
                yield from self._yield_user_completions('')
                return

            if not current_word and prev in _PROJECT_FLAGS:
                yield from self._yield_project_completions('')
                return

            if not current_word and prev in _PROJECT_MFID_FLAGS:
                yield from self._yield_project_completions('', use_mfid=True)
                return

            if not current_word and prev in _INSTRUMENT_FLAGS:
                yield from self._yield_instrument_completions('')
                return

            if not current_word and prev in _INSTRUMENT_MFID_FLAGS:
                yield from self._yield_instrument_completions('', use_mfid=True)
                return

            if not current_word and prev in _ENTITY_FLAGS:
                entity_type = _ENTITY_FLAGS[prev]
                icon = _ENTITY_ICONS.get(entity_type.rstrip('s'), '')
                yield from self._yield_entity_completions(entity_type, '', '', icon)
                return

            if not current_word:
                action = sub_parser._option_string_actions.get(prev)
                if action is not None and action.choices:
                    for choice in action.choices:
                        yield Completion(str(choice) + ' ', start_position=0)
                    return

            for flag, action in sub_parser._option_string_actions.items():
                if action.help == argparse.SUPPRESS:
                    continue
                if flag.startswith(current_word):
                    yield Completion(flag + ' ', start_position=-len(current_word))

except ImportError:
    _CrucibleCompleter = None


class CrucibleShell:
    """Interactive Crucible shell.

    Owns one CrucibleClient instance (self.client), shared mutable state
    (self.state), and the prompt_toolkit completer (self.completer).
    """

    _SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def __init__(self, parser):
        self.parser    = parser
        self.client    = None
        self.state     = {}
        self.completer = None
        self.is_admin  = False
        self._session  = None         # prompt_toolkit PromptSession
        self._clock_stop = threading.Event()

    def run(self):
        """Start the interactive shell."""
        if _CrucibleCompleter:
            self._run_prompt_toolkit()
        else:
            self._run_readline()

    def _verify_connection(self):
        """Spinner + whoami. Sets self.client. Exits on failure."""
        from crucible.client import CrucibleClient

        _spin_state = {'msg': 'Connecting to Crucible'}
        _stop       = threading.Event()
        _is_tty     = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        _RETRY_RE   = _re.compile(r'Retry\(total=(\d+)')

        def _spin():
            for frame in itertools.cycle(self._SPINNER_FRAMES):
                if _stop.is_set():
                    break
                sys.stdout.write(f'\r  {_spin_state["msg"]}  {frame}')
                sys.stdout.flush()
                time.sleep(0.08)
            sys.stdout.write('\r\033[2K')
            sys.stdout.flush()

        class _RetryToSpinner(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                if 'Retrying' not in msg:
                    return True
                m = _RETRY_RE.search(msg)
                n = m.group(1) if m else '?'
                _spin_state['msg'] = f'Retrying... ({n} left)'
                return False

        _filt = _RetryToSpinner()
        for _h in logging.getLogger().handlers:
            _h.addFilter(_filt)

        if _is_tty:
            _spin_thread = threading.Thread(target=_spin, daemon=True)
            _spin_thread.start()
        else:
            print('  Connecting to Crucible...')

        try:
            self.client = CrucibleClient()
            info = self.client.whoami()
        except Exception as e:
            _stop.set()
            if _is_tty:
                _spin_thread.join()
            for _h in logging.getLogger().handlers:
                _h.removeFilter(_filt)
            logger.error(f"Cannot connect to Crucible: {e}")
            sys.exit(1)

        _stop.set()
        if _is_tty:
            _spin_thread.join()
        for _h in logging.getLogger().handlers:
            _h.removeFilter(_filt)

        return info

    def _init_state(self, whoami_info):
        """Populate self.state from startup data."""
        from .helpers import (
            fetch_projects, fetch_deletions, fetch_join_requests, fetch_service_accounts,
            fetch_user_label, fetch_project_context, fetch_api_label, fetch_api_attention,
        )
        deletions     = fetch_deletions(self.client)
        join_requests = fetch_join_requests(self.client)
        self.is_admin = deletions is not None
        service_accounts = fetch_service_accounts(self.client) if self.is_admin else None

        project_id, project_source = fetch_project_context()
        self.state = {
            'user_label':        fetch_user_label(self.client, whoami_info),
            'projects':          fetch_projects(self.client),
            'project':           project_id,
            'project_source':    project_source,
            'api_label':         fetch_api_label(),
            'api_attention':     fetch_api_attention(),
            'debug':             False,
            'deletions':         deletions or [],
            'join_requests':     join_requests or [],
            'service_accounts':  service_accounts or [],
            'recent_mfids':      deque(maxlen=15),
        }

    def refresh(self):
        """Re-fetch projects, user info, deletions, join requests, and service accounts. Updates state + completer."""
        from .helpers import (
            fetch_projects, fetch_deletions, fetch_join_requests, fetch_service_accounts,
            fetch_user_label, fetch_project_context, fetch_api_label, fetch_api_attention,
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            proj_f = pool.submit(fetch_projects,      self.client)
            del_f  = pool.submit(fetch_deletions,     self.client)
            jr_f   = pool.submit(fetch_join_requests, self.client)
            sa_f   = pool.submit(fetch_service_accounts, self.client)
            new_projects         = proj_f.result()
            new_deletions        = del_f.result()
            new_join_requests    = jr_f.result()
            new_service_accounts = sa_f.result()
        self.is_admin = new_deletions is not None
        self.state['projects']         = new_projects
        self.state['user_label']       = fetch_user_label(self.client)
        project_id, project_source = fetch_project_context()
        self.state['project']          = project_id
        self.state['project_source']   = project_source
        self.state['api_label']        = fetch_api_label()
        self.state['api_attention']    = fetch_api_attention()
        self.state['deletions']        = new_deletions or []
        self.state['join_requests']    = new_join_requests or []
        self.state['service_accounts'] = new_service_accounts or []
        if self.completer is not None:
            self.completer._projects         = new_projects
            self.completer._deletions        = new_deletions
            self.completer._join_requests    = new_join_requests
            self.completer._service_accounts = new_service_accounts
            self.completer._user_search_cache.clear()
            self.completer._entity_search_cache.clear()
            self.completer._project_search_cache.clear()
            self.completer._instrument_search_cache.clear()
        print(f"Refreshed: {len(new_projects)} projects, user info reloaded.")

    def _toolbar(self):
        from prompt_toolkit.application import get_app
        label = self.state.get('project') or '(no project set)'
        if len(label) > 22:
            label = label[:21] + '…'
        source = self.state.get('project_source')
        source_label = ' [env]' if source == 'environment' else ''
        project_label = f'🔬 {label}{source_label}'
        proj_content = project_label + ' ' * max(0, 25 - _vlen(project_label))
        clock        = datetime.now().strftime('%H:%M')

        left_str  = f' {proj_content} '
        mid_str   = f' 🧸 {self.state.get("user_label", "?")} '
        api_str   = f' 🔗 {self.state.get("api_label", "?")} '
        clock_str = f' {clock} '
        separator = ' │ '
        debug_str = ' DEBUG ' if self.state.get('debug') else ''

        try:
            term_width = get_app().output.get_size().columns
        except Exception:
            term_width = 80

        fixed_width = (
            _vlen(left_str) + _vlen(mid_str) + _vlen(api_str)
            + _vlen(clock_str) + 3 * _vlen(separator) + len(debug_str)
        )
        if debug_str:
            fixed_width += _vlen(separator)
        pad = ' ' * max(0, term_width - fixed_width)
        api_tag = 'tb-api-attention' if self.state.get('api_attention') else 'tb-api'
        debug_segment = (
            f'<tb-separator>{separator}</tb-separator><tb-debug>{debug_str}</tb-debug>'
            if debug_str else ''
        )
        return _shell_html(
            f'<tb-project>{left_str}</tb-project>'
            f'<tb-separator>{separator}</tb-separator>{mid_str}'
            f'<tb-separator>{separator}</tb-separator><{api_tag}>{api_str}</{api_tag}>'
            f'{pad}{debug_segment}'
            f'<tb-separator>{separator}</tb-separator><tb-clock>{clock_str}</tb-clock>'
        )

    def _clock_tick(self):
        """Background thread: invalidate toolbar once per minute."""
        secs_to_next = 60 - datetime.now().second
        if self._clock_stop.wait(timeout=secs_to_next):
            return
        while not self._clock_stop.is_set():
            try:
                self._session.app.invalidate()
            except Exception:
                pass
            self._clock_stop.wait(timeout=60)

    def _resolve_future(self, last, key, default=None):
        """Resolve a named future from last_resource, returning default on failure."""
        future = last.get(key)
        if future is None:
            return default
        try:
            return future.result(timeout=15)
        except Exception:
            return default

    def _render_resource(self, last):
        """Re-render the cached resource with current verbose/graph flags."""
        try:
            rtype = last['type']
            data  = last['data']
            if not last.get('graph'):
                links = None
            elif '_links_future' in last:
                links = self._resolve_future(last, '_links_future', None)
            else:
                links = data.get('links')
            if rtype == 'dataset':
                from .dataset import _show_dataset
                prefetched = {
                    'keywords': self._resolve_future(last, '_keywords_future', []),
                    'af_list':  self._resolve_future(last, '_files_future', []),
                    'link_map': self._resolve_future(last, '_dl_links_future', {}),
                }
                _show_dataset(data, self.client, verbose=last['verbose'],
                              graph=last['graph'],
                              include_metadata=last.get('include_metadata', False),
                              links=links, prefetched=prefetched)
            elif rtype == 'sample':
                from .sample import _show_sample
                _show_sample(data, self.client, verbose=last['verbose'],
                             graph=last['graph'],
                             include_metadata=last.get('include_metadata', False),
                             links=links)
        except Exception as e:
            logger.error(f"Error rendering resource: {e}")

    def _activate_project(self, project_id, title=None):
        """Persist a project selection and apply it to the running shell."""
        if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
            from .helpers import show_warning
            show_warning(
                "CRUCIBLE_CURRENT_PROJECT controls the current project. "
                "Unset it before using the shell project selector."
            )
            return False
        from .config import set_config_value
        set_config_value('current_project', project_id)
        self.state['project'] = project_id
        self.state['project_source'] = 'config file'
        label = f"{project_id} - {title}" if title else project_id
        print(f"Using project: {label} (remembered)")
        return True

    def _dispatch(self, line):
        """Parse and execute one command line. Returns False to signal exit."""
        from . import _remap_deprecated, setup_logging

        line = line.strip()
        if not line:
            return True
        if line in ('exit', 'quit'):
            return False
        if line == 'help':
            self.parser.print_help()
            _W = 18
            print()
            term.header("Shell commands")
            for _cmd, _desc in [
                ('use PROJECT',   'select and remember current project'),
                ('unuse',         'clear the current project'),
                ('refresh',       're-fetch projects, user info, deletions'),
                ('reload',        'restart the shell process'),
                ('debug on|off',  'toggle debug logging'),
                ('v',             'toggle verbose view for last fetched resource'),
                ('! CMD',         'run a shell command'),
                ('ls [PATH]',     'list directory'),
                ('cd [PATH]',     'change directory'),
                ('pwd',           'print working directory'),
                ('exit / quit',   'exit the shell'),
            ]:
                print(f"  {term.cyan(_cmd)}{' ' * (_W - len(_cmd))} {_desc}")
            if _CrucibleCompleter:
                print()
                term.header("Keyboard shortcuts")
                for _key, _desc in [
                    ('Alt+V',  'toggle verbose view for last fetched resource'),
                    ('Alt+G',  'toggle graph view for last fetched resource'),
                    ('Alt+R',  'refresh projects, user info, and deletions'),
                    ('Alt+P',  'project picker (type a number or filter text)'),
                    ('Alt+O',  'open last resource in Graph Explorer'),
                    ('Ctrl+L', 'clear screen'),
                ]:
                    print(f"  {term.bold(_key)}{' ' * (_W - len(_key))} {_desc}")
            print()
            return True

        if line.startswith('use ') or line == 'use':
            parts = line.split(None, 1)
            if len(parts) < 2 or not parts[1].strip():
                print("Usage: use <project_id>")
                return True
            project_id = parts[1].strip()
            if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
                from .helpers import show_warning
                show_warning(
                    "CRUCIBLE_CURRENT_PROJECT controls the current project. "
                    "Unset it before using the shell project selector."
                )
                return True
            try:
                import requests as _req
                project = self.client.projects.get(project_id)
                if project is None:
                    logger.error(f"Project not found: {project_id}")
                    return True
            except _req.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (403, 404):
                    logger.error(f"Project '{project_id}' not found or not accessible")
                else:
                    logger.error(f"Cannot access project '{project_id}': {e}")
                return True
            except Exception as e:
                logger.error(f"Cannot access project '{project_id}': {e}")
                return True
            try:
                title = project.get('title') or ''
                self._activate_project(project_id, title)
            except Exception as e:
                logger.error(f"Error switching project: {e}")
            return True

        if line == 'unuse':
            if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
                from .helpers import show_warning
                show_warning(
                    "CRUCIBLE_CURRENT_PROJECT controls the current project. "
                    "Unset it before clearing the shell project selection."
                )
                return True
            from .config import unset_config_value
            unset_config_value('current_project')
            self.state['project'] = None
            self.state['project_source'] = None
            print("Cleared current project.")
            return True

        if line == 'refresh':
            try:
                from crucible.config import config as _cfg
                _cfg.reload()
            except Exception:
                pass
            self.refresh()
            return True

        if line == 'reload':
            print('\033[2J\033[H', end='', flush=True)
            os.execv(sys.executable, [sys.executable] + sys.argv)

        if line.startswith('!'):
            import subprocess
            cmd = line[1:].strip()
            if cmd:
                subprocess.run(cmd, shell=True)
            return True

        if line == 'pwd':
            print(os.getcwd())
            return True

        if line.startswith('ls') and (len(line) == 2 or line[2] == ' '):
            parts = line.split(None, 1)
            path  = os.path.expanduser(parts[1].strip()) if len(parts) > 1 else '.'
            try:
                entries = sorted(os.scandir(path), key=lambda e: (e.name.startswith('.'), e.name.lower()))
            except (FileNotFoundError, NotADirectoryError) as exc:
                print(f"ls: {exc}")
                return True
            col_width = max((len(e.name) for e in entries), default=0) + 3
            term_width = shutil.get_terminal_size().columns
            cols = max(1, term_width // col_width)
            for i, entry in enumerate(entries):
                display = entry.name + ('/' if entry.is_dir() else '')
                if entry.is_dir():
                    label = term.cyan(display)
                elif entry.name.endswith('.crux'):
                    label = term.bold(display)
                elif entry.name.startswith('.'):
                    label = term.dim(display)
                else:
                    label = display
                pad = ' ' * (col_width - _vlen(display))
                end = '\n' if (i + 1) % cols == 0 or i == len(entries) - 1 else ''
                print(label + pad, end=end)
            return True

        if line.startswith('cd') and (len(line) == 2 or line[2] == ' '):
            parts = line.split(None, 1)
            arg   = parts[1].strip() if len(parts) > 1 else '~'
            if arg == '-':
                oldpwd = self.state.get('oldpwd')
                if not oldpwd:
                    print("cd: no previous directory")
                    return True
                path = oldpwd
            else:
                path = os.path.expanduser(arg)
            try:
                prev = os.getcwd()
                os.chdir(path)
                self.state['oldpwd'] = prev
                if arg == '-':
                    print(os.getcwd())
            except FileNotFoundError:
                print(f"cd: no such directory: {path}")
            except NotADirectoryError:
                print(f"cd: not a directory: {path}")
            return True

        if line == 'v':
            last = self.state.get('last_resource')
            if not last:
                print("No recent get to toggle. Run 'get <id>' first.")
                return True
            last['verbose'] = not last['verbose']
            self._render_resource(last)
            return True

        if line == 'debug' or line.startswith('debug '):
            parts   = line.split()
            current = self.state.get('debug', False)
            if len(parts) == 1:
                print(f"Debug is {'on' if current else 'off'}.")
                return True
            action = parts[1].lower()
            if action not in ('on', 'off'):
                print("Usage: debug on | debug off")
                return True
            on = (action == 'on')
            self.state['debug'] = on
            setup_logging(debug=on)
            print(f"Debug {'enabled' if on else 'disabled'}.")
            return True

        words = line.split()
        try:
            argv = _remap_deprecated(shlex.split(line))
            args = self.parser.parse_args(argv)
            setup_logging(debug=getattr(args, 'debug', False) or self.state.get('debug', False))
            if hasattr(args, 'func'):
                args._shell_state = self.state
                args.func(args)
                from .helpers import fetch_project_context
                project_id, project_source = fetch_project_context()
                self.state['project'] = project_id
                self.state['project_source'] = project_source
            else:
                self.parser.print_help()
        except SystemExit:
            pass
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:
            logger.error(f"Error: {e}")

        # Re-fetch pending deletions after any deletion command (admin only)
        if (self.is_admin and len(words) >= 2
                and words[0] == 'deletion' and words[1] in ('approve', 'reject', 'request')):
            from .helpers import fetch_deletions
            new_deletions = fetch_deletions(self.client)
            self.state['deletions'] = new_deletions
            if self.completer is not None:
                self.completer._deletions = new_deletions

        # Re-fetch pending join requests after any ag/access-group command
        if (len(words) >= 2 and words[0] in ('ag', 'access-group')
                and words[1] in ('approve', 'reject', 'request')):
            from .helpers import fetch_join_requests
            new_join_requests = fetch_join_requests(self.client)
            self.state['join_requests'] = new_join_requests
            if self.completer is not None:
                self.completer._join_requests = new_join_requests

        # Re-fetch service accounts after any sa/service-account command that changes the list
        if (self.is_admin and len(words) >= 2 and words[0] in ('sa', 'service-account')
                and words[1] in ('create', 'update', 'rotate-key')):
            from .helpers import fetch_service_accounts
            new_service_accounts = fetch_service_accounts(self.client)
            self.state['service_accounts'] = new_service_accounts or []
            if self.completer is not None:
                self.completer._service_accounts = new_service_accounts or []

        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'unset', 'edit'):
            from crucible.config import config as _cfg
            from crucible.client import CrucibleClient
            try:
                _cfg.reload()
                self.client = CrucibleClient()
                if self.completer is not None:
                    self.completer._client       = self.client
                    self.completer._unlink_cache = {}
                    self.completer._user_search_cache.clear()
                    self.completer._entity_search_cache.clear()
                    self.completer._project_search_cache.clear()
                    self.completer._instrument_search_cache.clear()
            except Exception:
                pass
            self.refresh()

        return True

    def _run_prompt_toolkit(self):
        from prompt_toolkit                import PromptSession
        from prompt_toolkit.history        import FileHistory
        from prompt_toolkit.auto_suggest   import AutoSuggestFromHistory
        from prompt_toolkit.styles         import Style
        from prompt_toolkit.key_binding    import KeyBindings
        from prompt_toolkit.completion     import ThreadedCompleter
        from platformdirs import user_data_dir

        history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        print('\033[2J\033[H', end='', flush=True)

        info = self._verify_connection()
        self._init_state(info)

        _print_shell_banner(shutil.get_terminal_size((80, 24)).columns)

        _u     = info.get('user_info', {})
        _first = _u.get('first_name', '').strip() or \
                 _u.get('last_name', '').strip() or \
                 info.get('access_group_name') or 'there'
        print(f"\nWelcome to the Crucible interactive shell, {_first}.\n"
              "(type 'help' for commands, 'exit' to quit)")
        if self.state.get('project_source') == 'environment':
            from .helpers import show_warning
            show_warning(
                "CRUCIBLE_CURRENT_PROJECT is controlling the current project and is deprecated. "
                "Use 'use PROJECT_ID' to save a selection after unsetting the environment variable."
            )

        self.completer = _CrucibleCompleter(
            self.parser,
            client=self.client,
            projects=self.state['projects'],
            deletions=self.state['deletions'],
            join_requests=self.state['join_requests'],
            service_accounts=self.state['service_accounts'],
            state=self.state,
        )

        kb = KeyBindings()
        from .keybindings import register as _register_keybindings
        _register_keybindings(kb, self)

        self._session = PromptSession(
            history=FileHistory(history_path),
            auto_suggest=AutoSuggestFromHistory(),
            completer=ThreadedCompleter(self.completer),
            complete_while_typing=True,
            key_bindings=kb,
            bottom_toolbar=self._toolbar,
            style=Style.from_dict(_shell_style_rules()),
            color_depth=_shell_color_depth(),
        )

        threading.Thread(target=self._clock_tick, daemon=True).start()

        while True:
            try:
                line = self._session.prompt(_PROMPT)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
            if not self._dispatch(line):
                break
            print()

        self._clock_stop.set()

    def _run_readline(self):
        """Fallback shell using stdlib readline."""
        print("\nCrucible interactive shell  (type 'help' for commands, 'exit' to quit)")
        try:
            import readline  # noqa: F401
        except ImportError:
            pass

        while True:
            try:
                line = input(_PROMPT)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
            if not self._dispatch(line):
                break
            print()


def run(parser):
    """Start the interactive shell. Called from main() when no command given."""
    CrucibleShell(parser).run()
