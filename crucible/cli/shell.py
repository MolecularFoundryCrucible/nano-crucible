#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

import sys
import re as _re
import time
import shlex
import threading
import itertools
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_BANNER = """\

Crucible interactive shell  (type 'help' for commands, 'exit' to quit)"""

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


try:
    from prompt_toolkit.completion     import Completer, Completion
    from prompt_toolkit.formatted_text import HTML as _HTML

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource → subcommand → flags."""

        def __init__(self, parser, client=None, projects=None, deletions=None):
            self._top       = _get_subparser_map(parser)
            self._client    = client
            self._projects  = projects  or []
            self._deletions = deletions or []

        def _lazy_projects(self):
            if not self._projects and self._client is not None:
                from .helpers import fetch_projects
                self._projects = fetch_projects(self._client)
            return self._projects

        def get_completions(self, document, complete_event):
            text           = document.text_before_cursor
            words          = text.split()
            trailing_space = text.endswith(' ')

            if not words or (len(words) == 1 and not trailing_space):
                prefix = words[0] if words else ''
                candidates = list(self._top) + ['use', 'unuse', 'refresh', 'reload', 'debug']
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
                                         display_meta=_HTML(f'<ansibrightblack>{title}</ansibrightblack>'))
                return

            if resource == 'deletion' and len(words) >= 2 and words[1] in ('approve', 'reject'):
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
                        parts.append(f'<b>{name}</b>')
                    if reason:
                        parts.append(f'<ansibrightblack>{reason}</ansibrightblack>')
                    yield Completion(
                        did + ' ',
                        start_position=-len(prefix),
                        display=_HTML(f'<b>{did}</b>'),
                        display_meta=_HTML(' | '.join(parts)),
                    )
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
                                             display_meta=_HTML(f'<ansibrightblack>{title}</ansibrightblack>'))
                return

            sub_parser  = sub_map.get(subcommand)
            if sub_parser is None:
                return

            current_word = '' if trailing_space else words[-1]
            if not current_word.startswith('-'):
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
        self.state = {
            'user_label': fetch_user_label(self.client),
            'projects':   fetch_projects(self.client),
            'project':    fetch_current_project(),
            'session':    fetch_current_session(),
            'api_label':  fetch_api_label(),
            'debug':      False,
            'deletions':  fetch_deletions(self.client),
        }

    def refresh(self):
        """Re-fetch projects, user info, and deletions. Updates state + completer."""
        from .helpers import (
            fetch_projects, fetch_deletions, fetch_user_label,
            fetch_current_project, fetch_current_session, fetch_api_label,
        )
        new_projects = fetch_projects(self.client)
        new_deletions = fetch_deletions(self.client)
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

    def _resolve_graph(self, last):
        """Return cached graph data from the prefetch future, or None."""
        future = last.get('_graph_future')
        if future is None:
            return None
        try:
            return future.result(timeout=15)
        except Exception:
            return None

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
            graph_data = self._resolve_graph(last) if last.get('graph') else None
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
            import os
            print('\033[2J\033[H', end='', flush=True)
            os.execv(sys.executable, [sys.executable] + sys.argv)

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

        # Re-fetch pending deletions after any deletion command
        words = line.split()
        if len(words) >= 2 and words[0] == 'deletion' and words[1] in ('approve', 'reject', 'request'):
            from .helpers import fetch_deletions
            new_deletions = fetch_deletions(self.client)
            self.state['deletions'] = new_deletions
            if self.completer is not None:
                self.completer._deletions = new_deletions

        # Reload identity after config set / config edit
        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'edit'):
            from .helpers import (
                fetch_projects, fetch_deletions, fetch_user_label,
                fetch_current_project, fetch_current_session, fetch_api_label,
            )
            from crucible.config import config as _cfg
            from crucible.client import CrucibleClient
            try:
                _cfg.reload()
                self.client = CrucibleClient()
                if self.completer is not None:
                    self.completer._client = self.client
            except Exception:
                pass
            self.state['user_label'] = fetch_user_label(self.client)
            self.state['project']    = fetch_current_project()
            self.state['session']    = fetch_current_session()
            self.state['api_label']  = fetch_api_label()
            new_projects  = fetch_projects(self.client)
            new_deletions = fetch_deletions(self.client)
            self.state['projects']  = new_projects
            self.state['deletions'] = new_deletions
            if self.completer is not None:
                self.completer._projects  = new_projects
                self.completer._deletions = new_deletions

        return True

    def _run_prompt_toolkit(self):
        from prompt_toolkit                import PromptSession
        from prompt_toolkit.history        import FileHistory
        from prompt_toolkit.auto_suggest   import AutoSuggestFromHistory
        from prompt_toolkit.styles         import Style
        from prompt_toolkit.key_binding    import KeyBindings
        from prompt_toolkit.completion     import ThreadedCompleter
        from platformdirs import user_data_dir
        import os

        history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        print('\033[2J\033[H', end='', flush=True)

        info = self._verify_connection()
        self._init_state(info)

        _u     = info.get('user_info', {})
        _first = _u.get('first_name', '').strip() or \
                 f"{_u.get('first_name', '')} {_u.get('last_name', '')}".strip() or \
                 info.get('access_group_name') or 'there'
        print(f"\nWelcome to the Crucible interactive shell, {_first}.\n"
              "(type 'help' for commands, 'exit' to quit)")

        self.completer = _CrucibleCompleter(
            self.parser,
            client=self.client,
            projects=self.state['projects'],
            deletions=self.state['deletions'],
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
        print(_BANNER)
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
