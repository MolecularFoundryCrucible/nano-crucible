"""Shell history that keeps secrets out of the history file."""

import os
import re

from prompt_toolkit.history import FileHistory

_SECRET_LINE = re.compile(
    r'(\bconfig\s+set\s+api_key\b|\b[A-Z0-9_]*API_KEY\s*=)', re.IGNORECASE)


def is_secret(line):
    """True when a command line carries a credential."""
    return bool(_SECRET_LINE.search(line))


class PrivateFileHistory(FileHistory):
    """Owner-only history file that never records lines carrying secrets."""

    def __init__(self, filename):
        super().__init__(filename)
        if not os.path.exists(filename):
            open(filename, 'a').close()
        try:
            os.chmod(filename, 0o600)
        except OSError:
            pass

    def append_string(self, string):
        if is_secret(string):
            return
        super().append_string(string)
