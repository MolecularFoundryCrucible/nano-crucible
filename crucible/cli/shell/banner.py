"""Startup welcome: the Crucible mark in half-block pixels beside a session summary."""

from .. import term
from ._common import (BANNER_PIXELS, brand_colors, shell_color_depth,
                      shell_style_rules, vlen)


def load_shell_banner():
    try:
        from importlib.resources import files
    except ImportError:
        from importlib.resources import read_text
        return read_text('crucible.cli', 'crucible_ascii.txt').rstrip('\n')
    return files('crucible.cli').joinpath('crucible_ascii.txt').read_text().rstrip('\n')

def shell_banner_rows(banner):
    lines = banner.splitlines()
    width = max(map(len, lines), default=0)
    return [line.ljust(width, '_') for line in lines]

def shell_banner_row_pairs(banner):
    rows = shell_banner_rows(banner)
    if len(rows) % 2:
        rows.append('_' * len(rows[0]))
    return zip(rows[::2], rows[1::2])

def shell_banner_panel(banner):
    visible_pixels = frozenset('%=')
    return '\n'.join(
        ''.join(
            '█' if upper in visible_pixels and lower in visible_pixels
            else '▀' if upper in visible_pixels
            else '▄' if lower in visible_pixels
            else ' '
            for upper, lower in zip(upper_row, lower_row)
        )
        for upper_row, lower_row in shell_banner_row_pairs(banner)
    )

WELCOME_MARGIN = 2
WELCOME_GAP = 4
WELCOME_MIN_TEXT = 40

_DIM = 'class:welcome-dim'
_TITLE = 'class:welcome-title'
_ELEVATED = 'class:welcome-elevated'


def shell_banner_row_fragments(banner, depth=None):
    """Return the colored mark as one list of (style, text) fragments per row."""
    colors = brand_colors(depth)
    rows = []
    for upper_row, lower_row in shell_banner_row_pairs(banner):
        row = []
        for upper, lower in zip(upper_row, lower_row):
            upper_color = colors[BANNER_PIXELS[upper]]
            lower_color = colors[BANNER_PIXELS[lower]]
            if upper_color == lower_color:
                style, text = f'bg:{lower_color}', ' '
            else:
                style, text = f'fg:{upper_color} bg:{lower_color}', '▀'
            if row and row[-1][0] == style:
                row[-1] = (style, row[-1][1] + text)
            else:
                row.append((style, text))
        rows.append(row)
    return rows


def welcome_rows(*, version, first_name, user_label, platform_role, api_url,
                 project, elevated, deletions, joins):
    """Build the session summary printed beside the mark at startup."""
    def field(label, *value):
        return [(_DIM, label.ljust(10))] + list(value)

    user = user_label + (f' · {platform_role}'
                         if platform_role and platform_role != 'none' else '')
    rows = [
        [(_TITLE, 'Crucible'), ('', ' shell '), (_DIM, version)],
        [('', f'Welcome, {first_name}.')],
        [],
        field('User', ('', user)),
        field('API', ('', api_url or '?')),
        field('Project', ('', project) if project else (_DIM, 'none')),
        field('Access', ((_ELEVATED, ' elevated ' if term.color_enabled() else 'elevated')
                         if elevated else ('', 'normal'))),
    ]
    pending = []
    if deletions:
        pending.append(f"{deletions} deletion review{'s' if deletions != 1 else ''}")
    if joins:
        pending.append(f"{joins} join request{'s' if joins != 1 else ''}")
    if pending:
        rows.append(field('Pending', ('', ' · '.join(pending))))
    rows += [[], [(_DIM, "Type 'help' for commands, 'exit' to quit.")]]
    return rows


def _truncate(row, width):
    """Clip a fragment row to width display columns, ending in an ellipsis."""
    if sum(vlen(text) for _style, text in row) <= width:
        return row
    clipped, used = [], 0
    for style, text in row:
        for char in text:
            if used + vlen(char) > width - 1:
                return clipped + [('', '…')]
            if clipped and clipped[-1][0] == style:
                clipped[-1] = (style, clipped[-1][1] + char)
            else:
                clipped.append((style, char))
            used += vlen(char)
    return clipped


def compose_welcome(logo_rows, text_rows, columns):
    """Lay out the mark and text side by side, stacked, or as text alone.

    Side by side needs room for the mark plus WELCOME_MIN_TEXT columns of
    text; otherwise the text goes below the mark, and the mark is dropped
    when even it does not fit. The shorter column is centered vertically.
    """
    margin = [('', ' ' * WELCOME_MARGIN)]
    logo_width = max((sum(vlen(t) for _s, t in row) for row in logo_rows), default=0)
    side_width = columns - WELCOME_MARGIN - logo_width - WELCOME_GAP

    if logo_rows and side_width >= WELCOME_MIN_TEXT:
        height = max(len(logo_rows), len(text_rows))
        logo_top = (height - len(logo_rows)) // 2
        text_top = (height - len(text_rows)) // 2
        rows = []
        for index in range(height):
            logo_index, text_index = index - logo_top, index - text_top
            logo = (logo_rows[logo_index] if 0 <= logo_index < len(logo_rows)
                    else [('', ' ' * logo_width)])
            text = (text_rows[text_index] if 0 <= text_index < len(text_rows)
                    else [])
            rows.append(margin + logo + [('', ' ' * WELCOME_GAP)]
                        + _truncate(text, side_width))
        return rows

    text_width = max(columns - WELCOME_MARGIN, 1)
    text = [margin + _truncate(row, text_width) for row in text_rows]
    if logo_rows and columns >= WELCOME_MARGIN + logo_width:
        return [margin + row for row in logo_rows] + [[]] + text
    return text


def print_welcome(text_rows, columns):
    """Print the startup mark with the session summary beside it."""
    banner = load_shell_banner()
    depth = shell_color_depth()
    if term.color_enabled():
        logo_rows = shell_banner_row_fragments(banner, depth)
    else:
        logo_rows = [[('', line)] for line in shell_banner_panel(banner).splitlines()]
    rows = compose_welcome(logo_rows, text_rows, columns)
    if not term.color_enabled():
        print('\n'.join(''.join(text for _style, text in row).rstrip() for row in rows))
        return
    from prompt_toolkit import print_formatted_text
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.styles import Style

    fragments = []
    for index, row in enumerate(rows):
        if index:
            fragments.append(('', '\n'))
        fragments.extend(row)
    print_formatted_text(FormattedText(fragments), style=Style.from_dict(shell_style_rules(depth)),
                         color_depth=depth)
