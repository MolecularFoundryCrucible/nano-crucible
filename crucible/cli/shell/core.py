"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

import os
import sys
import re as _re
import time
import shlex
import shutil
import threading
import itertools
import logging
from collections import deque
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ._common import PROMPT, shell_color_depth, shell_html, shell_style_rules, vlen
from .banner import print_shell_banner
from .builtins import find_builtin

try:
    from .completer import CrucibleCompleter
except ImportError:
    CrucibleCompleter = None

logger = logging.getLogger(__name__)


class CrucibleShell:
    """Interactive Crucible shell.

    Holds the process-wide shared client (self.client), shared mutable state
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
        if CrucibleCompleter:
            self._run_prompt_toolkit()
        else:
            self._run_readline()

    def _verify_connection(self):
        """Spinner + whoami. Sets self.client. Exits on failure."""
        from crucible.config import get_client

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
            self.client = get_client()
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
        from ..helpers import (
            fetch_projects, fetch_deletions, fetch_join_requests, fetch_service_accounts,
            fetch_user_label, fetch_project_context, fetch_api_label, fetch_api_attention,
        )
        deletions     = fetch_deletions(self.client)
        join_requests = fetch_join_requests(self.client)
        self.is_admin = self.client.can_elevate or deletions is not None
        service_accounts = (fetch_service_accounts(self.client)
                            if self._can_manage_service_accounts() else None)

        project_id, project_source = fetch_project_context()
        self.state = {
            'user_label':        fetch_user_label(self.client, whoami_info),
            'projects':          fetch_projects(self.client),
            'project':           project_id,
            'project_source':    project_source,
            'api_label':         fetch_api_label(),
            'api_attention':     fetch_api_attention(),
            'debug':             False,
            'elevated':          self.client.is_elevated,
            'deletions':         deletions or [],
            'join_requests':     join_requests or [],
            'service_accounts':  service_accounts or [],
            'recent_mfids':      deque(maxlen=15),
        }

    def _can_manage_service_accounts(self):
        """Whether service-account administration is reachable for this caller."""
        return bool(self.client.can_elevate
                    or self.client.capabilities.get('can_manage_service_accounts'))

    def _apply_elevated(self, on):
        """Set elevation on the shared client and the toolbar state.

        Turning it off pins "normal" rather than clearing the mode, because
        sending no header at all leaves a platform administrator elevated.
        """
        self.state['elevated'] = on
        if self.client is not None:
            self.client.privilege_mode = 'elevated' if on else 'normal'

    def refresh(self):
        """Re-fetch projects, user info, deletions, join requests, and service accounts. Updates state + completer."""
        from ..helpers import (
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
        self.is_admin = self.client.can_elevate or new_deletions is not None
        self.state['elevated']         = self.client.is_elevated
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
        proj_content = project_label + ' ' * max(0, 25 - vlen(project_label))
        clock        = datetime.now().strftime('%H:%M')

        left_str  = f' {proj_content} '
        mid_str   = f' 🧸 {self.state.get("user_label", "?")} '
        api_str   = f' 🔗 {self.state.get("api_label", "?")} '
        clock_str = f' {clock} '
        separator = ' │ '
        debug_str = ' DEBUG ' if self.state.get('debug') else ''
        elevated_str = ' ELEVATED ' if self.state.get('elevated') else ''

        try:
            term_width = get_app().output.get_size().columns
        except Exception:
            term_width = 80

        fixed_width = (
            vlen(left_str) + vlen(mid_str) + vlen(api_str)
            + vlen(clock_str) + 3 * vlen(separator)
            + len(debug_str) + len(elevated_str)
        )
        if debug_str:
            fixed_width += vlen(separator)
        if elevated_str:
            fixed_width += vlen(separator)
        pad = ' ' * max(0, term_width - fixed_width)
        api_tag = 'tb-api-attention' if self.state.get('api_attention') else 'tb-api'
        debug_segment = (
            f'<tb-separator>{separator}</tb-separator><tb-debug>{debug_str}</tb-debug>'
            if debug_str else ''
        )
        elevated_segment = (
            f'<tb-separator>{separator}</tb-separator>'
            f'<tb-elevated>{elevated_str}</tb-elevated>'
            if elevated_str else ''
        )
        return shell_html(
            f'<tb-project>{left_str}</tb-project>'
            f'<tb-separator>{separator}</tb-separator>{mid_str}'
            f'<tb-separator>{separator}</tb-separator><{api_tag}>{api_str}</{api_tag}>'
            f'{pad}{elevated_segment}{debug_segment}'
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
                from ..dataset import _show_dataset
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
                from ..sample import _show_sample
                _show_sample(data, self.client, verbose=last['verbose'],
                             graph=last['graph'],
                             include_metadata=last.get('include_metadata', False),
                             links=links)
        except Exception as e:
            logger.error(f"Error rendering resource: {e}")

    def _activate_project(self, project_id, title=None):
        """Persist a project selection and apply it to the running shell."""
        if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
            from ..helpers import show_warning
            show_warning(
                "CRUCIBLE_CURRENT_PROJECT controls the current project. "
                "Unset it before using the shell project selector."
            )
            return False
        from ..config import set_config_value
        set_config_value('current_project', project_id)
        self.state['project'] = project_id
        self.state['project_source'] = 'config file'
        label = f"{project_id} - {title}" if title else project_id
        print(f"Using project: {label} (remembered)")
        return True

    def _dispatch(self, line):
        """Parse and execute one command line. Returns False to signal exit."""
        from .. import _remap_deprecated, setup_logging

        line = line.strip()
        if not line:
            return True
        if line in ('exit', 'quit'):
            return False
        handler = find_builtin(line)
        if handler is not None:
            return handler(self, line)

        words = line.split()
        try:
            argv = _remap_deprecated(shlex.split(line))
            args = self.parser.parse_args(argv)
            setup_logging(debug=getattr(args, 'debug', False) or self.state.get('debug', False))
            # An inline --elevated applies to this command only; the session
            # toggle is what persists.
            inline_elevated = getattr(args, 'elevated', False)
            session_mode = self.client.privilege_mode if self.client else None
            session_elevated = self.state.get('elevated', False)
            if inline_elevated:
                self._apply_elevated(True)
            if hasattr(args, 'func'):
                args._shell_state = self.state
                try:
                    args.func(args)
                finally:
                    if inline_elevated:
                        self.state['elevated'] = session_elevated
                        if self.client is not None:
                            self.client.privilege_mode = session_mode
                from ..helpers import fetch_project_context
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
            from ..helpers import fetch_deletions
            new_deletions = fetch_deletions(self.client)
            self.state['deletions'] = new_deletions
            if self.completer is not None:
                self.completer._deletions = new_deletions

        # Re-fetch pending join requests after any ag/access-group command
        if (len(words) >= 2 and words[0] in ('ag', 'access-group')
                and words[1] in ('approve', 'reject', 'request')):
            from ..helpers import fetch_join_requests
            new_join_requests = fetch_join_requests(self.client)
            self.state['join_requests'] = new_join_requests
            if self.completer is not None:
                self.completer._join_requests = new_join_requests

        # Re-fetch service accounts after any sa/service-account command that changes the list
        if (self.is_admin and len(words) >= 2 and words[0] in ('sa', 'service-account')
                and words[1] in ('create', 'update', 'rotate-key')):
            from ..helpers import fetch_service_accounts
            new_service_accounts = fetch_service_accounts(self.client)
            self.state['service_accounts'] = new_service_accounts or []
            if self.completer is not None:
                self.completer._service_accounts = new_service_accounts or []

        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'unset', 'edit'):
            from crucible.config import config as _cfg
            from crucible.config import get_client
            try:
                _cfg.reload()
                self.client = get_client()
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

        print_shell_banner(shutil.get_terminal_size((80, 24)).columns)

        _u     = info.get('user_info', {})
        _first = _u.get('first_name', '').strip() or \
                 _u.get('last_name', '').strip() or \
                 info.get('access_group_name') or 'there'
        print(f"\nWelcome to the Crucible interactive shell, {_first}.\n"
              "(type 'help' for commands, 'exit' to quit)")
        if self.state.get('project_source') == 'environment':
            from ..helpers import show_warning
            show_warning(
                "CRUCIBLE_CURRENT_PROJECT is controlling the current project and is deprecated. "
                "Use 'use PROJECT_ID' to save a selection after unsetting the environment variable."
            )

        self.completer = CrucibleCompleter(
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
            style=Style.from_dict(shell_style_rules()),
            color_depth=shell_color_depth(),
        )

        threading.Thread(target=self._clock_tick, daemon=True).start()

        while True:
            try:
                line = self._session.prompt(PROMPT)
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
                line = input(PROMPT)
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
