"""Unit coverage for list limits, counts, and the "more not shown" note."""

import argparse
from types import SimpleNamespace

import pytest

from crucible.cli import helpers
from crucible.resources.base import ListResult


def parse(argv):
    parser = argparse.ArgumentParser()
    helpers.add_limit_arguments(parser, 'datasets')
    return parser.parse_args(argv)


def test_limit_defaults_to_the_setting(monkeypatch):
    from crucible.config import config
    monkeypatch.setitem(config._data, 'default_limit', '50')

    assert helpers.resolve_limit(parse([])) == 50
    assert helpers.resolve_limit(parse(['--limit', '7'])) == 7
    assert helpers.resolve_limit(parse(['--all'])) is None


def test_default_limit_is_50(monkeypatch):
    from crucible.config import config
    monkeypatch.delitem(config._data, 'default_limit', raising=False)

    assert config.default_limit == 50


@pytest.mark.parametrize('records, shown, expected', [
    (ListResult([1] * 50, has_more=True, total=1234), None, '50 of 1,234'),
    (ListResult([1] * 50, has_more=True), None, '50+'),
    (ListResult([1] * 3), None, '3'),
    ([1] * 3, None, '3'),
    (ListResult([1] * 50, has_more=True, total=1234), 4, '4 of 1,234'),
])
def test_count_label(records, shown, expected):
    assert helpers.count_label(records, shown) == expected


def _tty(monkeypatch, is_tty):
    import sys
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: is_tty, raising=False)


def test_more_hint_names_the_remaining_count(monkeypatch, capsys):
    _tty(monkeypatch, True)

    helpers.print_more_hint(ListResult([1] * 50, has_more=True, total=1234), 50,
                            SimpleNamespace(json=False), hint='narrow with filters')

    out = capsys.readouterr().out
    assert '1,184 more not shown' in out
    assert 'narrow with filters' in out and '--all' in out


def test_more_hint_is_silent_when_everything_was_shown(monkeypatch, capsys):
    _tty(monkeypatch, True)

    helpers.print_more_hint(ListResult([1] * 3, has_more=False, total=3), 50, None)

    assert capsys.readouterr() == ('', '')


def test_more_hint_guesses_for_plain_lists_at_the_limit(monkeypatch, capsys):
    _tty(monkeypatch, True)

    helpers.print_more_hint([1] * 20, 20, None, allow_all=False)

    out = capsys.readouterr().out
    assert 'there may be more' in out
    assert 'refine the query' in out and '--all' not in out


@pytest.mark.parametrize('args, is_tty', [(SimpleNamespace(json=True), True), (None, False)])
def test_more_hint_goes_to_stderr_for_scripts(monkeypatch, capsys, args, is_tty):
    _tty(monkeypatch, is_tty)

    helpers.print_more_hint(ListResult([1], has_more=True, total=5), 1, args)

    captured = capsys.readouterr()
    assert captured.out == ''
    assert '4 more not shown' in captured.err


def test_sort_like_keeps_list_metadata():
    result = helpers.sort_like(ListResult([3, 1, 2], has_more=True, total=9))

    assert result == [1, 2, 3]
    assert (result.has_more, result.total) == (True, 9)
