"""Unit coverage for choosing and launching the user's editor.

The resolution tests run on any OS by passing the platform explicitly. The
round-trip tests launch a real stub editor, so on a Windows CI runner they
exercise the actual Windows process launch, including a .cmd shim.
"""

import json
import os
import sys
import textwrap

import pytest

from crucible.cli import editor, term


@pytest.fixture(autouse=True)
def no_configured_editor(monkeypatch):
    from crucible.config import config

    monkeypatch.setitem(config._data, 'editor', None)
    monkeypatch.delenv('VISUAL', raising=False)
    monkeypatch.delenv('EDITOR', raising=False)


@pytest.mark.parametrize('path, name', [
    ('code', 'code'),
    (r'C:\Users\me\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd', 'code'),
    (r'C:\Program Files\Notepad++\notepad++.exe', 'notepad++'),
    ('/usr/bin/gvim', 'gvim'),
    ('Code.EXE', 'code'),
])
def test_program_name_ignores_directory_case_and_extension(path, name):
    assert editor.program_name(path) == name


def test_windows_paths_with_spaces_survive_splitting():
    parts = editor.split_command(
        r'"C:\Program Files\Notepad++\notepad++.exe" -multiInst', platform='win32')

    assert parts == [r'C:\Program Files\Notepad++\notepad++.exe', '-multiInst']


@pytest.mark.parametrize('configured, platform, expected_tail', [
    ('code', 'win32', ['--wait']),
    (r'C:\tools\code.cmd', 'win32', ['--wait']),
    ('code --wait', 'win32', []),
    ('notepad++', 'win32', ['-multiInst', '-nosession']),
    ('notepad', 'win32', []),
    ('gvim', 'linux', ['-f']),
    ('vim', 'linux', []),
])
def test_wait_flags_are_added_once(monkeypatch, configured, platform, expected_tail):
    monkeypatch.setattr(editor.shutil, 'which', lambda name: None)

    command = editor.editor_command(configured, platform=platform)

    assert command[len(editor.split_command(configured, platform)):] == expected_tail


def test_resource_edits_and_config_edit_share_the_windows_default(monkeypatch):
    from crucible.cli.config import get_default_editor

    monkeypatch.setattr(editor.sys, 'platform', 'win32')
    monkeypatch.setattr(editor.shutil, 'which', lambda name: None)

    assert editor.editor_command()[0] == 'notepad'
    assert get_default_editor() == 'notepad'


def test_executable_is_resolved_to_a_full_path(monkeypatch):
    shim = r'C:\Users\me\bin\code.cmd'
    monkeypatch.setattr(editor.shutil, 'which', lambda name: shim if name == 'code' else None)

    assert editor.editor_command('code', platform='win32') == [shim, '--wait']


def _stub_editor(tmp_path, script):
    """Create a fake editor that rewrites the JSON file it is given.

    On Windows it is a .cmd shim calling Python, the same shape as VS Code's
    code.cmd; elsewhere an executable Python script.
    """
    program = tmp_path / 'fake_editor.py'
    program.write_text(textwrap.dedent(script))
    if os.name == 'nt':
        shim = tmp_path / 'fakeedit.cmd'
        shim.write_text(f'@"{sys.executable}" "{program}" %*\r\n')
        return str(shim)
    shim = tmp_path / 'fakeedit'
    shim.write_text(f'#!{sys.executable}\n' + program.read_text())
    shim.chmod(0o755)
    return str(shim)


def test_round_trip_through_a_real_editor_process(tmp_path, monkeypatch):
    from crucible.config import config

    stub = _stub_editor(tmp_path, """
        import json, sys
        path = sys.argv[-1]
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        data['location'] = 'Building 67'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    """)
    monkeypatch.setitem(config._data, 'editor', stub)

    edited = term.open_editor_json({'instrument_name': 'Titan', 'location': 'old'})

    assert edited == {'instrument_name': 'Titan', 'location': 'Building 67'}


def test_unchanged_file_and_bom_written_by_notepad(tmp_path, monkeypatch):
    from crucible.config import config

    stub = _stub_editor(tmp_path, """
        import sys
        path = sys.argv[-1]
        with open(path, encoding='utf-8') as f:
            text = f.read()
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(text.replace('old', 'new'))
    """)
    monkeypatch.setitem(config._data, 'editor', stub)

    assert term.open_editor_json({'location': 'old'}) == {'location': 'new'}


def test_missing_editor_reports_how_to_set_one(monkeypatch):
    from crucible.config import config

    monkeypatch.setitem(config._data, 'editor', 'definitely-not-an-editor-xyz')

    with pytest.raises(RuntimeError, match='config set editor'):
        term.open_editor_json({'a': 1})


def test_editor_error_exit_is_reported(tmp_path, monkeypatch):
    from crucible.config import config

    stub = _stub_editor(tmp_path, """
        import sys
        sys.exit(3)
    """)
    monkeypatch.setitem(config._data, 'editor', stub)

    with pytest.raises(RuntimeError, match='exited with an error'):
        term.open_editor_json({'a': 1})


def test_json_written_without_trailing_newline_still_parses(tmp_path, monkeypatch):
    from crucible.config import config

    stub = _stub_editor(tmp_path, """
        import sys
        with open(sys.argv[-1], 'w', encoding='utf-8') as f:
            f.write('{"a": 2,}')
    """)
    monkeypatch.setitem(config._data, 'editor', stub)

    assert term.open_editor_json({'a': 1}) == json.loads('{"a": 2}')
