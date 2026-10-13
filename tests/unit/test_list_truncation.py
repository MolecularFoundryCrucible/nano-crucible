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


@pytest.fixture
def fresh_page():
    helpers.begin_page(0)
    yield
    helpers.begin_page(0)


def test_more_hint_records_where_the_next_page_starts(monkeypatch, capsys, fresh_page):
    _tty(monkeypatch, True)
    records = ListResult([1] * 50, has_more=True, total=120, next_cursor='c2')

    helpers.print_more_hint(records, 50, SimpleNamespace(json=False, _shell_state={}))

    assert helpers.next_page() == {'cursor': 'c2', 'offset': None, 'start': 50, 'total': 120}
    assert "type 'more'" in capsys.readouterr().out


def test_later_pages_are_labelled_by_position(monkeypatch, capsys, fresh_page):
    _tty(monkeypatch, True)
    helpers.begin_page(50)
    records = ListResult([1] * 50, has_more=True, total=120, next_offset=100)

    assert helpers.count_label(records) == '51-100 of 120'
    helpers.print_more_hint(records, 50, SimpleNamespace(json=False))
    assert '20 more not shown' in capsys.readouterr().out
    assert helpers.next_page()['start'] == 100


@pytest.mark.parametrize('page, expected', [
    (None, {}),
    ({'cursor': 'c2', 'offset': None, 'start': 50}, {'cursor': 'c2'}),
    ({'cursor': None, 'offset': 100, 'start': 100}, {'offset': 100}),
])
def test_page_kwargs(page, expected):
    assert helpers.page_kwargs(SimpleNamespace(page=page)) == expected


def _shell():
    from crucible.cli.shell import core
    shell = core.CrucibleShell.__new__(core.CrucibleShell)
    from crucible.models import AccountCapabilities
    shell.state = {'debug': False}
    shell.client = SimpleNamespace(privilege_mode=None, can_elevate=False,
                                   capabilities=AccountCapabilities())
    shell.completer = None
    return shell


def test_shell_more_continues_the_last_listing(monkeypatch, fresh_page):
    from crucible.cli.shell import builtins
    seen = []

    def run(args):
        seen.append(getattr(args, 'page', None))
        helpers.print_more_hint(
            ListResult([1] * 2, has_more=True, total=9, next_cursor=f'c{len(seen) + 1}'),
            2, args)

    parser = argparse.ArgumentParser()
    parser.set_defaults(func=run, pageable=True)
    shell = _shell()
    shell.parser = parser
    monkeypatch.setattr('crucible.cli.helpers.fetch_project_context', lambda: (None, None))

    shell._dispatch('')
    assert builtins._more(shell, 'more') is True
    shell._dispatch(' ')
    shell.parser.parse_args = lambda argv: argparse.Namespace(func=run, pageable=True)
    shell._dispatch('dataset list')
    builtins._more(shell, 'more')
    builtins._more(shell, 'more')

    assert seen == [None, {'cursor': 'c2', 'offset': None, 'start': 2, 'total': 9},
                    {'cursor': 'c3', 'offset': None, 'start': 4, 'total': 9}]


def test_shell_more_without_a_listing(capsys):
    from crucible.cli.shell import builtins

    builtins._more(_shell(), 'more')

    assert 'Nothing to continue' in capsys.readouterr().out


def test_continued_pages_keep_the_first_total(monkeypatch, capsys, fresh_page):
    _tty(monkeypatch, True)
    helpers.begin_page(2, total=9)
    records = ListResult([1, 1], has_more=True, next_cursor='c3')

    assert helpers.count_label(records) == '3-4 of 9'
    helpers.print_more_hint(records, 2, SimpleNamespace(json=False))
    assert '5 more not shown' in capsys.readouterr().out
