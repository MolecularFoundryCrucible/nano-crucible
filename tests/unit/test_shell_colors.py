"""Unit coverage for brand colors at each terminal color depth."""

import pytest
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import _256_colors

from crucible.cli import term
from crucible.cli.shell import _common as shell_common

TRUE_COLOR_HINTS = ('COLORTERM', 'TERM_PROGRAM', 'WT_SESSION', 'PROMPT_TOOLKIT_COLOR_DEPTH')


@pytest.fixture
def color_env(monkeypatch):
    monkeypatch.setattr(term, '_COLOR_ENABLED', True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    for name in TRUE_COLOR_HINTS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('TERM', 'xterm-256color')
    return monkeypatch


def rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def test_true_color_keeps_the_exact_brand_colors():
    colors = shell_common.brand_colors(ColorDepth.DEPTH_24_BIT)

    assert colors['dark_blue'] == '#031e2d'
    assert colors['light_blue'] == '#a8c4cd'


def test_256_colors_keep_the_dark_blue_blue():
    colors = shell_common.brand_colors(ColorDepth.DEPTH_8_BIT)

    red, green, blue = rgb(colors['dark_blue'])
    assert blue > red and blue > green
    assert _256_colors[rgb(colors['dark_blue'])] == 17
    for name, value in colors.items():
        assert value.startswith('#'), name


def test_16_colors_keep_light_blue_and_off_white_apart():
    colors = shell_common.brand_colors(ColorDepth.DEPTH_4_BIT)

    assert colors['dark_blue'] == 'ansiblue'
    assert colors['light_blue'] != colors['off_white']
    assert all(value.startswith('ansi') for value in colors.values())


def test_style_rules_follow_the_color_depth():
    rules = shell_common.shell_style_rules(ColorDepth.DEPTH_8_BIT)

    assert 'bg:#00005f' in rules['bottom-toolbar']


@pytest.mark.parametrize('name, value', [
    ('COLORTERM', 'truecolor'),
    ('COLORTERM', '24bit'),
    ('TERM_PROGRAM', 'iTerm.app'),
    ('TERM_PROGRAM', 'vscode'),
    ('TERM_PROGRAM', 'WezTerm'),
    ('WT_SESSION', 'abc'),
    ('TERM', 'xterm-direct'),
])
def test_true_color_is_detected_from_terminal_hints(color_env, name, value):
    color_env.setenv(name, value)

    assert shell_common.shell_color_depth() == ColorDepth.DEPTH_24_BIT


@pytest.mark.parametrize('term_name, expected', [
    ('xterm-256color', ColorDepth.DEPTH_8_BIT),
    ('linux', ColorDepth.DEPTH_4_BIT),
    ('dumb', ColorDepth.DEPTH_1_BIT),
])
def test_without_true_color_the_depth_is_concrete(color_env, term_name, expected):
    color_env.setenv('TERM', term_name)

    assert shell_common.shell_color_depth() == expected


@pytest.mark.parametrize('term_name, expected', [
    ('', ColorDepth.DEPTH_4_BIT),
    ('xterm-256color', ColorDepth.DEPTH_8_BIT),
])
def test_windows_follows_term_when_set(color_env, monkeypatch, term_name, expected):
    monkeypatch.setattr(shell_common.sys, 'platform', 'win32')
    if term_name:
        color_env.setenv('TERM', term_name)
    else:
        color_env.delenv('TERM', raising=False)

    assert shell_common.shell_color_depth() == expected
