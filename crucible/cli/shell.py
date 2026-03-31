#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

import sys
import time
import shlex
import itertools
import threading
import logging

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
    from prompt_toolkit.completion import Completer, Completion

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource → subcommand → flags.

        Also handles the built-in `use PROJECT_ID` command for project switching.
        """

        def __init__(self, parser, projects=None):
            self._top = _get_subparser_map(parser)
            self._projects = projects or []

        def get_completions(self, document, complete_event):
            text  = document.text_before_cursor
            words = text.split()
            # Are we in the middle of a word, or just after a space?
            trailing_space = text.endswith(' ')

            #  level 0: complete top-level resource (+ built-in 'use') 
            if not words or (len(words) == 1 and not trailing_space):
                prefix = words[0] if words else ''
                candidates = list(self._top) + ['use', 'unuse', 'refresh']
                for name in candidates:
                    if name.startswith(prefix):
                        yield Completion(name + ' ', start_position=-len(prefix))
                return

            resource = words[0]

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
                                         display_meta=title)
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
                                             display_meta=title)
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
# Shell entry point
# ---------------------------------------------------------------------------

def run(parser):
    """Start the interactive shell. Called from main() when no command given."""
    print(_BANNER)
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
        new_projects = _fetch_projects()
        if completer is not None:
            completer._projects = new_projects
        if state is not None:
            state['projects']   = new_projects
            state['user_label'] = _fetch_user_label()
            state['project']    = _fetch_current_project()
            state['session']    = _fetch_current_session()
            print(f"Refreshed: {len(new_projects)} projects, user info reloaded.")
        else:
            print(f"Refreshed: {len(new_projects)} projects available.")
        return True

    try:
        argv = _remap_deprecated(shlex.split(line))
        args = parser.parse_args(argv)
        setup_logging(debug=getattr(args, 'debug', False))
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

    # Reload identity after config set / config edit (credentials may have changed)
    if state is not None:
        words = line.split()
        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'edit'):
            state['user_label'] = _fetch_user_label()
            state['project']    = _fetch_current_project()
            state['session']    = _fetch_current_session()
            new_projects        = _fetch_projects()
            state['projects']   = new_projects
            if completer is not None:
                completer._projects = new_projects

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
        email = user.get('lbl_email') or user.get('email') or ''
        if name and email:
            return f"{name} ({email})"
        return name or email or '?'
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


def _run_prompt_toolkit(parser):
    from prompt_toolkit                  import PromptSession
    from prompt_toolkit.history          import FileHistory
    from prompt_toolkit.auto_suggest     import AutoSuggestFromHistory
    from prompt_toolkit.styles           import Style
    from prompt_toolkit.key_binding      import KeyBindings
    from prompt_toolkit.filters          import completion_is_selected
    from prompt_toolkit.formatted_text   import HTML
    from platformdirs import user_data_dir
    import os

    history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    # Spin while fetching initial state (two API calls run in parallel)
    _msg  = 'Connecting to Crucible'
    _stop = threading.Event()
    _is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    def _spin():
        for frame in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']):
            if _stop.is_set():
                break
            sys.stdout.write(f'\r  {_msg}...  {frame}')
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write('\r' + ' ' * (len(_msg) + 8) + '\r')
        sys.stdout.flush()

    if _is_tty:
        threading.Thread(target=_spin, daemon=True).start()
    else:
        print(f'  {_msg}...')

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_user     = pool.submit(_fetch_user_label)
        f_projects = pool.submit(_fetch_projects)
        _user_label = f_user.result()
        _projects   = f_projects.result()

    _stop.set()

    # Mutable state — reloaded by refresh / config set / config edit
    state = {
        'user_label': _user_label,
        'projects':   _projects,
        'project':    _fetch_current_project(),
        'session':    _fetch_current_session(),
    }

    def _toolbar():
        proj = state['project']
        sess = state['session']
        label = f'{proj} / {sess}' if sess else proj
        proj_content = f'🔬  {label}'.ljust(34)
        return HTML(
            f'<tb-project> {proj_content} </tb-project>'
            f' 🧸  {state["user_label"]} '
        )

    # When a completion is highlighted in the dropdown, Enter should accept it
    # (insert the text) rather than submit the line.
    kb = KeyBindings()

    @kb.add('enter', filter=completion_is_selected)
    def _accept_completion(event):
        buff = event.app.current_buffer
        buff.apply_completion(buff.complete_state.current_completion)

    completer = _CrucibleCompleter(parser, projects=state['projects'])
    session = PromptSession(
        history=FileHistory(history_path),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_while_typing=True,   # only complete on Tab
        key_bindings=kb,
        bottom_toolbar=_toolbar,
        style=Style.from_dict({
            # prompt_toolkit styles the toolbar at two levels; both need overriding
            'bottom-toolbar':      'noinherit bg:#1c9aad fg:#E8F4F7',
            'bottom-toolbar.text': 'noinherit bg:#1c9aad fg:#E8F4F7',
            'tb-project':          'noinherit bg:#A8C4CD fg:#0D2B35',
        }),
    )

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


def _run_readline(parser):
    """Fallback shell using stdlib readline for history."""
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
