"""The shell switches elevation off after the prompt sits idle."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def elevated_shell(monkeypatch):
    from crucible.cli import shell
    from crucible.config import config

    monkeypatch.setitem(config._data, 'elevation_timeout', '15')
    started = []
    monkeypatch.setattr(shell.core.threading.Timer, 'start', lambda self: started.append(self))
    instance = shell.CrucibleShell(MagicMock())
    instance.state = {'elevated': True}
    instance.client = MagicMock(privilege_mode='elevated', can_elevate=True)
    instance._session = MagicMock()
    instance._started = started
    return instance


def test_idle_prompt_drops_elevation_and_says_so(elevated_shell, capsys):
    elevated_shell._arm_idle_timer()
    timer, = elevated_shell._started
    assert timer.interval == 15 * 60

    timer.function(*timer.args)
    assert elevated_shell.state['elevated'] is False
    assert elevated_shell.client.privilege_mode == 'normal'
    elevated_shell._session.app.invalidate.assert_called_once()

    elevated_shell._disarm_idle_timer()
    assert 'switched off after 15 idle minutes' in capsys.readouterr().out
    elevated_shell.client.refresh_profile.assert_called_once()


def test_entering_a_line_in_time_keeps_elevation(elevated_shell, capsys):
    elevated_shell._arm_idle_timer()
    timer, = elevated_shell._started

    elevated_shell._disarm_idle_timer()
    timer.function(*timer.args)

    assert elevated_shell.state['elevated'] is True
    assert elevated_shell.client.privilege_mode == 'elevated'
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('timeout, elevated', [('0', True), ('15', False)])
def test_no_timer_when_disabled_or_not_elevated(elevated_shell, monkeypatch, timeout, elevated):
    from crucible.config import config

    monkeypatch.setitem(config._data, 'elevation_timeout', timeout)
    elevated_shell.state['elevated'] = elevated
    elevated_shell._arm_idle_timer()
    assert elevated_shell._started == []


@pytest.mark.parametrize('raw, minutes', [(None, 15), ('30', 30), ('0', 0), ('soon', 15), ('-5', 0)])
def test_elevation_timeout_setting(monkeypatch, raw, minutes):
    from crucible.config import config

    if raw is None:
        monkeypatch.delitem(config._data, 'elevation_timeout', raising=False)
    else:
        monkeypatch.setitem(config._data, 'elevation_timeout', raw)
    assert config.elevation_timeout == minutes


def test_missing_prompt_toolkit_says_how_to_fix(monkeypatch, capsys):
    import builtins
    import sys

    from crucible import cli

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == 'shell' or name.endswith('cli.shell'):
            raise ModuleNotFoundError("No module named 'prompt_toolkit'", name='prompt_toolkit')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(sys, 'argv', ['crucible'])
    monkeypatch.setattr(builtins, '__import__', fake_import)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert 'needs prompt_toolkit' in capsys.readouterr().err
