"""Tab completion for the interactive shell."""

import argparse
import os
import shlex
import html as _html

from prompt_toolkit.completion import Completer, Completion

from .. import term
from ...constants import PLATFORM_ROLES
from ._common import ENTITY_ICONS, get_subparser_map, shell_html


class CrucibleCompleter(Completer):
    """Three-level argparse completer: resource -> subcommand -> flags."""

    def __init__(self, parser, client=None, projects=None, deletions=None,
                 join_requests=None, service_accounts=None, state=None):
        self._top               = get_subparser_map(parser)
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
        self._facet_cache       = {}  # (resource, field, project_id) -> [(value, label, count), ...]
        self._state             = state or {}
        self.hidden             = set()

    def _lazy_projects(self):
        if not self._projects and self._client is not None:
            from ..helpers import fetch_projects
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
                display=shell_html(f'<b>{_html.escape(identifier)}</b>'),
                display_meta=shell_html(f'<ansibrightblack>{_html.escape(meta)}{_html.escape(meta_orcid)}</ansibrightblack>'),
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
                display=shell_html(f'<b>{_html.escape(value)}</b>'),
                display_meta=shell_html(
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
                display=shell_html(f'<b>{_html.escape(value)}</b>'),
                display_meta=shell_html(
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
                        display=shell_html(f'<b>{_html.escape(uid)}</b>'),
                        display_meta=shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                    )
            return
        project_id = self._state.get('project')
        for uid, name in self._search_entities(entity_type, query, project_id=project_id):
            yield Completion(
                uid + ' ',
                start_position=-len(arg_text),
                display=shell_html(f'<b>{_html.escape(uid)}</b>'),
                display_meta=shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
            )

    # (resource, flag) -> facet field whose observed values complete that flag.
    _FACET_FLAGS = {
        ('dataset', '-m'): 'measurement',
        ('dataset', '--measurement'): 'measurement',
        ('dataset', '--session'): 'session',
        ('dataset', '--data-format'): 'data_format',
        ('sample', '--type'): 'sample_type',
        ('sample', '-t'): 'sample_type',
    }

    def _facet_values(self, resource, field, project_id):
        """Observed values of a facet field, cached per project for the session."""
        key = (resource, field, project_id)
        if key in self._facet_cache:
            return self._facet_cache[key]
        values = []
        if self._client is not None:
            try:
                operations = getattr(self._client, f'{resource}s')
                filters = {'project_id': project_id} if project_id else {}
                response = operations.facets(field, limit=200, sort='count',
                                             direction='desc', **filters)
                for bucket in response.get('items') or []:
                    value = bucket.get('value')
                    if value is not None and str(value).strip():
                        values.append((str(value), bucket.get('label') or str(value),
                                       bucket.get('count')))
            except Exception:
                pass
        self._facet_cache[key] = values
        return values

    @staticmethod
    def _typed_project(words):
        """The --project-id/-p value typed earlier on the line, if any."""
        for flag in ('--project-id', '-p', '-pid'):
            if flag in words:
                index = words.index(flag)
                if index + 1 < len(words):
                    return words[index + 1]
        return None

    def _yield_facet_completions(self, resource, field, words, prefix):
        """Complete a flag value from the values actually present in Crucible.

        Scoped to the project typed on the line, else the current project, so
        suggestions match what the command would list.
        """
        if '--all-projects' in words:
            project_id = None
        else:
            project_id = self._typed_project(words) or self._state.get('project')
        lowered = prefix.lower()
        for value, label, count in self._facet_values(resource, field, project_id):
            if not value.lower().startswith(lowered) and lowered not in value.lower():
                continue
            text = shlex.quote(value) if any(c.isspace() for c in value) else value
            meta = f'{count}' if label == value else f'{label} | {count}'
            yield Completion(
                text + ' ',
                start_position=-len(prefix),
                display=shell_html(f'<b>{_html.escape(value)}</b>'),
                display_meta=shell_html(f'<ansibrightblack>{_html.escape(meta)}</ansibrightblack>'),
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
        'debug':           '_complete_on_off',
        'elevated':        '_complete_on_off',
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
            candidates = list(self._top) + ['use', 'unuse', 'refresh', 'reload', 'debug', 'elevated', 'cd', 'ls', 'pwd']
            for name in candidates:
                if name in self.hidden:
                    continue
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

    def _complete_on_off(self, ctx):
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
                display=shell_html(f'<b>{did}</b>'),
                display_meta=shell_html(' | '.join(parts)),
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
                    display=shell_html(f'<b>{jid}</b>'),
                    display_meta=shell_html(' | '.join(parts)),
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
        _SA_SUBS = {'get', 'show', 'set-role', 'rotate-key', 'edit', 'update',
                    'list-access-groups', 'add-access-group', 'remove-access-group'}
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
            meta = sa.get('platform_role') or ''
            yield Completion(
                username + ' ',
                start_position=-len(prefix),
                display=shell_html(f'<b>{_html.escape(username)}</b>'),
                display_meta=shell_html(f'<ansibrightblack>{_html.escape(meta)}</ansibrightblack>'),
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
                icon_html = ENTITY_ICONS.get(etype, '<ansibrightblack>[?]</ansibrightblack>')
                meta = f'{icon_html} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'
                yield Completion(
                    uid + ' ',
                    start_position=-len(prefix),
                    display=shell_html(f'<b>{_html.escape(uid)}</b>'),
                    display_meta=shell_html(meta),
                )
        return True

    def _complete_recent_mfid(self, ctx):
        text, words, trailing_space, resource = ctx
        # Complete the first positional MFID from recently visited resources.
        if trailing_space and len(words) == 1:
            prefix = ''
            for uid, name, rtype in self._state.get('recent_mfids', []):
                if uid.startswith(prefix):
                    icon = ENTITY_ICONS.get(rtype, '<ansibrightblack>[?]</ansibrightblack>')
                    yield Completion(
                        uid + ' ',
                        start_position=-len(prefix),
                        display=shell_html(f'<b>{_html.escape(uid)}</b>'),
                        display_meta=shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                    )
            return True
        elif not trailing_space and len(words) == 2 and not words[1].startswith('-'):
            prefix = words[1]
            for uid, name, rtype in self._state.get('recent_mfids', []):
                if uid.startswith(prefix):
                    icon = ENTITY_ICONS.get(rtype, '<ansibrightblack>[?]</ansibrightblack>')
                    yield Completion(
                        uid + ' ',
                        start_position=-len(prefix),
                        display=shell_html(f'<b>{_html.escape(uid)}</b>'),
                        display_meta=shell_html(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
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
                      'set-role', 'revoke-keys', 'search'}
        if words[1] not in _USER_SUBS:
            return False
        if trailing_space and len(words) == 2:
            prefix = ''
        elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
            prefix = words[2]
        else:
            if words[1] != 'set-role':
                return False
            if trailing_space and len(words) == 3:
                for role in PLATFORM_ROLES:
                    yield Completion(role + ' ', start_position=0)
                return True
            if not trailing_space and len(words) == 4:
                for role in PLATFORM_ROLES:
                    if role.startswith(words[3]):
                        yield Completion(
                            role + ' ', start_position=-len(words[3]))
                return True
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
            'list-users', 'add-user', 'remove-user', 'update-user-role',
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
            yield from self._yield_instrument_completions('')
            return True
        if not trailing_space and len(words) == 3 and not words[2].startswith('-'):
            yield from self._yield_instrument_completions(words[2])
            return True
        if subcommand in {'transfer-ownership', 'update-user-role'} and len(words) in (3, 4):
            if trailing_space and len(words) == 3:
                yield from self._yield_user_completions('')
                return True
            if not trailing_space and len(words) == 4:
                yield from self._yield_user_completions(words[3])
                return True
        if subcommand == 'update-user-role' and len(words) >= 4:
            prefix = '' if trailing_space else words[-1]
            if (trailing_space and len(words) == 4) or (not trailing_space and len(words) == 5):
                for role in ('editor', 'admin'):
                    if role.startswith(prefix):
                        yield Completion(role + ' ', start_position=-len(prefix))
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
            'link', 'parsers', 'ingestors', 'facets',
        }
        if words[1] in _NO_ID_SUBS:
            return False
        from ...utils.identifiers import is_mfid
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
        icon = ENTITY_ICONS.get(resource, '')
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
                    display=shell_html('<ansicyan><b>../</b></ansicyan>'),
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
                        display=shell_html(disp),
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

        sub_map = get_subparser_map(self._top.get(resource)) \
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
        if subcommand in ('list', 'facets'):
            _ENTITY_FLAGS = {**_ENTITY_FLAGS,
                             '--sample-mfid': 'samples', '--dataset-mfid': 'datasets'}

        if subcommand == 'facets' and resource in ('dataset', 'sample'):
            positionals = [w for w in words[2:] if not w.startswith('-')]
            if (trailing_space and not positionals) or (
                    not trailing_space and len(positionals) == 1 and words[-1] == positionals[0]):
                action = next((a for a in sub_parser._actions if a.dest == 'field'), None)
                for choice in (action.choices if action is not None else ()):
                    if choice.startswith(current_word):
                        yield Completion(choice + ' ', start_position=-len(current_word))
                return

        facet_field = self._FACET_FLAGS.get((resource, prev))
        if facet_field and subcommand in ('list', 'facets') and (
                not current_word or not current_word.startswith('-')):
            yield from self._yield_facet_completions(resource, facet_field, words,
                                                     current_word)
            return

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
                icon = ENTITY_ICONS.get(entity_type.rstrip('s'), '')
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
            icon = ENTITY_ICONS.get(entity_type.rstrip('s'), '')
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
