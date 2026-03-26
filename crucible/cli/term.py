#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal display utilities for the Crucible CLI.

Provides TTY-aware color helpers, formatted headers, relative timestamps,
human-readable sizes, and compact table rendering.  All color/style functions
are no-ops when stdout is not a TTY (e.g. when piping or redirecting).
"""

import sys
from datetime import datetime, timezone


# ── TTY detection ──────────────────────────────────────────────────────────────

def _tty() -> bool:
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


# ── ANSI helpers ───────────────────────────────────────────────────────────────

def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _tty() else s

def cyan(s: str) -> str:
    return f"\033[36m{s}\033[0m" if _tty() else s

def orcid_link(orcid: str) -> str | None:
    """
    Render an ORCID in cyan, optionally as a clickable link to https://orcid.org/.

    Returns ``None`` for falsy input so callers can render it as ``—``.
    """
    if not orcid:
        return None
    url = f"https://orcid.org/{orcid}"
    colored = cyan(orcid)
    if _tty():
        return f"\033]8;;{url}\033\\{colored}\033]8;;\033\\"
    return colored


def mfid_link(uid: str, url: str | None = None) -> str | None:
    """
    Render an MFID in cyan, optionally as a clickable OSC 8 hyperlink.

    Returns ``None`` for falsy *uid* so callers can render it as ``—``.
    When *url* is provided and stdout is a TTY, the text becomes clickable
    in terminals that support OSC 8 (iTerm2, kitty, GNOME Terminal ≥ 3.26,
    Windows Terminal, etc.).
    """
    if not uid:
        return None
    colored = cyan(uid)
    if url and _tty():
        return f"\033]8;;{url}\033\\{colored}\033]8;;\033\\"
    return colored

def dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if _tty() else s


# ── Structural helpers ─────────────────────────────────────────────────────────

def header(title: str, width: int = 44) -> None:
    """Print a bold styled section header that fills to *width* characters."""
    prefix = f"── {title} "
    w = max(width, len(prefix) + 2)
    print(bold(prefix + "─" * (w - len(prefix))))


def subheader(title: str) -> None:
    """Print a dim sub-section label with a leading blank line."""
    print(f"\n  {dim(title)}")


# ── Formatters ─────────────────────────────────────────────────────────────────

def fmt_ts(ts) -> str | None:
    """
    Format an ISO timestamp as ``YYYY-MM-DD HH:MM  ±HH:MM  (relative)``.

    Returns ``None`` for falsy input so callers can render it as ``—``.
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=dt.tzinfo)
        delta = now - dt
        days = delta.days

        abs_str = dt.strftime('%Y-%m-%d %H:%M')
        tz_s = dt.strftime('%z')
        if tz_s:
            abs_str += f"  {tz_s[:3]}:{tz_s[3:]}"

        if days < 0:
            rel = 'in the future'
        elif days == 0:
            h = delta.seconds // 3600
            m = (delta.seconds % 3600) // 60
            rel = f"{h}h ago" if h else (f"{m}m ago" if m > 1 else "just now")
        elif days == 1:
            rel = 'yesterday'
        elif days < 30:
            rel = f"{days}d ago"
        elif days < 365:
            rel = f"{days // 30}mo ago"
        else:
            rel = f"{days // 365}y ago"

        return f"{abs_str}  {dim(f'({rel})')}"
    except (ValueError, TypeError):
        return str(ts)


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


# ── Table renderer ─────────────────────────────────────────────────────────────

def table(rows: list, headers: list, max_widths: list | None = None) -> None:
    """
    Print a compact aligned table to stdout.

    *rows*       — list of tuples/lists, one per row.
    *headers*    — column header strings (printed dim + uppercased).
    *max_widths* — optional per-column width caps (values are truncated with ``…``).
    """
    if not rows:
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell) if cell is not None else '—'))
    if max_widths:
        widths = [min(w, m) for w, m in zip(widths, max_widths)]

    header_line = "  " + "  ".join(h.upper().ljust(widths[i]) for i, h in enumerate(headers))
    print(dim(header_line))

    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            s = str(cell) if cell is not None else '—'
            if len(s) > widths[i]:
                s = s[:widths[i] - 1] + '…'
            parts.append(s.ljust(widths[i]))
        print("  " + "  ".join(parts).rstrip())
