"""Shared constants and rendering helpers for the interactive shell."""

import os
import re as _re
import sys

from .. import term

PROMPT = "crucible> "

# Every shell color, by terminal color depth (24-bit, 256-color, 16-color).
# The fallbacks are chosen by hand: prompt_toolkit's nearest match by RGB
# distance turns the dark blue into a neutral grey.
BRAND_PALETTE = {
    'dark_blue':  {24: '#031e2d', 8: '#00005f', 4: 'ansiblue'},
    'light_blue': {24: '#a8c4cd', 8: '#afd7d7', 4: 'ansicyan'},
    'orange':     {24: '#ff6600', 8: '#ff5f00', 4: 'ansiyellow'},
    'off_white':  {24: '#eeeeee', 8: '#ffffff', 4: 'ansiwhite'},
    'alert':      {24: '#b00020', 8: '#af0000', 4: 'ansired'},
}
BANNER_PIXELS = {'_': 'light_blue', '%': 'dark_blue', '=': 'orange', '.': 'off_white'}
_TRUE_COLOR_PROGRAMS = ('iTerm.app', 'vscode', 'WezTerm')


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


def brand_colors(depth=None):
    """Return {color name: style color} from BRAND_PALETTE for a color depth."""
    from prompt_toolkit.output import ColorDepth

    depth = depth or shell_color_depth()
    bits = {ColorDepth.DEPTH_24_BIT: 24, ColorDepth.DEPTH_8_BIT: 8}.get(depth, 4)
    return {name: values[bits] for name, values in BRAND_PALETTE.items()}


def shell_style_rules(depth=None):
    names = ('bottom-toolbar', 'bottom-toolbar.text', 'tb-project', 'tb-separator',
             'tb-api', 'tb-api-attention', 'tb-clock', 'tb-debug', 'tb-elevated',
             'welcome-title', 'welcome-dim', 'welcome-elevated')
    if not term.color_enabled():
        return {name: 'noinherit' for name in names}
    c = brand_colors(depth)
    return {
        'bottom-toolbar':      f"noinherit bg:{c['dark_blue']} fg:{c['light_blue']}",
        'bottom-toolbar.text': f"noinherit bg:{c['dark_blue']} fg:{c['light_blue']}",
        'tb-project':          f"noinherit bg:{c['light_blue']} fg:{c['dark_blue']}",
        'tb-separator':        f"noinherit bg:{c['dark_blue']} fg:{c['orange']}",
        'tb-api':              f"noinherit bg:{c['dark_blue']} fg:{c['light_blue']}",
        'tb-api-attention':    f"noinherit bg:{c['dark_blue']} fg:{c['orange']} bold",
        'tb-clock':            f"noinherit bg:{c['dark_blue']} fg:{c['light_blue']}",
        'tb-debug':            f"noinherit bg:{c['orange']} fg:{c['dark_blue']} bold",
        'tb-elevated':         f"noinherit bg:{c['alert']} fg:{c['off_white']} bold",
        'welcome-title':       f"bold fg:{c['orange']}",
        'welcome-dim':         'fg:ansibrightblack',
        'welcome-elevated':    f"bold bg:{c['alert']} fg:{c['off_white']}",
    }


def _advertises_true_color(env):
    terminal = env.get('TERM', '')
    return (env.get('COLORTERM', '').lower() in ('truecolor', '24bit')
            or env.get('TERM_PROGRAM') in _TRUE_COLOR_PROGRAMS
            or bool(env.get('WT_SESSION'))
            or terminal.endswith('-direct') or terminal.endswith('-24bit'))


def shell_color_depth():
    """Color depth for the shell, also selecting the BRAND_PALETTE column.

    PROMPT_TOOLKIT_COLOR_DEPTH wins, then any true-color hint from the
    terminal. Otherwise this mirrors prompt_toolkit's own default, but as a
    concrete value so the palette matches what is rendered.
    """
    from prompt_toolkit.output import ColorDepth

    if not term.color_enabled():
        return ColorDepth.DEPTH_1_BIT
    configured = ColorDepth.from_env()
    if configured is not None:
        return configured
    if _advertises_true_color(os.environ):
        return ColorDepth.DEPTH_24_BIT
    terminal = os.environ.get('TERM', '')
    if terminal == 'dumb':
        return ColorDepth.DEPTH_1_BIT
    if terminal in ('linux', 'eterm-color') or (sys.platform == 'win32' and not terminal):
        return ColorDepth.DEPTH_4_BIT
    return ColorDepth.DEPTH_8_BIT
