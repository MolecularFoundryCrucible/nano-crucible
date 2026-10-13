"""Unit coverage for paging long list output."""

import argparse
import io
import sys
from types import SimpleNamespace

import pytest

from crucible.cli import helpers, pager

LINK = '\033]8;;https://example.test\007text\033]8;;\007'


@pytest.fixture
def tty(monkeypatch):
    """Return a function that installs a fake terminal as stdout.

    It must run inside the test body: pytest's capture replaces sys.stdout
    again after fixtures are set up.
    """
    monkeypatch.setattr(pager, '_terminal_lines', lambda: 10)
    monkeypatch.delenv('CRUCIBLE_PAGER', raising=False)
    monkeypatch.delenv('PAGER', raising=False)
    from crucible.config import config
    monkeypatch.setitem(config._data, 'pager', 'auto')

    def install():
        stdout = io.StringIO()
        stdout.isatty = lambda: True
        monkeypatch.setattr(sys, 'stdout', stdout)
        return stdout
    return install


def args(**overrides):
    values = dict(pageable=True, json=False, no_pager=False)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_list_commands_are_pageable():
    parser = argparse.ArgumentParser()
    helpers.add_limit_arguments(parser)

    assert parser.parse_args([]).pageable is True


@pytest.mark.parametrize('overrides', [
    {'pageable': False}, {'json': True}, {'no_pager': True}])
def test_paging_is_skipped(tty, overrides):
    tty()
    assert pager.should_page(args(**overrides)) is False


def test_paging_needs_a_terminal(tty, monkeypatch):
    out = tty()
    out.isatty = lambda: False

    assert pager.should_page(args()) is False


def test_paging_is_off_unless_turned_on(tty, monkeypatch):
    tty()
    from crucible.config import config
    monkeypatch.delitem(config._data, 'pager')

    assert config.pager == 'never'
    assert pager.should_page(args()) is False


def test_paging_can_be_turned_off_in_config(tty, monkeypatch):
    tty()
    from crucible.config import config
    monkeypatch.setitem(config._data, 'pager', 'never')

    assert pager.should_page(args()) is False


def test_short_output_prints_directly(tty, monkeypatch):
    out = tty()
    monkeypatch.setattr(pager.subprocess, 'run', lambda *a, **k: pytest.fail('paged'))

    with pager.paged(args()):
        print('one\ntwo')

    assert out.getvalue() == 'one\ntwo\n'


def test_long_output_goes_to_the_pager(tty, monkeypatch):
    out = tty()
    calls = {}
    monkeypatch.setattr(pager, '_pager_argv', lambda: ['less', '-FRX'])
    monkeypatch.setattr(pager, '_strips_links', lambda argv: False)
    monkeypatch.setattr(pager.subprocess, 'run',
                        lambda argv, **kw: calls.update(argv=argv, input=kw['input']))

    with pager.paged(args()):
        for n in range(30):
            print(f'row {n} {LINK}')

    assert calls['argv'] == ['less', '-FRX']
    assert 'row 29' in calls['input'] and LINK in calls['input']
    assert out.getvalue() == ''


def test_old_less_gets_plain_links(tty, monkeypatch):
    tty()
    calls = {}
    monkeypatch.setattr(pager, '_pager_argv', lambda: ['less', '-FRX'])
    monkeypatch.setattr(pager, '_strips_links', lambda argv: True)
    monkeypatch.setattr(pager.subprocess, 'run',
                        lambda argv, **kw: calls.update(input=kw['input']))

    with pager.paged(args()):
        print('\n'.join([LINK] * 30))

    assert '\033]8' not in calls['input'] and 'text' in calls['input']


def test_missing_pager_prints_directly(tty, monkeypatch):
    out = tty()
    monkeypatch.setattr(pager, '_pager_argv', lambda: None)

    with pager.paged(args()):
        print('\n'.join(['x'] * 30))

    assert out.getvalue().count('x') == 30


def test_pager_choice_follows_the_environment(monkeypatch):
    monkeypatch.setattr(pager.shutil, 'which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setenv('PAGER', 'more')
    monkeypatch.setenv('CRUCIBLE_PAGER', 'less -R')

    assert pager._pager_argv() == ['less', '-R']

    monkeypatch.delenv('CRUCIBLE_PAGER')
    assert pager._pager_argv() == ['more']

    monkeypatch.delenv('PAGER')
    assert pager._pager_argv() == ['less', '-FRX']


@pytest.mark.parametrize('version, strips', [('less 590 (GNU)', False), ('less 551', True)])
def test_old_less_versions_strip_links(monkeypatch, version, strips):
    monkeypatch.setattr(pager.subprocess, 'run',
                        lambda *a, **k: SimpleNamespace(stdout=version))

    assert pager._strips_links(['less', '-FRX']) is strips


def test_no_pager_flag_is_global(monkeypatch):
    from crucible.cli import main

    seen = {}
    monkeypatch.setattr('sys.argv', ['crucible', '--no-pager', 'config', 'path'])
    monkeypatch.setattr('crucible.cli.config.cmd_path',
                        lambda a: seen.setdefault('no_pager', a.no_pager), raising=False)
    try:
        main()
    except SystemExit:
        pass

    assert seen.get('no_pager') is True
