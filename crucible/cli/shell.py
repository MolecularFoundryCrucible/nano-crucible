#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

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
    'dataset': '<ansired><b>[ds]</b></ansired>',
    'sample':  '<ansimagenta><b>[s]</b></ansimagenta>',
}


try:
    from prompt_toolkit.completion     import Completer, Completion
    from prompt_toolkit.formatted_text import HTML as _HTML

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource -> subcommand -> flags."""

        def __init__(self, parser, client=None, projects=None, deletions=None, state=None):
            self._top          = _get_subparser_map(parser)
            self._client       = client
            self._projects     = projects  or []
            self._deletions    = deletions or []
            self._unlink_cache = {}  # mfid -> [(uid, name, entity_type), ...]
            self._users        = []  # [(orcid, full_name), ...]
            self._state        = state or {}

        def _lazy_projects(self):
            if not self._projects and self._client is not None:
                from .helpers import fetch_projects
                self._projects = fetch_projects(self._client)
            return self._projects

        def _lazy_users(self):
            if not self._users and self._client is not None:
                try:
                    users = self._client.users.list()
                    self._users = [
                        (u.get('orcid') or '',
                         f"{u.get('first_name', '')} {u.get('last_name', '')}".strip())
                        for u in users if u.get('orcid')
                    ]
                except Exception:
                    pass
            return self._users

        def _yield_user_completions(self, prefix):
            """Yield ORCID completions matching prefix against ORCID or name."""
            prefix_lower = prefix.lower()
            for orcid, name in self._lazy_users():
                if orcid.startswith(prefix) or prefix_lower in name.lower():
                    yield Completion(
                        orcid + ' ',
                        start_position=-len(prefix),
                        display=_HTML(f'<b>{_html.escape(orcid)}</b>'),
                        display_meta=_HTML(f'<ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                    )

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

            if resource == 'debug':
                if len(words) > 2:
                    return
                prefix = words[1] if len(words) == 2 and not trailing_space else ''
                for choice in ('on', 'off'):
                    if choice.startswith(prefix):
                        yield Completion(choice + ' ', start_position=-len(prefix))
                return

            if resource == 'use':
                if len(words) > 2:
                    return
                prefix = words[1] if len(words) == 2 and not trailing_space else ''
                for pid, title in self._lazy_projects():
                    if pid.startswith(prefix):
                        yield Completion(pid + ' ', start_position=-len(prefix),
                                         display=_HTML(f'<b>{pid}</b>'),
                                         display_meta=_HTML(f'<ansibrightblack>{_html.escape(title)}</ansibrightblack>'))
                return

            if resource == 'deletion' and len(words) >= 2 and words[1] in ('approve', 'reject', 'get'):
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
                        display=_HTML(f'<b>{did}</b>'),
                        display_meta=_HTML(' | '.join(parts)),
                    )
                return

            if resource == 'unlink' and self._client is not None:
                # Positional form: unlink MFID1 MFID2
                # Complete MFID2 from the graph neighbors of MFID1.
                first = None
                prefix = ''
                if trailing_space and len(words) == 2 and not words[1].startswith('-'):
                    first, prefix = words[1], ''
                elif not trailing_space and len(words) == 3 \
                        and not words[1].startswith('-') and not words[2].startswith('-'):
                    first, prefix = words[1], words[2]
                if first:
                    for uid, name, etype in self._unlink_neighbors(first):
                        if uid.startswith(prefix):
                            icon_html = _ENTITY_ICONS.get(etype, '<ansibrightblack>[?]</ansibrightblack>')
                            meta = f'{icon_html} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'
                            yield Completion(
                                uid + ' ',
                                start_position=-len(prefix),
                                display=_HTML(f'<b>{_html.escape(uid)}</b>'),
                                display_meta=_HTML(meta),
                            )
                    return

            if resource in ('get', 'edit', 'open', 'tree'):
                # Complete the first positional MFID from recently visited resources.
                if trailing_space and len(words) == 1:
                    prefix = ''
                elif not trailing_space and len(words) == 2 and not words[1].startswith('-'):
                    prefix = words[1]
                else:
                    prefix = None
                if prefix is not None:
                    for uid, name, rtype in self._state.get('recent_mfids', []):
                        if uid.startswith(prefix):
                            icon = _ENTITY_ICONS.get(rtype, '<ansibrightblack>[?]</ansibrightblack>')
                            yield Completion(
                                uid + ' ',
                                start_position=-len(prefix),
                                display=_HTML(f'<b>{_html.escape(uid)}</b>'),
                                display_meta=_HTML(f'{icon} <ansibrightblack>{_html.escape(name)}</ansibrightblack>'),
                            )
                    return

            if resource == 'user' and len(words) >= 2:
                # Complete the ORCID positional for admin subcommands.
                _ORCID_SUBS = {'list-datasets', 'check-access', 'list-access-groups', 'list-projects'}
                if words[1] in _ORCID_SUBS:
                    if trailing_space and len(words) == 2:
                        prefix = ''
                    elif not trailing_space and len(words) == 3 and not words[2].startswith('-'):
                        prefix = words[2]
                    else:
                        prefix = None
                    if prefix is not None:
                        yield from self._yield_user_completions(prefix)
                        return

            if resource in ('cast', 'cd', 'ls'):
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
                            display=_HTML('<ansiblue><b>../</b></ansiblue>'),
                        )))

                    try:
                        scan = os.scandir(search_dir)
                    except (PermissionError, FileNotFoundError):
                        return

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
                                disp = f'<ansiblue><b>{esc}</b></ansiblue>'
                            elif is_crux:
                                disp = f'<ansiyellow><b>{esc}</b></ansiyellow>'
                            elif is_hidden:
                                disp = f'<ansibrightblack>{esc}</ansibrightblack>'
                            else:
                                disp = esc

                            results.append((is_hidden, display_name.lower(), Completion(
                                completion_text,
                                start_position=0,
                                display=_HTML(disp),
                            )))

                    results.sort(key=lambda x: (x[0], x[1]))
                    yield from (c for _, _, c in results)
                    return

                # Flag completion for cast
                if resource == 'cast':
                    current_word = '' if trailing_space else words[-1]
                    if current_word.startswith('-'):
                        cast_parser = self._top.get('cast')
                        if cast_parser:
                            for flag in cast_parser._option_string_actions:
                                if flag.startswith(current_word):
                                    yield Completion(flag + ' ', start_position=-len(current_word))
                return

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
                    for pid, title in self._lazy_projects():
                        if pid.startswith(prefix):
                            yield Completion(pid + ' ', start_position=-len(prefix),
                                             display=_HTML(f'<b>{pid}</b>'),
                                             display_meta=_HTML(f'<ansibrightblack>{_html.escape(title)}</ansibrightblack>'))
                return

            sub_parser  = sub_map.get(subcommand)
            if sub_parser is None:
                return

            current_word = '' if trailing_space else words[-1]
            if not current_word.startswith('-'):
                prev = words[-1] if trailing_space else (words[-2] if len(words) >= 2 else '')
                if prev == '--orcid':
                    yield from self._yield_user_completions(current_word)
                return

            for flag in sub_parser._option_string_actions:
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
            fetch_projects, fetch_deletions, fetch_user_label,
            fetch_current_project, fetch_current_session, fetch_api_label,
        )
        ag = whoami_info.get('access_group_name', '')
        self.is_admin = isinstance(ag, str) and ag.startswith('admin')

        self.state = {
            'user_label':    fetch_user_label(self.client, whoami_info),
            'projects':      fetch_projects(self.client),
            'project':       fetch_current_project(),
            'session':       fetch_current_session(),
            'api_label':     fetch_api_label(),
            'debug':         False,
            'deletions':     fetch_deletions(self.client) if self.is_admin else [],
            'recent_mfids':  deque(maxlen=15),
        }

    def refresh(self):
        """Re-fetch projects, user info, and deletions. Updates state + completer."""
        from .helpers import (
            fetch_projects, fetch_deletions, fetch_user_label,
            fetch_current_project, fetch_current_session, fetch_api_label,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            proj_f = pool.submit(fetch_projects, self.client)
            del_f  = pool.submit(fetch_deletions, self.client) if self.is_admin else None
            new_projects  = proj_f.result()
            new_deletions = del_f.result() if del_f is not None else []
        self.state['projects']   = new_projects
        self.state['user_label'] = fetch_user_label(self.client)
        self.state['project']    = fetch_current_project()
        self.state['session']    = fetch_current_session()
        self.state['api_label']  = fetch_api_label()
        self.state['deletions']  = new_deletions
        if self.completer is not None:
            self.completer._projects  = new_projects
            self.completer._deletions = new_deletions
        print(f"Refreshed: {len(new_projects)} projects, user info reloaded.")

    def _toolbar(self):
        from prompt_toolkit.application import get_app
        proj  = self.state.get('project', '')
        sess  = self.state.get('session', '')
        label = f'{proj} / {sess}' if sess else proj
        if len(label) > 22:
            label = label[:21] + '…'
        proj_content = f'🔬 {label}'.ljust(25)
        clock        = datetime.now().strftime('%H:%M')

        left_str  = f' {proj_content} '
        mid_str   = f' 🧸 {self.state.get("user_label", "?")} '
        right_str = f' 🔗 {self.state.get("api_label", "?")}  │  {clock} '
        debug_str = ' DEBUG ' if self.state.get('debug') else ''

        try:
            term_width = get_app().output.get_size().columns
        except Exception:
            term_width = 80

        from prompt_toolkit.formatted_text import HTML
        pad = ' ' * max(0, term_width - _vlen(left_str) - _vlen(mid_str)
                        - len(debug_str) - _vlen(right_str))
        return HTML(
            f'<tb-project>{left_str}</tb-project>'
            f'{mid_str}{pad}'
            f'<tb-debug>{debug_str}</tb-debug>'
            f'<tb-clock>{right_str}</tb-clock>'
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
            rtype      = last['type']
            data       = last['data']
            graph_data = self._resolve_future(last, '_graph_future') if last.get('graph') else None
            if rtype == 'dataset':
                from .dataset import _show_dataset
                prefetched = {
                    'keywords': self._resolve_future(last, '_keywords_future', []),
                    'af_list':  self._resolve_future(last, '_files_future', []),
                    'link_map': self._resolve_future(last, '_links_future', {}),
                }
                _show_dataset(data, self.client, verbose=last['verbose'],
                              graph=last['graph'],
                              include_metadata=last.get('include_metadata', False),
                              graph_data=graph_data, prefetched=prefetched)
            elif rtype == 'sample':
                from .sample import _show_sample
                _show_sample(data, self.client, verbose=last['verbose'],
                             graph=last['graph'], graph_data=graph_data)
        except Exception as e:
            logger.error(f"Error rendering resource: {e}")

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
                ('use PROJECT',   'switch active project'),
                ('unuse',         'clear active project'),
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
            try:
                from crucible.cli.config import set_config_value
                set_config_value('current_project', project_id)
                set_config_value('current_session', '')
                print(f"Switched to project: {project_id}")
                self.state['project'] = project_id
                self.state['session'] = ''
            except Exception as e:
                logger.error(f"Error switching project: {e}")
            return True

        if line == 'unuse':
            try:
                from crucible.cli.config import set_config_value
                set_config_value('current_project', '')
                set_config_value('current_session', '')
                print("Cleared current project and session.")
                self.state['project'] = '(no project set)'
                self.state['session'] = ''
            except Exception as e:
                logger.error(f"Error clearing project: {e}")
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

        # Reload client and full state after config set / config edit
        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'edit'):
            from crucible.config import config as _cfg
            from crucible.client import CrucibleClient
            try:
                _cfg.reload()
                self.client = CrucibleClient()
                if self.completer is not None:
                    self.completer._client       = self.client
                    self.completer._unlink_cache = {}
                    self.completer._users        = []
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

        _u     = info.get('user_info', {})
        _first = _u.get('first_name', '').strip() or \
                 _u.get('last_name', '').strip() or \
                 info.get('access_group_name') or 'there'
        print(f"\nWelcome to the Crucible interactive shell, {_first}.\n"
              "(type 'help' for commands, 'exit' to quit)")

        self.completer = _CrucibleCompleter(
            self.parser,
            client=self.client,
            projects=self.state['projects'],
            deletions=self.state['deletions'],
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
            style=Style.from_dict({
                'bottom-toolbar':      'noinherit bg:#1c9aad fg:#E8F4F7',
                'bottom-toolbar.text': 'noinherit bg:#1c9aad fg:#E8F4F7',
                'tb-project':          'noinherit bg:#A8C4CD fg:#0D2B35',
                'tb-clock':            'noinherit bg:#A8C4CD fg:#0D2B35',
                'tb-debug':            'noinherit bg:#E8820A fg:#1C1C1C bold',
            }),
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
