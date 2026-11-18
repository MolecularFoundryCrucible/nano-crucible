"""Reading a pasted sign-in code in the terminal, and Enter as the way out of a
browser sign-in whose redirect never reaches this machine."""

import sys

from ..auth.session import CodePrompt
from . import term


class TerminalCodePrompt(CodePrompt):

    def __init__(self, stream=sys.stdout):
        self._stream = stream

    def _interactive(self) -> bool:
        try:
            return sys.stdin.isatty()
        except (AttributeError, ValueError):
            return False

    def waiting(self) -> None:
        if self._interactive():
            print("  Waiting for the browser. If it cannot reach this terminal (an error after you "
                  "choose Allow), press Enter to paste a code instead.\n", file=self._stream)

    def requested(self) -> bool:
        if not self._interactive():
            return False
        if sys.platform == 'win32':
            import msvcrt
            while msvcrt.kbhit():
                if msvcrt.getwch() in '\r\n':
                    return True
            return False
        import select
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            sys.stdin.readline()
            return True
        return False

    def read_code(self) -> str:
        print(file=self._stream)
        try:
            return input(f"  {term.bold('Sign-in code')}: ")
        except EOFError:
            return ''
