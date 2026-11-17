"""The shell's once-a-day check for a newer nano-crucible on PyPI."""

import json
import time

import pytest

from crucible.cli import updates


@pytest.fixture
def pypi(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, '_cache_file', lambda: tmp_path / 'update_check.json')
    monkeypatch.setattr(updates, '_editable_install', lambda: False)
    calls = []

    def latest(current, timeout):
        calls.append(current)
        return '4.1.0'
    monkeypatch.setattr(updates, '_latest_from_pypi', latest)
    return calls


def test_reports_a_newer_release_and_caches_the_answer(pypi, tmp_path):
    assert updates.available_update('4.0.0') == '4.1.0'
    assert updates.available_update('4.0.0') == '4.1.0'

    assert len(pypi) == 1
    assert json.loads((tmp_path / 'update_check.json').read_text())['latest'] == '4.1.0'


def test_asks_again_once_the_cache_is_a_day_old(pypi, tmp_path):
    (tmp_path / 'update_check.json').write_text(
        json.dumps({'checked_at': time.time() - updates.CHECK_INTERVAL - 1, 'latest': '4.0.5'}))

    assert updates.available_update('4.0.0') == '4.1.0'
    assert len(pypi) == 1


@pytest.mark.parametrize('current', ['4.1.0', '4.2.0'])
def test_no_update_when_current_or_ahead(pypi, current):
    assert updates.available_update(current) is None


@pytest.mark.parametrize('current, enabled', [('4.0.0', False), ('4.0.0a1', True), ('4.0.0.dev3', True)])
def test_disabled_or_prerelease_installs_are_not_checked(pypi, current, enabled):
    assert updates.available_update(current, enabled=enabled) is None
    assert pypi == []


def test_editable_installs_are_not_checked(pypi, monkeypatch):
    monkeypatch.setattr(updates, '_editable_install', lambda: True)

    assert updates.available_update('4.0.0') is None
    assert pypi == []


def test_failures_are_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, '_cache_file', lambda: tmp_path / 'update_check.json')
    monkeypatch.setattr(updates, '_editable_install', lambda: False)

    def offline(current, timeout):
        raise OSError('offline')
    monkeypatch.setattr(updates, '_latest_from_pypi', offline)

    assert updates.available_update('4.0.0') is None


def test_latest_skips_prereleases_and_yanked_releases(monkeypatch):
    payload = {'releases': {
        '3.3.0': [{'yanked': False}], '4.0.0': [{'yanked': False}],
        '4.1.0': [{'yanked': True}], '4.2.0rc1': [{'yanked': False}], '4.0.1': [],
    }}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return payload
    monkeypatch.setattr('requests.get', lambda *a, **k: Reply())

    assert updates._latest_from_pypi('3.3.0', 1) == '4.0.0'


@pytest.mark.parametrize('prefix, command', [
    ('/home/u/.local/share/uv/tools/nano-crucible', 'uv tool upgrade nano-crucible'),
    ('/home/u/.local/pipx/venvs/nano-crucible', 'pipx upgrade nano-crucible'),
    ('/opt/conda/envs/lab', 'pip install -U nano-crucible'),
])
def test_upgrade_command_matches_the_installer(monkeypatch, prefix, command):
    monkeypatch.setattr('sys.prefix', prefix)
    assert updates.upgrade_command() == command
