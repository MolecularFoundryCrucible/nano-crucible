"""Unit coverage for the shell's secret-filtering history."""

import os
import stat

import pytest

from crucible.cli.shell.history import PrivateFileHistory, is_secret


@pytest.mark.parametrize('line, secret', [
    ('config set api_key abc123', True),
    ('  config   set API_KEY abc', True),
    ('!CRUCIBLE_API_KEY=abc crucible whoami', True),
    ('config set api_url https://example.test', False),
    ('config get api_key', False),
    ('dataset list', False),
])
def test_secret_lines_are_detected(line, secret):
    assert is_secret(line) is secret


def test_history_skips_secrets_and_is_owner_only(tmp_path):
    path = tmp_path / 'history'
    history = PrivateFileHistory(str(path))

    history.append_string('dataset list')
    history.append_string('config set api_key abc123')

    content = path.read_text()
    assert 'dataset list' in content
    assert 'abc123' not in content
    assert 'config set api_key abc123' not in history.get_strings()
    if os.name == 'posix':
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
