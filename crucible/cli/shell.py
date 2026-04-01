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


# Argparse-backed completer (used by prompt_toolkit)
def _get_subparser_map(parser):
    """Return {name: subparser} for a parser's subcommands, or {} if none."""
    for action in parser._actions:
        if hasattr(action, 'choices') and isinstance(action.choices, dict):
            return action.choices or {}
    return {}


def _fetch_deletions():
    """Fetch pending deletion requests for autocomplete."""
    try:
        from crucible.config import config
        return config.client.deletions.list(status='pending')
    except Exception:
        return []


def _fetch_projects():
    """Fetch all projects once at startup. Returns [(project_id, title), ...]."""
    try:
        from crucible.config import config
        projects = config.client.projects.list()
        result = [(p.get('project_id', ''),
                   p.get('title') or '-')
                  for p in projects if p.get('project_id')]
        logger.debug(f"_fetch_projects: got {len(result)} projects")
        return result
    except Exception as e:
        logger.debug(f"_fetch_projects failed: {e}")
        return []



try:
    from prompt_toolkit.completion      import Completer, Completion
    from prompt_toolkit.formatted_text  import HTML as _HTML

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource → subcommand → flags.

        Also handles the built-in `use PROJECT_ID` command for project switching.
        """

        def __init__(self, parser, projects=None, deletions=None):
            self._top = _get_subparser_map(parser)
            self._projects  = projects  or []
            self._deletions = deletions or []

        def get_completions(self, document, complete_event):
            text  = document.text_before_cursor
            words = text.split()
            # Are we in the middle of a word, or just after a space?
            trailing_space = text.endswith(' ')

            #  level 0: complete top-level resource (+ built-in 'use') 
            if not words or (len(words) == 1 and not trailing_space):
                prefix = words[0] if words else ''
                candidates = list(self._top) + ['use', 'unuse', 'refresh', 'reload', 'debug']
                for name in candidates:
                    if name.startswith(prefix):
                        yield Completion(name + ' ', start_position=-len(prefix))
                return

            resource = words[0]

            #  built-in: debug on|off
            if resource == 'debug':
                if len(words) > 2:
                    return
                prefix = words[1] if len(words) == 2 and not trailing_space else ''
                for choice in ('on', 'off'):
                    if choice.startswith(prefix):
                        yield Completion(choice + ' ', start_position=-len(prefix))
                return

            #  built-in: use <project_id>
            if resource == 'use':
                if len(words) > 2:
                    return  # already have a project arg
                prefix = words[1] if len(words) == 2 and not trailing_space else ''
                if not self._projects:
                    self._projects = _fetch_projects()
                for pid, title in self._projects:
                    if pid.startswith(prefix):
                        yield Completion(pid + ' ', start_position=-len(prefix),
                                         display=_HTML(f'<b>{pid}</b>'),
                                         display_meta=_HTML(f'<ansibrightblack>{title}</ansibrightblack>'))
                return


            #  built-in: deletion approve/reject <ID> [<ID> ...]
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

            sub_map  = _get_subparser_map(self._top.get(resource)) \
                       if resource in self._top else {}

            #  level 1: complete subcommand 
            if len(words) == 1 or (len(words) == 2 and not trailing_space):
                prefix = words[1] if len(words) == 2 else ''
                for name in sub_map:
                    if name.startswith(prefix):
                        yield Completion(name + ' ', start_position=-len(prefix))
                return

            #  level 2+: complete flags for the chosen subcommand
            subcommand = words[1]

            #  special case: config set <KEY> [VALUE]
            if resource == 'config' and subcommand == 'set':
                try:
                    from crucible.config.config import Config as _Cfg
                    config_keys = list(_Cfg._CONFIG_MAP)
                except Exception:
                    return
                # Complete the KEY (words: ['config','set'] + optional partial key)
                if not (len(words) == 3 and trailing_space) and len(words) <= 3:
                    prefix = words[2] if len(words) == 3 else ''
                    for key in config_keys:
                        if key.startswith(prefix):
                            yield Completion(key + ' ', start_position=-len(prefix))
                # Complete VALUE for current_project from the project list
                elif len(words) >= 3 and words[2] == 'current_project':
                    prefix = words[3] if len(words) == 4 and not trailing_space else ''
                    if not self._projects:
                        self._projects = _fetch_projects()
                    for pid, title in self._projects:
                        if pid.startswith(prefix):
                            yield Completion(pid + ' ', start_position=-len(prefix),
                                             display=_HTML(f'<b>{pid}</b>'),
                                             display_meta=_HTML(f'<ansibrightblack>{title}</ansibrightblack>'))
                return

            sub_parser = sub_map.get(subcommand)
            if sub_parser is None:
                return

            current_word = '' if trailing_space else words[-1]
            if not current_word.startswith('-'):
                return  # positional args — too context-specific to complete

            for flag in sub_parser._option_string_actions:
                if flag.startswith(current_word):
                    yield Completion(flag + ' ', start_position=-len(current_word))

except ImportError:
    _CrucibleCompleter = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vlen(s):
    """Visual (terminal column) width of *s*; falls back to len() if wcwidth unavailable."""
    try:
        from wcwidth import wcswidth
        w = wcswidth(s)
        return w if w >= 0 else len(s)
    except ImportError:
        return len(s)


# ---------------------------------------------------------------------------
# Shell entry point
# ---------------------------------------------------------------------------

def run(parser):
    """Start the interactive shell. Called from main() when no command given."""
    _run_prompt_toolkit(parser) if _CrucibleCompleter else _run_readline(parser)


def _dispatch(parser, line, completer=None, state=None):
    """Parse and execute one line. Returns False to signal exit."""
    from . import _remap_deprecated, setup_logging

    line = line.strip()
    if not line:
        return True
    if line in ('exit', 'quit'):
        return False
    if line == 'help':
        parser.print_help()
        return True

    # Built-in: use <project_id>
    if line.startswith('use ') or line == 'use':
        parts = line.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            print("Usage: use <project_id>")
            return True
        project_id = parts[1].strip()
        try:
            from crucible.cli.config import set_config_value
            set_config_value('current_project', project_id)
            set_config_value('current_session', '')  # session is project-scoped
            print(f"Switched to project: {project_id}")
            if state is not None:
                state['project'] = project_id
                state['session'] = ''
        except Exception as e:
            logger.error(f"Error switching project: {e}")
        return True

    # Built-in: unuse — clear project and session
    if line == 'unuse':
        try:
            from crucible.cli.config import set_config_value
            set_config_value('current_project', '')
            set_config_value('current_session', '')
            print("Cleared current project and session.")
            if state is not None:
                state['project'] = '(no project set)'
                state['session'] = ''
        except Exception as e:
            logger.error(f"Error clearing project: {e}")
        return True

    # Built-in: refresh — re-fetch projects and user label
    if line == 'refresh':
        try:
            from crucible.config import config as _cfg
            _cfg.reload()
        except Exception:
            pass
        new_projects = _fetch_projects()
        if completer is not None:
            completer._projects = new_projects
        if state is not None:
            state['projects']   = new_projects
            state['user_label'] = _fetch_user_label()
            state['project']    = _fetch_current_project()
            state['session']    = _fetch_current_session()
            state['api_label']  = _fetch_api_label()
            new_deletions = _fetch_deletions()
            state['deletions']  = new_deletions
            if completer is not None:
                completer._deletions = new_deletions
            print(f"Refreshed: {len(new_projects)} projects, user info reloaded.")
        else:
            print(f"Refreshed: {len(new_projects)} projects available.")
        return True

    # Built-in: reload — re-exec the process to pick up source code changes
    if line == 'reload':
        import os
        print("Reloading...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # Built-in: debug on|off — set debug logging for the session
    if line == 'debug' or line.startswith('debug '):
        parts = line.split()
        current = (state or {}).get('debug', False)
        if len(parts) == 1:
            print(f"Debug is {'on' if current else 'off'}.")
            return True
        action = parts[1].lower()
        if action not in ('on', 'off'):
            print("Usage: debug on | debug off")
            return True
        from . import setup_logging
        on = (action == 'on')
        if state is not None:
            state['debug'] = on
        setup_logging(debug=on)
        print(f"Debug {'enabled' if on else 'disabled'}.")
        return True

    try:
        argv = _remap_deprecated(shlex.split(line))
        args = parser.parse_args(argv)
        setup_logging(debug=getattr(args, 'debug', False) or (state or {}).get('debug', False))
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    except SystemExit:
        pass  # subcommands call sys.exit() on error — keep the shell alive
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        logger.error(f"Error: {e}")

    # Re-fetch pending deletions after any deletion command (list changes)
    if state is not None:
        words = line.split()
        if len(words) >= 2 and words[0] == 'deletion' and words[1] in ('approve', 'reject', 'request'):
            new_deletions       = _fetch_deletions()
            state['deletions']  = new_deletions
            if completer is not None:
                completer._deletions = new_deletions

    # Reload identity after config set / config edit (credentials may have changed)
    if state is not None:
        words = line.split()
        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'edit'):
            state['user_label'] = _fetch_user_label()
            state['project']    = _fetch_current_project()
            state['session']    = _fetch_current_session()
            state['api_label']  = _fetch_api_label()
            new_projects        = _fetch_projects()
            state['projects']   = new_projects
            new_deletions       = _fetch_deletions()
            state['deletions']  = new_deletions
            if completer is not None:
                completer._projects  = new_projects
                completer._deletions = new_deletions

    return True


def _fetch_user_label():
    """Fetch current user info once at startup. Returns a display string."""
    try:
        from crucible.config import config
        info = config.client.whoami()
        user = info.get('user_info', {})
        first = user.get('first_name', '')
        last  = user.get('last_name', '')
        name  = f"{first} {last}".strip()
        return name or info.get('access_group_name') or '?'
    except Exception:
        return '?'


def _fetch_current_project():
    """Return the current project ID (or a placeholder string)."""
    try:
        from crucible.config import config
        return config.current_project or '(no project set)'
    except Exception:
        return '?'


def _fetch_current_session():
    """Return the current session name, or empty string if none."""
    try:
        from crucible.config import config
        return config.current_session or ''
    except Exception:
        return ''


def _fetch_api_label():
    """Return 'api: <last-path-segment>' derived from the configured api_url."""
    try:
        from urllib.parse import urlparse
        from crucible.config import config
        parsed = urlparse(config.api_url or '')
        parts = [p for p in parsed.path.split('/') if p]
        label = parts[-1] if parts else (parsed.netloc or '?')
        return f"api: {label}"
    except Exception:
        return 'api: ?'


def _run_prompt_toolkit(parser):
    from prompt_toolkit                  import PromptSession
    from prompt_toolkit.history          import FileHistory
    from prompt_toolkit.auto_suggest     import AutoSuggestFromHistory
    from prompt_toolkit.styles           import Style
    from prompt_toolkit.key_binding      import KeyBindings
    from prompt_toolkit.filters          import completion_is_selected
    from prompt_toolkit.formatted_text   import HTML
    from prompt_toolkit.completion       import ThreadedCompleter
    from platformdirs import user_data_dir
    import os

    history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    # Verify connection — exit early rather than starting a broken shell.
    # The spinner message is mutable so retry warnings can update it in-place
    # instead of printing on a separate line and fighting with the spinner.
    _spin_state = {'msg': 'Connecting to Crucible'}
    _stop       = threading.Event()
    _is_tty     = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    _FRAMES     = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    _RETRY_RE   = _re.compile(r'Retry\(total=(\d+)')

    def _spin():
        for frame in itertools.cycle(_FRAMES):
            if _stop.is_set():
                break
            sys.stdout.write(f'\r  {_spin_state["msg"]}  {frame}')
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write('\r\033[2K')
        sys.stdout.flush()

    class _RetryToSpinner(logging.Filter):
        """Redirect urllib3 retry warnings into the spinner message."""
        def filter(self, record):
            msg = record.getMessage()
            if 'Retrying' not in msg:
                return True
            m = _RETRY_RE.search(msg)
            n = m.group(1) if m else '?'
            _spin_state['msg'] = f'Retrying... ({n} left)'
            return False  # swallow — shown in spinner instead

    _filt = _RetryToSpinner()
    for _h in logging.getLogger().handlers:
        _h.addFilter(_filt)

    if _is_tty:
        _spin_thread = threading.Thread(target=_spin, daemon=True)
        _spin_thread.start()
    else:
        print('  Connecting to Crucible...')

    try:
        from crucible.config import config as _cfg
        _info = _cfg.client.whoami()
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

    # Build user label from the whoami response already in hand
    _u     = _info.get('user_info', {})
    _name  = f"{_u.get('first_name', '')} {_u.get('last_name', '')}".strip()
    _user_label = _name or _info.get('access_group_name') or '?'
    _projects   = _fetch_projects()

    # Build API label: last path segment (e.g. "api: testapi-staging")
    from urllib.parse import urlparse as _urlparse
    _parsed     = _urlparse(_cfg.api_url or '')
    _path_parts = [p for p in _parsed.path.split('/') if p]
    _api_label  = f"api: {_path_parts[-1] if _path_parts else (_parsed.netloc or '?')}"

    _first = _u.get('first_name', '').strip() or _name or _info.get('access_group_name') or 'there'
    print(f"\nWelcome to the Crucible interactive shell, {_first}.\n"
          "(type 'help' for commands, 'exit' to quit)")

    # Mutable state — reloaded by refresh / config set / config edit
    state = {
        'user_label': _user_label,
        'projects':   _projects,
        'project':    _fetch_current_project(),
        'session':    _fetch_current_session(),
        'api_label':  _api_label,
        'debug':      False,
        'deletions':  _fetch_deletions(),
    }

    def _toolbar():
        from prompt_toolkit.application import get_app
        proj = state['project']
        sess = state['session']
        label = f'{proj} / {sess}' if sess else proj
        if len(label) > 22:
            label = label[:21] + '…'
        proj_content = f'🔬 {label}'.ljust(25)
        clock        = datetime.now().strftime('%H:%M')

        left_str  = f' {proj_content} '
        mid_str   = f' 🧸 {state["user_label"]} '
        right_str = f' 🔗 {state["api_label"]}  │  {clock} '
        debug_str = ' DEBUG ' if state['debug'] else ''

        try:
            term_width = get_app().output.get_size().columns
        except Exception:
            term_width = 80

        pad = ' ' * max(0, term_width - _vlen(left_str) - _vlen(mid_str)
                        - len(debug_str) - _vlen(right_str))
        return HTML(
            f'<tb-project>{left_str}</tb-project>'
            f'{mid_str}{pad}'
            f'<tb-debug>{debug_str}</tb-debug>'
            f'<tb-clock>{right_str}</tb-clock>'
        )

    # When a completion is highlighted in the dropdown, Enter should accept it
    # (insert the text) rather than submit the line.
    kb = KeyBindings()

    @kb.add('enter', filter=completion_is_selected)
    def _accept_completion(event):
        buff = event.app.current_buffer
        buff.apply_completion(buff.complete_state.current_completion)

    completer = _CrucibleCompleter(parser, projects=state['projects'],
                                   deletions=state['deletions'])
    session = PromptSession(
        history=FileHistory(history_path),
        auto_suggest=AutoSuggestFromHistory(),
        completer=ThreadedCompleter(completer),
        complete_while_typing=True,
        key_bindings=kb,
        bottom_toolbar=_toolbar,
        style=Style.from_dict({
            # prompt_toolkit styles the toolbar at two levels; both need overriding
            'bottom-toolbar':      'noinherit bg:#1c9aad fg:#E8F4F7',
            'bottom-toolbar.text': 'noinherit bg:#1c9aad fg:#E8F4F7',
            'tb-project':          'noinherit bg:#A8C4CD fg:#0D2B35',
            'tb-clock':            'noinherit bg:#A8C4CD fg:#0D2B35',
            'tb-debug':            'noinherit bg:#E8820A fg:#1C1C1C bold',
        }),
    )

    # Background thread: invalidate the toolbar once per minute so the clock
    # updates even when the user is idle.
    _clock_stop = threading.Event()

    def _clock_tick():
        # Sleep to the next minute boundary, then fire every 60 s.
        secs_to_next = 60 - datetime.now().second
        if _clock_stop.wait(timeout=secs_to_next):
            return
        while not _clock_stop.is_set():
            try:
                session.app.invalidate()
            except Exception:
                pass
            _clock_stop.wait(timeout=60)

    threading.Thread(target=_clock_tick, daemon=True).start()

    while True:
        try:
            line = session.prompt(_PROMPT)
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            break
        if not _dispatch(parser, line, completer=completer, state=state):
            break
        print()  # blank line between commands for readability

    _clock_stop.set()


def _run_readline(parser):
    """Fallback shell using stdlib readline for history."""
    print(_BANNER)
    try:
        import readline  # noqa: F401 — activates history/completion automatically
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
        if not _dispatch(parser, line):
            break
        print()
