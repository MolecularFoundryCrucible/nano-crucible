"""Unit coverage for how the CLI renders API timestamps in local time."""

import time

import pytest

from crucible.cli import term


@pytest.fixture
def pacific(monkeypatch):
    if not hasattr(time, 'tzset'):
        pytest.skip('time.tzset is not available on Windows')
    monkeypatch.setenv('TZ', 'America/Los_Angeles')
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.parametrize('value', [
    '2026-10-19T03:00:00.000000Z',
    '2026-10-19T03:00:00+00:00',
    '2026-10-19T03:00:00',
])
def test_utc_timestamps_are_shown_in_local_time(pacific, value):
    assert term.fmt_date(value) == '2026-10-18'
    assert term.fmt_ts(value).startswith('2026-10-18 20:00')


def test_a_bare_date_keeps_its_calendar_day(pacific):
    assert term.fmt_date('2026-10-19') == '2026-10-19'
    assert term.fmt_ts('2026-10-19').startswith('2026-10-19 00:00')


def test_unparseable_values_pass_through():
    assert term.fmt_date('garbage') == 'garbage'
    assert term.fmt_ts('garbage') == 'garbage'
