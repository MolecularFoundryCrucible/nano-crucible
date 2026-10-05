"""Shared constants and rendering helpers for the interactive shell."""

import os
import re as _re

from .. import term

PROMPT = "crucible> "
BRAND_DARK_BLUE = '#031e2d'
BRAND_LIGHT_BLUE = '#a8c4cd'
BRAND_ORANGE = '#ff6600'
BRAND_OFF_WHITE = '#eeeeee'
BANNER_MIN_WIDTH = 16
BANNER_PIXEL_COLORS = {
    '_': BRAND_LIGHT_BLUE,
    '%': BRAND_DARK_BLUE,
    '=': BRAND_ORANGE,
    '.': BRAND_OFF_WHITE,
}


def get_subparser_map(parser):
    """Return {name: subparser} for a parser's subcommands, or {} if none."""
    for action in parser._actions:
        if hasattr(action, 'choices') and isinstance(action.choices, dict):
            return action.choices or {}
    return {}


def vlen(s):
    """Visual (terminal column) width of s; falls back to len() if wcwidth unavailable."""
    try:
        from wcwidth import wcswidth
        w = wcswidth(s)
        return w if w >= 0 else len(s)
    except ImportError:
        return len(s)


ENTITY_ICONS = {
    'dataset':    '<ansibrightblack><b>[ds]</b></ansibrightblack>',
    'sample':     '<ansibrightblack><b>[s]</b></ansibrightblack>',
    'instrument': '<ansibrightblack><b>[i]</b></ansibrightblack>',
}


def shell_html(markup):
    from prompt_toolkit.formatted_text import HTML

    if not term.color_enabled():
        markup = _re.sub(r'</?[^>]+>', '', markup)
    return HTML(markup)


def shell_style_rules():
    if not term.color_enabled():
        return {
            'bottom-toolbar':      'noinherit',
            'bottom-toolbar.text': 'noinherit',
            'tb-project':          'noinherit',
            'tb-separator':        'noinherit',
            'tb-api':              'noinherit',
            'tb-api-attention':    'noinherit',
            'tb-clock':            'noinherit',
            'tb-debug':            'noinherit',
            'tb-elevated':         'noinherit',
        }
    return {
        'bottom-toolbar':      f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_LIGHT_BLUE}',
        'bottom-toolbar.text': f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_LIGHT_BLUE}',
        'tb-project':          f'noinherit bg:{BRAND_LIGHT_BLUE} fg:{BRAND_DARK_BLUE}',
        'tb-separator':        f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_ORANGE}',
        'tb-api':              f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_LIGHT_BLUE}',
        'tb-api-attention':    f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_ORANGE} bold',
        'tb-clock':            f'noinherit bg:{BRAND_DARK_BLUE} fg:{BRAND_LIGHT_BLUE}',
        'tb-debug':            f'noinherit bg:{BRAND_ORANGE} fg:{BRAND_DARK_BLUE} bold',
        'tb-elevated':         f'noinherit bg:#b00020 fg:{BRAND_OFF_WHITE} bold',
    }

def shell_color_depth():
    from prompt_toolkit.output import ColorDepth

    if not term.color_enabled():
        return ColorDepth.DEPTH_1_BIT
    configured = ColorDepth.from_env()
    if configured is not None:
        return configured
    if os.environ.get('COLORTERM', '').lower() in ('truecolor', '24bit'):
        return ColorDepth.DEPTH_24_BIT
    return None
