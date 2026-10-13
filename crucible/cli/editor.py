"""Choose and launch the user's text editor for interactive edit commands."""

import os
import shlex
import shutil
import subprocess
import sys

# Editors that return immediately unless told to wait for the file to close,
# keyed by lowercase program name without extension.
WAIT_FLAGS = {
    'gvim':          ['-f'],
    'mvim':          ['-f'],
    'nvim-qt':       ['--nofork'],
    'gedit':         ['--wait'],
    'kate':          ['--block'],
    'subl':          ['--wait'],
    'sublime_text':  ['--wait'],
    'code':          ['--wait'],
    'code-insiders': ['--wait'],
    'codium':        ['--wait'],
    'notepad++':     ['-multiInst', '-nosession'],
}

# Tried in order when nothing is configured. Notepad and vi always exist on
# their platforms, so each list ends with a guaranteed fallback.
PLATFORM_DEFAULTS = {
    'win32':  ['code', 'notepad++', 'notepad'],
    'darwin': ['code', 'nano', 'vim', 'vi'],
    'linux':  ['code', 'nano', 'vim', 'vi', 'gedit', 'kate'],
}


def configured_editor():
    """The editor named by crucible config, $VISUAL, or $EDITOR, if any."""
    try:
        from crucible.config import config
        configured = config.editor
    except Exception:
        configured = None
    return configured or os.environ.get('VISUAL') or os.environ.get('EDITOR')


def default_editor(platform=None):
    """The first available platform default editor."""
    platform = platform or sys.platform
    candidates = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS['linux'])
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return candidates[-1]


def split_command(editor, platform=None):
    """Split an editor setting into argv, keeping Windows paths intact.

    POSIX shell splitting would treat the backslashes in
    ``C:\\Program Files\\...`` as escapes, so Windows uses non-POSIX rules
    and strips surrounding quotes.
    """
    platform = platform or sys.platform
    if platform == 'win32':
        return [part.strip('"') for part in shlex.split(editor, posix=False)]
    return shlex.split(editor)


def program_name(path):
    """Lowercase program name without directory or Windows extension."""
    name = os.path.basename(path.replace('\\', '/')).lower()
    for extension in ('.exe', '.cmd', '.bat', '.com'):
        if name.endswith(extension):
            return name[:-len(extension)]
    return name


def editor_command(editor=None, platform=None):
    """Return the argv that opens a file in the editor and waits for it.

    The file path is appended by the caller. The executable is resolved to
    a full path so Windows can start batch-file shims such as ``code.cmd``,
    which CreateProcess does not find by bare name.
    """
    platform = platform or sys.platform
    editor = editor or configured_editor() or default_editor(platform)
    parts = split_command(editor, platform)
    if not parts:
        raise ValueError("The configured editor is empty.")
    resolved = shutil.which(parts[0])
    if resolved:
        parts[0] = resolved
    lowered = [part.lower() for part in parts[1:]]
    wait = [flag for flag in WAIT_FLAGS.get(program_name(parts[0]), [])
            if flag.lower() not in lowered]
    return parts + wait


def edit_file(path, editor=None):
    """Open path in the editor and block until it closes.

    Raises:
        FileNotFoundError: The editor program does not exist.
        subprocess.CalledProcessError: The editor exited with an error.
    """
    command = editor_command(editor)
    subprocess.run(command + [str(path)], check=True)
    return command
