"""Shell-only commands such as use, cd, debug, and elevated.

Each handler takes the shell and the full input line and returns True to keep
the shell running.
"""

import logging
import os
import shutil
import sys

from .. import term
from ._common import vlen

try:
    from .completer import CrucibleCompleter
except ImportError:
    CrucibleCompleter = None

logger = logging.getLogger(__name__)


def _help(shell, line):
    shell.parser.print_help()
    _W = 18
    print()
    term.header("Shell commands")
    for _cmd, _desc in [
        ('use PROJECT',   'select and remember current project'),
        ('unuse',         'clear the current project'),
        ('refresh',       're-fetch projects, user info, deletions'),
        ('reload',        'restart the shell process'),
        ('debug on|off',  'toggle debug logging'),
        ('elevated on|off', 'toggle platform-administrator elevation'),
        ('v',             'toggle verbose view for last fetched resource'),
        ('! CMD',         'run a shell command'),
        ('ls [PATH]',     'list directory'),
        ('cd [PATH]',     'change directory'),
        ('pwd',           'print working directory'),
        ('exit / quit',   'exit the shell'),
    ]:
        print(f"  {term.cyan(_cmd)}{' ' * (_W - len(_cmd))} {_desc}")
    if CrucibleCompleter:
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


def _use(shell, line):
    parts = line.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        print("Usage: use <project_id>")
        return True
    project_id = parts[1].strip()
    if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
        from ..helpers import show_warning
        show_warning(
            "CRUCIBLE_CURRENT_PROJECT controls the current project. "
            "Unset it before using the shell project selector."
        )
        return True
    try:
        import requests as _req
        project = shell.client.projects.get(project_id)
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
        shell._activate_project(project_id, title)
    except Exception as e:
        logger.error(f"Error switching project: {e}")
    return True


def _unuse(shell, line):
    if os.environ.get('CRUCIBLE_CURRENT_PROJECT') is not None:
        from ..helpers import show_warning
        show_warning(
            "CRUCIBLE_CURRENT_PROJECT controls the current project. "
            "Unset it before clearing the shell project selection."
        )
        return True
    from ..config import unset_config_value
    unset_config_value('current_project')
    shell.state['project'] = None
    shell.state['project_source'] = None
    print("Cleared current project.")
    return True


def _refresh(shell, line):
    try:
        from crucible.config import config as _cfg
        _cfg.reload()
    except Exception:
        pass
    shell.refresh()
    return True


def _reload(shell, line):
    print('\033[2J\033[H', end='', flush=True)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _bang(shell, line):
    import subprocess
    cmd = line[1:].strip()
    if cmd:
        subprocess.run(cmd, shell=True)
    return True


def _pwd(shell, line):
    print(os.getcwd())
    return True


def _ls(shell, line):
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
        pad = ' ' * (col_width - vlen(display))
        end = '\n' if (i + 1) % cols == 0 or i == len(entries) - 1 else ''
        print(label + pad, end=end)
    return True


def _cd(shell, line):
    parts = line.split(None, 1)
    arg   = parts[1].strip() if len(parts) > 1 else '~'
    if arg == '-':
        oldpwd = shell.state.get('oldpwd')
        if not oldpwd:
            print("cd: no previous directory")
            return True
        path = oldpwd
    else:
        path = os.path.expanduser(arg)
    try:
        prev = os.getcwd()
        os.chdir(path)
        shell.state['oldpwd'] = prev
        if arg == '-':
            print(os.getcwd())
    except FileNotFoundError:
        print(f"cd: no such directory: {path}")
    except NotADirectoryError:
        print(f"cd: not a directory: {path}")
    return True


def _toggle_verbose(shell, line):
    last = shell.state.get('last_resource')
    if not last:
        print("No recent get to toggle. Run 'get <id>' first.")
        return True
    last['verbose'] = not last['verbose']
    shell._render_resource(last)
    return True


def _debug(shell, line):
    parts   = line.split()
    current = shell.state.get('debug', False)
    if len(parts) == 1:
        print(f"Debug is {'on' if current else 'off'}.")
        return True
    action = parts[1].lower()
    if action not in ('on', 'off'):
        print("Usage: debug on | debug off")
        return True
    on = (action == 'on')
    shell.state['debug'] = on
    from .. import setup_logging
    setup_logging(debug=on)
    print(f"Debug {'enabled' if on else 'disabled'}.")
    return True


def _elevated(shell, line):
    parts   = line.split()
    current = shell.state.get('elevated', False)
    if len(parts) == 1:
        print(f"Elevated privilege is {'on' if current else 'off'}.")
        return True
    action = parts[1].lower()
    if action not in ('on', 'off'):
        print("Usage: elevated on | elevated off")
        return True
    on = (action == 'on')
    if on and shell.client is not None and not shell.client.can_elevate:
        print("Your account is not eligible for elevated privilege.")
        return True
    shell._apply_elevated(on)
    if on:
        print("Elevated privilege enabled. Requests now ask for "
              "platform-administrator access.")
    else:
        print("Elevated privilege disabled.")
    return True


BUILTINS = {
    'help': (_help, False),
    'use': (_use, True),
    'unuse': (_unuse, False),
    'refresh': (_refresh, False),
    'reload': (_reload, False),
    '!': (_bang, True),
    'pwd': (_pwd, False),
    'ls': (_ls, True),
    'cd': (_cd, True),
    'v': (_toggle_verbose, False),
    'debug': (_debug, True),
    'elevated': (_elevated, True),
}


def find_builtin(line):
    """Return the handler for a shell-only command line, or None."""
    if line.startswith('!'):
        return BUILTINS['!'][0]
    name, _, rest = line.partition(' ')
    entry = BUILTINS.get(name)
    if entry is None:
        return None
    handler, takes_args = entry
    if rest.strip() and not takes_args:
        return None
    return handler
