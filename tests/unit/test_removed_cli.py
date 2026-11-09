"""Commands, aliases, and options removed in 4.0.0 stop with what to use instead."""

import sys

import pytest

from crucible.cli import main


def run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, 'argv', ['crucible', *argv])
    with pytest.raises(SystemExit) as stopped:
        main()
    return stopped.value.code, capsys.readouterr().err


@pytest.mark.parametrize('argv, replacement', [
    (('upload', '-i', 'x.dat'), 'crucible dataset create'),
    (('account', 'api-key'), 'crucible account keys create'),
    (('dataset', 'list-access-groups', 'MFID'), 'crucible dataset access list'),
    (('dataset', 'add-access-group', 'MFID', 'group'), 'crucible dataset access grant'),
    (('user', 'add-access-group', 'fabrice', 'group'), 'crucible project add-user'),
    (('user', 'remove-access-group', 'fabrice', 'group'), 'crucible project remove-user'),
    (('sa', 'add-access-group', 'robot', 'group'), 'crucible instrument bind-sa'),
    (('dataset', 'publish', 'MFID'), 'crucible dataset set-public'),
    (('project', 'get-users', 'p'), 'crucible project list-users'),
])
def test_removed_commands_name_the_replacement(monkeypatch, capsys, argv, replacement):
    code, err = run(monkeypatch, capsys, *argv)

    assert code == 2
    assert 'removed in nano-crucible 4.0.0' in err
    assert replacement in err


@pytest.mark.parametrize('argv, replacement', [
    (('user', 'get', '--orcid', '0000-0001-6402-3752'), 'the USER argument'),
    (('sa', 'get', '--username', 'robot'), 'the SA argument'),
    (('project', 'add-user', 'p', '--orcid', '0000-0001-6402-3752'), '--user'),
    (('project', 'get', 'p', '--members'), '--include-members'),
    (('instrument', 'get', 'x', '--by-id'), 'told apart automatically'),
    (('dataset', 'list', '--instrument', 'XRD'), '--instrument-id'),
    (('dataset', 'list', '-pid', 'p'), '--project-id'),
    (('sample', 'update', 'MFID', '--public'), 'sample set-public'),
    (('dataset', 'add-file', 'MFID', 'f.dat', '--upload-protocol', 'legacy'), 'signed multipart'),
    (('ag', 'list', '--group', 'g'), '--project'),
])
def test_removed_options_name_the_replacement(monkeypatch, capsys, argv, replacement):
    code, err = run(monkeypatch, capsys, *argv)

    assert code == 2
    assert 'was removed in nano-crucible 4.0.0' in err
    assert replacement in err


def test_removed_commands_are_left_out_of_help(capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['crucible', 'account', '--help'])
    with pytest.raises(SystemExit):
        main()

    assert 'api-key' not in capsys.readouterr().out


def test_the_current_project_environment_variable_stops_the_cli(monkeypatch, capsys):
    monkeypatch.setenv('CRUCIBLE_CURRENT_PROJECT', 'p')
    code, err = run(monkeypatch, capsys, 'whoami')

    assert code == 2
    assert 'CRUCIBLE_CURRENT_PROJECT was removed' in err
    assert '--project-id' in err
