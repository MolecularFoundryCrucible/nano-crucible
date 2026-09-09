#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal display utilities for the Crucible CLI.

Provides TTY-aware color helpers, formatted headers, relative timestamps,
human-readable sizes, and compact table rendering. Color and style functions
are no-ops when their output stream is not a TTY.
"""

import os
import re
import shutil
import sys
from datetime import datetime, timezone

from ..utils.identifiers import is_orcid

# Strips ANSI SGR sequences (\033[...m) and OSC 8 hyperlinks (\033]8;...\007)
_ANSI_RE = re.compile(r'\033(?:\[[0-9;]*m|\][^\007\033]*(?:\007|\033\\))')
# Matches a full OSC 8 hyperlink: \033]8;;URL\007TEXT\033]8;;\007
_OSC8_RE = re.compile(r'\033\]8;;([^\007]*)\007(.*?)\033\]8;;\007', re.DOTALL)

def _dlen(s: str) -> int:
    """Visible display length of *s*, ignoring ANSI/OSC escape sequences."""
    return len(_ANSI_RE.sub('', s))


# ── TTY detection ──────────────────────────────────────────────────────────────

_COLOR_ENABLED = 'NO_COLOR' not in os.environ


def configure_color(enabled: bool = True) -> None:
    global _COLOR_ENABLED
    _COLOR_ENABLED = bool(enabled) and 'NO_COLOR' not in os.environ


def color_enabled() -> bool:
    return _COLOR_ENABLED


def _tty(stream=None) -> bool:
    stream = stream or sys.stdout
    return _COLOR_ENABLED and hasattr(stream, 'isatty') and stream.isatty()


def _interactive(stream=None) -> bool:
    stream = stream or sys.stdout
    return hasattr(stream, 'isatty') and stream.isatty()


def _styled(s: str, code: str, stream=None) -> str:
    use_color = _tty() if stream is None else _tty(stream)
    return f"\033[{code}m{s}\033[0m" if use_color else s


# ── ANSI helpers ───────────────────────────────────────────────────────────────

def bold(s: str, stream=None) -> str:
    return _styled(s, '1', stream)

def cyan(s: str, stream=None) -> str:
    return _styled(s, '36', stream)

def blue(s: str, stream=None) -> str:
    return _styled(s, '34', stream)

def magenta(s: str, stream=None) -> str:
    return _styled(s, '35', stream)

def gold(s: str, stream=None) -> str:
    return _styled(s, '38;5;220', stream)

def green(s: str, stream=None) -> str:
    return _styled(s, '32', stream)

def gray(s: str, stream=None) -> str:
    return _styled(s, '90', stream)

def yellow(s: str, stream=None) -> str:
    return _styled(s, '33', stream)

def red(s: str, stream=None) -> str:
    return _styled(s, '31', stream)

def underline(s: str, stream=None) -> str:
    return _styled(s, '4', stream)

def hyperlink(text: str, url: str | None) -> str:
    """Wrap *text* in an OSC 8 hyperlink for interactive terminal output."""
    if url and _interactive():
        return f"\033]8;;{url}\007{text}\033]8;;\007"
    return text


def navigation_link(text: str, url: str | None, *, emphasized: bool = False) -> str | None:
    """Render a navigable value with consistent color and link affordance."""
    if not text:
        return None
    rendered = cyan(str(text)) if url else str(text)
    if emphasized:
        rendered = bold(rendered)
    if url and _interactive():
        rendered = underline(rendered)
    return hyperlink(rendered, url)


def identifier_link(identifier: str, url: str | None = None) -> str | None:
    """Render an identifier in cyan and link it when a destination is available."""
    if not identifier:
        return None
    return navigation_link(identifier, url) if url else cyan(identifier)


def orcid_link(orcid: str) -> str | None:
    """Render an ORCID in cyan as a clickable link to https://orcid.org/."""
    if not orcid:
        return None
    return identifier_link(orcid, f"https://orcid.org/{orcid}")


def user_id_link(user_id: str) -> str | None:
    """Render a canonical user ID linked to its Crucible Explorer profile."""
    if not user_id:
        return None
    from .helpers import user_explorer_url
    return identifier_link(user_id, user_explorer_url(user_id))


def user_link(label: str, user_id: str) -> str | None:
    """Link a user label to its Crucible Explorer profile."""
    if not label:
        return None
    from .helpers import user_explorer_url
    return navigation_link(label, user_explorer_url(user_id))


def user_id_label(user_id: str) -> str:
    """Return the display label for a canonical user identifier."""
    return "ORCID" if is_orcid(user_id) else "User ID"


def fmt_name(person: dict, default: str | None = None, fallback_username: bool = True) -> str | None:
    """Format given names as initials followed by the complete family name.

    Falls back to username (unless fallback_username=False), then to default,
    if both name fields are empty.
    """
    first_name = (person.get('first_name') or '').strip()
    last_name = (person.get('last_name') or '').strip()
    initials = []
    for given_name in first_name.split():
        parts = [part for part in given_name.split('-') if part]
        if parts:
            initials.append('-'.join(f'{part[0].upper()}.' for part in parts))
    name = ' '.join([*initials, last_name]).strip()
    if name:
        return name
    if fallback_username and person.get('username'):
        return person['username']
    return default


def fmt_owner(resource: dict) -> str | None:
    """Format the owner of a resource.

    If include_owner was used and the owner object is present, returns
    'F. Lastname (@username)' linked to the Crucible Explorer profile. Falls
    back to the canonical owner identifier.
    """
    owner = resource.get('owner')
    owner_id = resource.get('owner_orcid')
    if owner:
        name = fmt_name(owner, default=owner_id or '-')
        uname = owner.get('username')
        linked_name = user_link(name, owner_id)
        return f"{linked_name}  {dim(f'(@{uname})')}" if uname else linked_name
    return user_id_link(owner_id)


def project_link(pid: str, url: str | None = None) -> str | None:
    """Render a project ID in cyan, optionally as a clickable OSC 8 hyperlink."""
    if not pid:
        return None
    return identifier_link(pid, url)


def mfid_link(uid: str, url: str | None = None) -> str | None:
    """Render an MFID in cyan, optionally as a clickable OSC 8 hyperlink.

    Returns ``None`` for falsy *uid* so callers can render it as ``—``.
    """
    if not uid:
        return None
    return identifier_link(uid, url)

def dim(s: str, stream=None) -> str:
    return _styled(s, '2', stream)


def success(message: str, args=None) -> None:
    if getattr(args, 'json', False):
        return
    print(f"{green('Success:')} {message}")


def status_marker(status: str, stream=None) -> str:
    styles = {
        'success': ('✓', 'OK', green),
        'warning': ('!', 'WARNING', yellow),
        'error': ('×', 'ERROR', red),
        'info': ('-', 'INFO', dim),
    }
    if status not in styles:
        raise ValueError(f"Unknown status marker: {status}")
    symbol, label, style = styles[status]
    return style(symbol if _interactive(stream) else label, stream=stream)


def _standing_label(standing: str, *, owner_label: str, stream=None) -> str:
    if not standing:
        return '-'
    normalized = standing.lower()
    styles = {
        'owner': gold,
        'admin': magenta,
        'editor': blue,
        'contributor': lambda value, stream=None: value,
        'viewer': gray,
    }
    display = owner_label if normalized == 'owner' else standing
    return styles.get(normalized, dim)(display, stream=stream)


def role_label(role: str, stream=None) -> str:
    """Color a project role while preserving plain redirected output."""
    return _standing_label(role, owner_label='lead', stream=stream)


def permission_label(permission: str, stream=None) -> str:
    """Color an ACL permission while preserving its canonical name."""
    return _standing_label(permission, owner_label='owner', stream=stream)


# ── Structural helpers ─────────────────────────────────────────────────────────

def header(title: str, width: int = 44) -> None:
    """Print a bold styled section header that fills to *width* characters."""
    prefix = f"── {title} "
    w = max(width, len(prefix) + 2)
    print(bold(prefix + "─" * (w - len(prefix))))


def subheader(title: str) -> None:
    """Print a bold sub-section label with a leading blank line."""
    print(f"\n  {dim('─')}  {bold(title)}")


def field_printer(width: int = 14):
    """Return a ``_p(label, value)`` closure that prints aligned label:value rows."""
    def _p(label: str, value) -> None:
        print(f"  {label:<{width}}{value if value not in (None, '') else '-'}")
    return _p


# ── Formatters ─────────────────────────────────────────────────────────────────

def _rel(delta) -> str:
    """Human-readable relative label for a timedelta."""
    days = delta.days
    if days < 0:
        return 'in the future'
    if days == 0:
        h = delta.seconds // 3600
        m = (delta.seconds % 3600) // 60
        return f"{h}h ago" if h else (f"{m}m ago" if m > 1 else "just now")
    if days == 1:
        return 'yesterday'
    if days < 30:
        return f"{days}d ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def fmt_ts(ts) -> str | None:
    """
    Format a timestamp for display.

    Handles:
      - ISO 8601 strings  → ``YYYY-MM-DD HH:MM  ±HH:MM  (relative)``
      - ``YYYYMMDD_am/pm``→ ``YYYY-MM-DD AM/PM  (relative)``
      - ``YYYYMMDD``      → ``YYYY-MM-DD  (relative)``
      - Anything else     → returned as-is

    Returns ``None`` for falsy input so callers can render it as ``—``.
    """
    if not ts:
        return None

    s = str(ts).strip()
    dt = None
    abs_str = None

    # ── Strategy 1: ISO 8601 ─────────────────────────────────────────────────
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone()  # convert to local timezone
        abs_str = dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        pass

    # ── Strategy 2: YYYYMMDD[_am|_pm] ───────────────────────────────────────
    if dt is None:
        m = re.match(r'^(\d{4})(\d{2})(\d{2})(?:_(am|pm))?$', s.lower())
        if m:
            y, mo, d, ampm = m.groups()
            try:
                hour = 12 if ampm == 'pm' else 0
                dt = datetime(int(y), int(mo), int(d), hour, 0, 0,
                              tzinfo=timezone.utc)
                abs_str = f"{y}-{mo}-{d}"
                if ampm:
                    abs_str += f" {ampm.upper()}"
            except ValueError:
                pass

    if dt is None:
        return s  # unrecognised format — return raw

    now = datetime.now(tz=dt.tzinfo)
    return f"{abs_str}  {dim(f'({_rel(now - dt)})')}"


def fmt_date(ts) -> str:
    """Format a timestamp as a bare YYYY-MM-DD, for compact table columns.

    Returns '-' for falsy or unparseable input.
    """
    if not ts:
        return '-'
    try:
        dt = datetime.fromisoformat(str(ts).strip())
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return str(ts)


_STATUS_COLORS = {
    'active':   green,
    'maintenance': yellow,
    'decommissioned': dim,
    'pending':  yellow,
    'approved': green,
    'complete': green,
    'ingested': green,
    'rejected': red,
    'failed':   red,
}


def status_label(status: str) -> str:
    """Colorize a status string using the shared request/ingestion status palette.

    Covers: pending (yellow), approved/complete/ingested (green), rejected/failed (red).
    Unrecognized statuses are returned unstyled. Returns '-' for falsy input.
    """
    if not status:
        return '-'
    return _STATUS_COLORS.get(status, lambda s: s)(status)


def fmt_bool(value) -> str:
    """Format a nullable boolean for human-readable output."""
    if value is None:
        return '-'
    return 'yes' if value else 'no'


def fmt_size(size) -> str | None:
    """Return a human-readable byte count, e.g. ``1.4 GB``."""
    if size is None:
        return None
    try:
        n = int(size)
    except (ValueError, TypeError):
        return str(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f"{n} {unit}" if unit == 'B' else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ── Diff display ───────────────────────────────────────────────────────────────

def diff(original: dict, updated: dict) -> None:
    """
    Print a before/after diff for changed fields.

      field_name    old value  →  new value

    Only fields that differ between *original* and *updated* are shown.
    None / empty values are rendered as ``—``.
    """
    changes = {k: (original.get(k), updated[k]) for k in updated if updated[k] != original.get(k)}
    if not changes:
        return

    MAX_VAL = 60

    def _v(val):
        s = str(val) if val not in (None, '') else '-'
        return s if len(s) <= MAX_VAL else s[:MAX_VAL - 1] + '…'

    key_w = max(len(k) for k in changes)
    old_w = max(len(_v(v[0])) for v in changes.values())

    for key, (old, new) in changes.items():
        old_s = _v(old)
        new_s = _v(new)
        print(f"  {key:<{key_w}}  {dim(old_s.ljust(old_w))}  ->  {new_s}")


# ── Editor launcher ────────────────────────────────────────────────────────────

# GUI editors that fork into the background by default.
# Maps the binary name to the flag(s) that make them block until closed.
_GUI_EDITOR_WAIT_FLAGS: dict[str, list[str]] = {
    'gvim':          ['-f'],
    'mvim':          ['-f'],
    'nvim-qt':       ['--nofork'],
    'gedit':         ['--wait'],
    'kate':          ['--block'],
    'subl':          ['--wait'],
    'sublime_text':  ['--wait'],
    'code':          ['--wait'],
    'code-insiders': ['--wait'],
}


def open_editor_json(data: dict) -> dict | None:
    """
    Serialize *data* to a temp JSON file, open it in ``$EDITOR`` (or
    ``$VISUAL``), and return the parsed result after the editor closes.

    Returns ``None`` if the content was not changed.
    Raises ``ValueError`` on invalid JSON and ``RuntimeError`` if the editor
    exits with a non-zero status.

    Known GUI editors (gvim, VS Code, Sublime Text, kate, gedit, …) are
    automatically invoked with their foreground/wait flags so the function
    blocks until the file is saved and the window is closed.  Users who have
    already set ``EDITOR="gvim -f"`` or ``EDITOR="code --wait"`` are not
    affected — duplicate flags are not added.
    """
    import json
    import os
    import subprocess
    import tempfile

    # Priority: crucible config > $VISUAL > $EDITOR > nano
    try:
        from crucible.config import config as _cfg
        _editor_cfg = _cfg.editor
    except Exception:
        _editor_cfg = None

    raw = _editor_cfg or os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'nano'
    parts = raw.split()
    editor_bin = os.path.basename(parts[0])
    extra = [f for f in _GUI_EDITOR_WAIT_FLAGS.get(editor_bin, []) if f not in parts]
    cmd = parts + extra

    original_text = json.dumps(data, indent=2, default=str)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', prefix='crucible-', delete=False
    ) as f:
        f.write(original_text)
        tmp_path = f.name

    try:
        subprocess.run(cmd + [tmp_path], check=True)
        with open(tmp_path) as f:
            edited_text = f.read()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Editor exited with an error: {e}") from e
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if edited_text.strip() == original_text.strip():
        return None

    try:
        # strip trailing commas before closing braces/brackets (common editor mistake)
        cleaned = re.sub(r',\s*([}\]])', r'\1', edited_text)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e


# ── Table renderer ─────────────────────────────────────────────────────────────

def _truncate_styled_text(text: str, width: int) -> str:
    remaining = max(0, width - 1)
    parts = []
    for token in re.split(r'(\033\[[0-9;]*m)', text):
        if not token:
            continue
        if token.startswith('\033['):
            if remaining:
                parts.append(token)
            continue
        if remaining:
            visible = token[:remaining]
            parts.append(visible)
            remaining -= len(visible)
            if not remaining:
                break
    truncated = ''.join(parts) + '…'
    if '\033[' in text:
        truncated += '\033[0m'
    return truncated


def _truncate_cell(s: str, width: int) -> str:
    """Truncate *s* while preserving terminal styles and hyperlinks."""
    m = _OSC8_RE.search(s)
    if m:
        url = m.group(1)
        truncated = _truncate_styled_text(m.group(2), width)
        if url and _interactive():
            return f"\033]8;;{url}\007{truncated}\033]8;;\007"
        return truncated
    return _truncate_styled_text(s, width)


def _table_output_width() -> int:
    if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
        return shutil.get_terminal_size(fallback=(100, 24)).columns
    return 100


def _shrink_widths(widths: list, floors: list, target: int) -> list:
    result = list(widths)
    while sum(result) > target:
        candidates = [i for i, width in enumerate(result) if width > floors[i]]
        if not candidates:
            break
        index = max(
            candidates,
            key=lambda i: (result[i] - floors[i], result[i], -i),
        )
        result[index] -= 1
    return result


def _fit_cell(value: str, width: int) -> str:
    if _dlen(value) > width:
        value = _truncate_cell(value, width)
    return value + ' ' * (width - _dlen(value))


def table(rows: list, headers: list, max_widths: list | None = None,
          min_widths: list | None = None) -> None:
    """
    Print a compact aligned table to stdout.

    *rows*       — list of tuples/lists, one per row.
    *headers*    — column header strings (printed dim + uppercased).
    *max_widths* — optional per-column width caps (values are truncated with ``…``).
    *min_widths* - optional preferred minimums used while fitting the terminal.
    """
    if not rows:
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _dlen(str(cell) if cell is not None else '-'))
    if max_widths:
        for i, maximum in enumerate(max_widths[:len(widths)]):
            widths[i] = min(widths[i], maximum)

    header_floors = [min(width, max(1, len(str(header))))
                     for width, header in zip(widths, headers)]
    preferred_floors = list(header_floors)
    if min_widths:
        for i, minimum in enumerate(min_widths[:len(widths)]):
            preferred_floors[i] = min(
                widths[i],
                max(header_floors[i], minimum),
            )

    indent = '  '
    separator = '  '
    output_width = max(1, _table_output_width())
    minimum_cells = len(headers)
    if output_width < len(indent) + len(separator) * (len(headers) - 1) + minimum_cells:
        indent = ''
    if output_width < len(indent) + len(separator) * (len(headers) - 1) + minimum_cells:
        separator = ' '
    if output_width < len(indent) + len(separator) * (len(headers) - 1) + minimum_cells:
        separator = ''
    overhead = len(indent) + len(separator) * (len(headers) - 1)
    content_width = max(len(headers), output_width - overhead)
    widths = _shrink_widths(widths, preferred_floors, content_width)
    widths = _shrink_widths(widths, header_floors, content_width)
    widths = _shrink_widths(widths, [1] * len(widths), content_width)

    header_line = indent + separator.join(
        _fit_cell(str(header).upper(), widths[i])
        for i, header in enumerate(headers)
    ).rstrip()
    print(dim(header_line))

    for row in rows:
        parts = [
            _fit_cell(str(cell) if cell is not None else '-', widths[i])
            for i, cell in enumerate(row)
        ]
        print(indent + separator.join(parts).rstrip())


# ── Colored argparse help formatter ────────────────────────────────────────────

import argparse as _argparse

# Section headings generated by argparse: 'options:', 'commands:', 'positional arguments:', …
_HELP_HEADING_RE = re.compile(r'^[a-z][a-z ]*:$')
# Flag names: -f, --flag, --my-flag
_HELP_FLAG_RE    = re.compile(r'-{1,2}[a-zA-Z][\w-]*')
# Metavar placeholders: FILE, ID, MFID (2+ uppercase chars)
_HELP_META_RE    = re.compile(r'\b[A-Z][A-Z_0-9]+\b')


class ColorHelpFormatter(_argparse.RawDescriptionHelpFormatter):
    """RawDescriptionHelpFormatter with ANSI highlights (TTY only).

    Colors are applied after argparse finishes formatting, so column alignment
    is unaffected by escape sequences.
    """

    def format_help(self):
        import os as _os
        text = super().format_help()
        # Use os.isatty(1) rather than sys.stdout.isatty() — prompt_toolkit
        # wraps sys.stdout in a proxy that reports isatty()=False even on a
        # real terminal, so we check the file descriptor directly.
        try:
            is_tty = _os.isatty(1)
        except Exception:
            is_tty = _tty()
        if not _COLOR_ENABLED or not is_tty:
            return text

        out = []
        for line in text.split('\n'):
            stripped = line.rstrip()

            # Section headings: 'options:', 'commands:', 'positional arguments:', …
            if _HELP_HEADING_RE.match(stripped):
                out.append(bold(stripped))
                continue

            # Bold the 'usage:' prefix
            if stripped.startswith('usage:'):
                line = bold('usage') + ':' + stripped[6:]

            # Bold+cyan flags, dim metavars — on usage line and indented option lines
            if stripped.startswith('usage:') or (line.startswith('  ') and '-' in line):
                line = _HELP_FLAG_RE.sub(lambda m: bold(cyan(m.group())), line)
                line = _HELP_META_RE.sub(lambda m: dim(m.group()), line)

            out.append(line)

        return '\n'.join(out)
