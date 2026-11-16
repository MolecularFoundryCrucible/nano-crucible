"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
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
from html import escape
from concurrent.futures import Future, ThreadPoolExecutor

from .. import term
from ._common import PROMPT, shell_color_depth, shell_html, shell_style_rules, vlen
from .banner import print_welcome, welcome_rows
from .builtins import find_builtin
from .completer import CrucibleCompleter

logger = logging.getLogger(__name__)


def _in_background(fn, *args):
    """Run fn on a daemon thread, so a slow call never holds up exit."""
    future: Future = Future()

    def work():
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
    threading.Thread(target=work, daemon=True).start()
    return future


def _settle(future, timeout, default=None):
    try:
        return future.result(timeout=timeout)
    except Exception:
        return default


def _startup_error(exc, api_url):
    """One actionable line for a shell that cannot start."""
    import requests
    from crucible.auth.errors import SignInRequired
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return (f"Cannot reach {api_url}. Check your network, or the API URL "
                "('crucible config get api_url').")
    if isinstance(exc, SignInRequired) or isinstance(exc, ValueError):
        return str(exc)
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status == 401:
        return (f"{api_url} refused the credential (401). Run 'crucible login', "
                "or set a new API key with 'crucible config init'.")
    return f"Cannot connect to Crucible: {exc}"


def _needs_sign_in(exc):
    """Whether signing in or configuring a credential would fix a failed start."""
    from crucible.auth.errors import SignInRequired
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    return isinstance(exc, (SignInRequired, ValueError)) or status == 401


SIGNED_OUT_COMMANDS = ('login', 'config', 'status', 'help', 'exit')
_SIGNED_OUT_RETRY = {'login', 'config'}


SLOW_COMMAND_SECONDS = 2.0
_INTERACTIVE_WORDS = {'edit', 'login', 'reload', 'cd', 'init'}


def _report_duration(line, seconds):
    """Note how long a slow command took, like zsh's REPORTTIME.

    Commands that wait on an editor, a browser, or the user are left out,
    since their time is the user's, not Crucible's.
    """
    words = line.split()
    if (seconds < SLOW_COMMAND_SECONDS or not words or line.lstrip().startswith('!')
            or _INTERACTIVE_WORDS & set(words)):
        return
    print(term.dim(f"(took {seconds:.1f}s)"))


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
        self._session  = None         # prompt_toolkit PromptSession
        self._background = {}
        self._idle_lock  = threading.Lock()
        self._idle_timer = None
        self._idle_dropped = 0
        self._signed_out_reason = None

    def run(self):
        """Start the interactive shell."""
        self._run_prompt_toolkit()

    def _verify_connection(self, fatal=True):
        """Spinner + whoami. Sets self.client and returns the whoami info.

        Returns None, with the reason in self._signed_out_reason, when a
        credential is missing or refused; other failures exit when fatal.
        """
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

        from crucible.config import config as _cfg
        try:
            self.client = get_client()
            self._start_background_checks()
            info = self.client.whoami()
        except Exception as e:
            _stop.set()
            if _is_tty:
                _spin_thread.join()
            for _h in logging.getLogger().handlers:
                _h.removeFilter(_filt)
            from crucible.errors import NotSignedInError
            if fatal and not _needs_sign_in(e):
                logger.error(_startup_error(e, _cfg.api_url))
                sys.exit(1)
            self.client = None
            self._signed_out_reason = (f"Not signed in to {_cfg.api_url}."
                                       if isinstance(e, NotSignedInError)
                                       else _startup_error(e, _cfg.api_url))
            return None

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
            auth_label,
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            projects_f = pool.submit(fetch_projects, self.client)
            deletions_f = pool.submit(fetch_deletions, self.client)
            joins_f = pool.submit(fetch_join_requests, self.client)
            accounts_f = (pool.submit(fetch_service_accounts, self.client)
                          if self._can_manage_service_accounts() else None)
            projects = projects_f.result()
            deletions = deletions_f.result()
            join_requests = joins_f.result()
            service_accounts = accounts_f.result() if accounts_f else None

        project_id, project_source = fetch_project_context()
        self.state = {
            'user_label':        fetch_user_label(self.client, whoami_info),
            'auth_label':        auth_label(self.client),
            'projects':          projects,
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
        self._collect_background_checks()

    def _start_background_checks(self):
        """Ask for the API version and for a newer release while startup goes on."""
        from crucible import __version__
        from crucible.config import config as _cfg
        from ..updates import available_update
        self._background = {
            'health': _in_background(self.client.health),
            'update': _in_background(available_update, __version__, _cfg.update_check),
        }

    def _collect_background_checks(self, wait=3.0):
        from crucible import __version__
        from ..helpers import api_version_note
        from ..status import _readiness_details
        health = self._background.get('health')
        version = (_readiness_details(_settle(health, wait)).get('api_version')
                   if health is not None else None)
        self.state['api_version'] = version
        self.state['api_version_note'] = api_version_note(version, __version__)
        update = self._background.get('update')
        if update is not None:
            self.state['update'] = _settle(update, 0.5)

    def _pending_counts(self):
        """Pending deletion reviews and join requests awaiting this caller."""
        deletions = [
            d for d in self.state.get('deletions') or []
            if ((d.get('capabilities') or {}).get('can_review') is not False)
        ]
        return len(deletions), len(self.state.get('join_requests') or [])

    def _welcome_rows(self, whoami_info):
        """Session summary shown beside the mark at startup."""
        from crucible import __version__
        from crucible.config import config as _cfg

        user = whoami_info.get('user_info') or {}
        first_name = ((user.get('first_name') or '').strip()
                      or (user.get('last_name') or '').strip()
                      or whoami_info.get('access_group_name') or 'there')
        full_name = ' '.join(part for part in (
            (user.get('first_name') or '').strip(),
            (user.get('last_name') or '').strip()) if part)
        username = user.get('username')
        if full_name and username:
            user_label = f'{full_name} (@{username})'
        else:
            user_label = full_name or (f'@{username}' if username else None)
        from ..updates import upgrade_command
        from ..whoami import credential_label
        deletions, joins = self._pending_counts()
        latest = self.state.get('update')
        return welcome_rows(
            version=__version__,
            first_name=first_name,
            user_label=user_label or self.state.get('user_label') or '?',
            platform_role=self.client.authorization.platform_role,
            api_url=_cfg.api_url,
            project=self.state.get('project'),
            elevated=self.state.get('elevated', False),
            deletions=deletions,
            joins=joins,
            api_name=self.state.get('api_label'),
            api_version=self.state.get('api_version'),
            signed_in_with=credential_label(self.client),
            update=(latest, upgrade_command()) if latest else None,
        )

    def _print_pending(self):
        """Mention pending reviews once, so they do not need a toolbar slot."""
        deletions, joins = self._pending_counts()
        parts = []
        if deletions:
            parts.append(f"{deletions} deletion request{'s' if deletions != 1 else ''} "
                         f"to review ({term.cyan('deletion list')})")
        if joins:
            parts.append(f"{joins} join request{'s' if joins != 1 else ''} "
                         f"to review ({term.cyan('ag list')})")
        if parts:
            print(f"Pending: {'; '.join(parts)}.")

    def _hidden_commands(self):
        """Commands this caller cannot use, kept out of completion.

        Entries are top-level names, or "resource subcommand" pairs.
        """
        hidden = set()
        if not self._can_manage_service_accounts():
            hidden.update({'sa', 'service-account'})
        if not self.client.can_elevate:
            hidden.update({'user create', 'user set-role', 'user list-keys', 'user revoke-keys',
                           'user approve', 'user reject', 'deletion delete'})
        return hidden

    def _can_manage_service_accounts(self):
        """Whether service-account administration is reachable for this caller."""
        return bool(self.client.can_elevate
                    or self.client.capabilities.can_manage_service_accounts)

    def rebind_client(self, keep_privilege_mode=True):
        """Reload config and adopt the fresh shared client.

        config.reload() discards the shared client, so the shell must pick up
        the new one or its toolbar and completion would drift from the client
        commands use. A session elevation toggle survives unless the caller
        is applying a config change that should replace it.
        """
        from crucible.config import config as _cfg, get_client

        previous = self.client.privilege_mode if self.client else None
        _cfg.reload()
        self.client = get_client()
        if keep_privilege_mode and previous is not None:
            self.client.privilege_mode = previous
        if self.completer is not None:
            self.completer._client       = self.client
            self.completer._unlink_cache = {}
            self.completer._user_search_cache.clear()
            self.completer._entity_search_cache.clear()
            self.completer._facet_cache.clear()
            self.completer._project_search_cache.clear()
            self.completer._instrument_search_cache.clear()

    def _apply_elevated(self, on):
        """Set elevation on the shared client and the toolbar state.

        Turning it off pins "normal" rather than clearing the mode, because
        sending no header at all leaves a platform administrator elevated.
        """
        self.state['elevated'] = on
        if self.client is not None:
            self.client.privilege_mode = 'elevated' if on else 'normal'
            self.client.refresh_profile()
            if getattr(self, 'completer', None) is not None:
                self.completer.hidden = self._hidden_commands()

    def _arm_idle_timer(self):
        """Switch elevation off if the prompt sits idle for elevation_timeout minutes."""
        from crucible.config import config as _cfg
        minutes = _cfg.elevation_timeout
        if not minutes or not self.state.get('elevated'):
            return
        timer = threading.Timer(minutes * 60, self._idle_expired, args=(minutes,))
        timer.daemon = True
        with self._idle_lock:
            self._idle_timer = timer
        timer.start()

    def _idle_expired(self, minutes):
        with self._idle_lock:
            if self._idle_timer is None:
                return
            self._idle_timer = None
            self._idle_dropped = minutes
            self.state['elevated'] = False
            if self.client is not None:
                self.client.privilege_mode = 'normal'
        if self._session is not None:
            self._session.app.invalidate()

    def _disarm_idle_timer(self):
        """Stop the idle timer once a line is entered, and report a drop."""
        with self._idle_lock:
            timer, self._idle_timer = self._idle_timer, None
            minutes, self._idle_dropped = self._idle_dropped, 0
        if timer is not None:
            timer.cancel()
        if minutes:
            self._apply_elevated(False)
            print(term.yellow(f"Elevated privilege switched off after {minutes} idle "
                              "minutes; 'elevate on' turns it back on."))

    def refresh(self):
        """Re-fetch projects, user info, deletions, join requests, and service accounts. Updates state + completer."""
        from ..helpers import (
            fetch_projects, fetch_deletions, fetch_join_requests, fetch_service_accounts,
            fetch_user_label, fetch_project_context, fetch_api_label, fetch_api_attention,
            auth_label,
        )
        self.client.refresh_profile()
        with ThreadPoolExecutor(max_workers=4) as pool:
            proj_f = pool.submit(fetch_projects,      self.client)
            del_f  = pool.submit(fetch_deletions,     self.client)
            jr_f   = pool.submit(fetch_join_requests, self.client)
            sa_f   = (pool.submit(fetch_service_accounts, self.client)
                      if self._can_manage_service_accounts() else None)
            new_projects         = proj_f.result()
            new_deletions        = del_f.result()
            new_join_requests    = jr_f.result()
            new_service_accounts = sa_f.result() if sa_f else None
        self.state['elevated']         = self.client.is_elevated
        self.state['projects']         = new_projects
        self.state['user_label']       = fetch_user_label(self.client)
        project_id, project_source = fetch_project_context()
        self.state['project']          = project_id
        self.state['project_source']   = project_source
        self.state['api_label']        = fetch_api_label()
        self.state['api_attention']    = fetch_api_attention()
        self.state['auth_label']       = auth_label(self.client)
        self._background = {'health': _in_background(self.client.health)}
        self._collect_background_checks()
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
            self.completer._facet_cache.clear()
            self.completer._project_search_cache.clear()
            self.completer._instrument_search_cache.clear()
            self.completer.hidden = self._hidden_commands()
        print(f"Refreshed: {len(new_projects)} projects, user info reloaded.")
        self._print_pending()

    def _toolbar(self):
        from prompt_toolkit.application import get_app
        try:
            term_width = get_app().output.get_size().columns
        except Exception:
            term_width = 80

        separator = ' │ '
        project = self.state.get('project') or '(no project set)'
        if self.state.get('project_source') == 'environment':
            project += ' [env]'
        user = self.state.get('user_label') or '?'
        auth = self.state.get('auth_label')
        api = self.state.get('api_label') or '?'
        note = self.state.get('api_version_note')
        if note:
            api += f' · API {note}'
        badges = [(tag, f' {text} ') for tag, text, on in (
            ('tb-elevated', 'ELEVATED', self.state.get('elevated')),
            ('tb-debug', 'DEBUG', self.state.get('debug'))) if on]

        def fit(project_label, user_label):
            parts = [f' 🔬 {project_label} ', f' 🔗 {api} ']
            if user_label:
                parts.insert(1, f' 🧸 {user_label} ')
            used = sum(vlen(p) for p in parts) + vlen(separator) * (len(parts) - 1)
            used += sum(len(text) + vlen(separator) for _, text in badges)
            return parts, used

        def short(text, width):
            return text if len(text) <= width else text[:width - 1] + '…'

        user_full = f'{user} · {auth}' if auth else user
        for project_label, user_label in (
                (short(project, 30), user_full),
                (short(project, 30), user),
                (short(project, 20), None),
                (short(project, 12), None)):
            parts, used = fit(project_label, user_label)
            if used <= term_width:
                break
        pad = ' ' * max(0, term_width - used)

        api_tag = ('tb-api-attention'
                   if self.state.get('api_attention') or note else 'tb-api')
        tags = ['tb-project'] + (['tb-user'] if len(parts) == 3 else []) + [api_tag]
        sep = f'<tb-separator>{separator}</tb-separator>'
        body = sep.join(f'<{tag}>{escape(text)}</{tag}>' for tag, text in zip(tags, parts))
        tail = ''.join(f'{sep}<{tag}>{text}</{tag}>' for tag, text in badges)
        return shell_html(f'{body}{pad}{tail}')

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
        from ..config import set_config_value
        set_config_value('current_project', project_id)
        self.state['project'] = project_id
        self.state['project_source'] = 'config file'
        label = f"{project_id} - {title}" if title else project_id
        print(f"Using project: {label} (remembered)")
        return True

    def _dispatch(self, line, page=None):
        """Parse and execute one command line. Returns False to signal exit.

        page continues a listing from where the previous one stopped, as
        recorded by helpers.next_page().
        """
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
            # An inline --elevate applies to this command only; the session
            # toggle is what persists.
            inline_elevated = getattr(args, 'elevated', False)
            session_mode = self.client.privilege_mode if self.client else None
            session_elevated = self.state.get('elevated', False)
            if inline_elevated and self.client is not None:
                self.client.privilege_mode = 'elevated'
                self.client.refresh_profile()
            if hasattr(args, 'func'):
                from ..helpers import begin_page, next_page
                args._shell_state = self.state
                if page:
                    args.page = page
                begin_page(page['start'], page.get('total')) if page else begin_page()
                try:
                    from ..pager import paged
                    from ..stepup import install_for
                    install_for(args)
                    with paged(args):
                        args.func(args)
                    if getattr(args, 'pageable', False):
                        upcoming = next_page()
                        self.state['last_listing'] = (line, upcoming) if upcoming else None
                finally:
                    if inline_elevated:
                        self.state['elevated'] = session_elevated
                        if self.client is not None:
                            self.client.privilege_mode = session_mode
                            self.client.refresh_profile()
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
        if (len(words) >= 2
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
        if (self._can_manage_service_accounts() and len(words) >= 2
                and words[0] in ('sa', 'service-account')
                and words[1] in ('create', 'update', 'rotate-key')):
            from ..helpers import fetch_service_accounts
            new_service_accounts = fetch_service_accounts(self.client)
            self.state['service_accounts'] = new_service_accounts or []
            if self.completer is not None:
                self.completer._service_accounts = new_service_accounts or []

        if len(words) >= 2 and words[0] == 'project' and words[1] in ('create', 'update', 'edit'):
            from ..helpers import fetch_projects
            new_projects = fetch_projects(self.client)
            self.state['projects'] = new_projects
            if self.completer is not None:
                self.completer._projects = new_projects
                self.completer._project_search_cache.clear()

        if len(words) >= 2 and words[0] == 'config' and words[1] in ('set', 'unset', 'edit'):
            try:
                self.rebind_client(keep_privilege_mode=False)
            except Exception:
                pass
            self.refresh()

        if words and words[0] in ('login', 'logout'):
            try:
                self.rebind_client()
            except ValueError as exc:
                print(exc)
                return True
            self.refresh()

        return True

    def _run_prompt_toolkit(self):
        from prompt_toolkit                import PromptSession
        from prompt_toolkit.auto_suggest   import AutoSuggestFromHistory
        from prompt_toolkit.styles         import Style
        from prompt_toolkit.key_binding    import KeyBindings
        from prompt_toolkit.completion     import ThreadedCompleter
        from platformdirs import user_data_dir
        from .history import PrivateFileHistory

        history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        print('\033[2J\033[H', end='', flush=True)

        history = PrivateFileHistory(history_path)
        info = self._verify_connection()
        if info is None:
            info = self._signed_out_prompt(history)
            if info is None:
                return
        self._init_state(info)

        print_welcome(self._welcome_rows(info), shutil.get_terminal_size((80, 24)).columns)

        self.completer = CrucibleCompleter(
            self.parser,
            client=self.client,
            projects=self.state['projects'],
            deletions=self.state['deletions'],
            join_requests=self.state['join_requests'],
            service_accounts=self.state['service_accounts'],
            state=self.state,
        )
        self.completer.hidden = self._hidden_commands()

        kb = KeyBindings()
        from .keybindings import register as _register_keybindings
        _register_keybindings(kb, self)

        self._session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=ThreadedCompleter(self.completer),
            complete_while_typing=True,
            key_bindings=kb,
            bottom_toolbar=self._toolbar,
            style=Style.from_dict(shell_style_rules()),
            color_depth=shell_color_depth(),
        )

        while True:
            self._arm_idle_timer()
            try:
                line = self._session.prompt(PROMPT)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
            finally:
                self._disarm_idle_timer()
            started = time.monotonic()
            if not self._dispatch(line):
                break
            _report_duration(line, time.monotonic() - started)
            print()


    def _signed_out_prompt(self, history):
        """Offer sign-in and configuration until a credential works.

        Returns the whoami info once connected, or None when the user leaves.
        """
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.styles import Style

        hint = (f"Type {term.cyan('login')} to sign in with a browser, or "
                f"{term.cyan('config init')} to set an API key.")
        print(term.yellow(self._signed_out_reason))
        print(hint)
        print()
        session = PromptSession(
            history=history,
            completer=WordCompleter(list(SIGNED_OUT_COMMANDS)),
            complete_while_typing=True,
            bottom_toolbar=self._signed_out_toolbar,
            style=Style.from_dict(shell_style_rules()),
            color_depth=shell_color_depth(),
        )
        while True:
            try:
                line = session.prompt(PROMPT)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                return None
            words = line.split()
            if not words:
                continue
            if words[0] in ('exit', 'quit'):
                return None
            if words[0] not in SIGNED_OUT_COMMANDS:
                print(f"Not signed in. Until you are, the shell runs only "
                      f"{', '.join(SIGNED_OUT_COMMANDS)}. {hint}")
                continue
            if words[0] == 'help':
                print(f"Not signed in. {hint} {term.cyan('status')} checks the API; "
                      f"{term.cyan('exit')} leaves.")
                continue
            self._run_signed_out_command(line)
            if words[0] not in _SIGNED_OUT_RETRY:
                continue
            info = self._connect_if_credential()
            if info is not None:
                print()
                return info
            print()

    def _run_signed_out_command(self, line):
        from .. import setup_logging
        try:
            args = self.parser.parse_args(shlex.split(line))
            setup_logging(debug=getattr(args, 'debug', False))
            if hasattr(args, 'func'):
                args.func(args)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:
            logger.error(f"Error: {e}")

    def _connect_if_credential(self):
        """Connect when a credential now resolves; stay quiet while none does."""
        from crucible.config import config as _cfg, get_client
        from crucible.errors import NotSignedInError
        _cfg.reload()
        try:
            get_client()
        except NotSignedInError:
            return None
        except ValueError:
            pass
        info = self._verify_connection(fatal=False)
        if info is None:
            print(term.yellow(self._signed_out_reason))
        return info

    def _signed_out_toolbar(self):
        from ..helpers import fetch_api_label
        sep = '<tb-separator> │ </tb-separator>'
        api = escape(fetch_api_label() or '?')
        return shell_html(f'<tb-user> not signed in </tb-user>{sep}<tb-api> 🔗 {api} </tb-api>')


def run(parser):
    """Start the interactive shell. Called from main() when no command given."""
    CrucibleShell(parser).run()
