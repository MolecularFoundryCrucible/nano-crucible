"""Open long list output in a pager, the way git does."""

import io
import os
import re
import shlex
import shutil
import subprocess
import sys
from contextlib import contextmanager

from . import term

_DEFAULT_PAGER = 'less -FRX'
_LESS_LINK_VERSION = 566


class _TerminalBuffer(io.StringIO):
    """Captured stdout that still reports a terminal, so colors and links render."""

    def isatty(self):
        return True


def should_page(args) -> bool:
    """Whether this command's output may go through a pager."""
    from ..config import config

    if not getattr(args, 'pageable', False) or getattr(args, 'no_pager', False):
        return False
    if getattr(args, 'json', False):
        return False
    if not (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()):
        return False
    return config.pager == 'auto'


def _terminal_lines() -> int:
    return shutil.get_terminal_size((80, 24)).lines


def _pager_argv():
    """The pager command to run, or None when it is not installed."""
    command = (os.environ.get('CRUCIBLE_PAGER') or os.environ.get('PAGER')
               or _DEFAULT_PAGER)
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv or shutil.which(argv[0]) is None:
        return None
    return argv


def _strips_links(argv) -> bool:
    """Whether OSC 8 links must be removed for this pager.

    less passes them through with -R from version 566 on; other pagers are
    trusted to handle what the terminal does.
    """
    if os.path.basename(argv[0]) != 'less':
        return False
    try:
        version = subprocess.run([argv[0], '--version'], capture_output=True,
                                 text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    match = re.search(r'less (\d+)', version or '')
    return not match or int(match.group(1)) < _LESS_LINK_VERSION


def show(text: str) -> None:
    """Print text, through the pager when it is taller than the terminal."""
    argv = _pager_argv()
    if argv is None or text.count('\n') < _terminal_lines() - 1:
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    if _strips_links(argv):
        text = term._OSC8_RE.sub(r'\2', text)
    try:
        subprocess.run(argv, input=text, text=True, encoding='utf-8', errors='replace')
    except (OSError, subprocess.SubprocessError):
        sys.stdout.write(text)
        sys.stdout.flush()
    except KeyboardInterrupt:
        pass


@contextmanager
def paged(args):
    """Capture the command's stdout and show it through show() afterwards."""
    if not should_page(args):
        yield
        return
    real_stdout = sys.stdout
    buffer = _TerminalBuffer()
    sys.stdout = buffer
    try:
        yield
    finally:
        sys.stdout = real_stdout
        show(buffer.getvalue())
