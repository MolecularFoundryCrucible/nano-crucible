"""Startup banner: the Crucible mark rendered with half-block pixels."""

from .. import term
from ._common import (BANNER_MIN_WIDTH, BANNER_PIXEL_COLORS, shell_color_depth,
                      vlen)


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

def shell_banner_left_margin(panel, columns):
    width = max((vlen(line) for line in panel.splitlines()), default=0)
    return max((columns - width) // 2, 0)

def shell_banner_fragments(banner, left_margin=0):
    from prompt_toolkit.formatted_text import FormattedText

    fragments = []
    pairs = list(shell_banner_row_pairs(banner))
    for row_index, (upper_row, lower_row) in enumerate(pairs):
        if left_margin:
            fragments.append(('', ' ' * left_margin))
        for upper, lower in zip(upper_row, lower_row):
            upper_color = BANNER_PIXEL_COLORS[upper]
            lower_color = BANNER_PIXEL_COLORS[lower]
            if upper_color == lower_color:
                style = f'bg:{lower_color}'
                text = ' '
            else:
                style = f'fg:{upper_color} bg:{lower_color}'
                text = '▀'
            if fragments and fragments[-1][0] == style:
                previous_style, previous_text = fragments[-1]
                fragments[-1] = (previous_style, previous_text + text)
            else:
                fragments.append((style, text))
        if row_index < len(pairs) - 1:
            fragments.append(('', '\n'))
    return FormattedText(fragments)

def print_shell_banner(columns):
    if columns < BANNER_MIN_WIDTH:
        return False
    banner = load_shell_banner()
    panel = shell_banner_panel(banner)
    left_margin = shell_banner_left_margin(panel, columns)
    if not term.color_enabled():
        prefix = ' ' * left_margin
        print('\n'.join(f'{prefix}{line}' for line in panel.splitlines()))
        return True
    from prompt_toolkit import print_formatted_text
    print_formatted_text(
        shell_banner_fragments(banner, left_margin=left_margin),
        color_depth=shell_color_depth(),
    )
    return True
