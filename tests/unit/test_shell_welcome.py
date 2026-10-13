"""Unit coverage for the shell's startup welcome: logo beside the session info."""

import pytest

from crucible.cli import term
from crucible.cli.shell import banner as shell_banner
from crucible.cli.shell._common import vlen


def plain(row):
    return ''.join(text for _style, text in row)


def rows_text(rows):
    return [plain(row).rstrip() for row in rows]


def info(**overrides):
    values = dict(version='3.3.0', first_name='Ada', user_label='A. Lovelace (@ada)',
                  platform_role='admin', api_url='https://crucible.lbl.gov/api/v3',
                  project='alphafold', elevated=False, deletions=0, joins=0)
    values.update(overrides)
    return shell_banner.welcome_rows(**values)


def test_welcome_rows_name_the_session():
    text = rows_text(info())

    assert text[0] == 'Crucible shell 3.3.0'
    assert text[1] == 'Welcome, Ada.'
    assert any(line.startswith('User') and 'A. Lovelace (@ada) · admin' in line for line in text)
    assert any(line.startswith('API') and 'https://crucible.lbl.gov/api/v3' in line for line in text)
    assert any(line.startswith('Project') and 'alphafold' in line for line in text)
    assert any(line.startswith('Access') and 'normal' in line for line in text)
    assert text[-1] == "Type 'help' for commands, 'exit' to quit."
    assert not any(line.startswith('Pending') for line in text)


def test_welcome_rows_mark_elevation_and_pending_reviews():
    text = rows_text(info(elevated=True, deletions=2, joins=1))

    assert any(line.startswith('Access') and 'elevated' in line for line in text)
    assert any(line.startswith('Pending')
               and '2 deletion reviews' in line and '1 join request' in line
               for line in text)


def test_welcome_rows_without_project_or_role():
    text = rows_text(info(project=None, platform_role='none'))

    assert any(line.startswith('Project') and 'none' in line for line in text)
    user_line = next(line for line in text if line.startswith('User'))
    assert '·' not in user_line


def test_compose_puts_text_beside_the_logo_at_a_fixed_margin():
    logo = [[('', '#' * 4)] for _ in range(2)]
    text = [[('', f'line {n}')] for n in range(4)]

    rows = rows_text(shell_banner.compose_welcome(logo, text, columns=80))

    assert rows[0].startswith('  ') and 'line 0' in rows[0]
    assert rows[1].startswith('  ####')
    assert rows[1].index('line 1') == rows[2].index('line 2')
    assert all(vlen(plain(row)) <= 80 for row in shell_banner.compose_welcome(logo, text, 80))


def test_compose_truncates_long_values_to_the_terminal():
    logo = [[('', '#' * 4)]]
    text = [[('', 'x' * 200)]]

    rows = shell_banner.compose_welcome(logo, text, columns=60)

    assert vlen(plain(rows[0])) <= 60
    assert plain(rows[0]).rstrip().endswith('…')


def test_compose_stacks_on_narrow_terminals():
    logo = [[('', '#' * 16)]]
    text = [[('', 'hello')]]

    rows = rows_text(shell_banner.compose_welcome(logo, text, columns=40))

    assert rows[0].strip() == '#' * 16
    assert rows[-1].strip() == 'hello'


def test_compose_drops_the_logo_when_it_cannot_fit():
    logo = [[('', '#' * 16)]]
    text = [[('', 'hello')]]

    rows = rows_text(shell_banner.compose_welcome(logo, text, columns=12))

    assert rows == ['  hello']


@pytest.mark.parametrize('color', [True, False])
def test_print_welcome_renders_logo_and_text(monkeypatch, capsys, color):
    import prompt_toolkit

    monkeypatch.setattr(term, 'color_enabled', lambda: color)
    monkeypatch.setattr(prompt_toolkit, 'print_formatted_text', lambda text, **kw: print(
        ''.join(fragment[1] for fragment in text)))

    shell_banner.print_welcome(info(), columns=100)

    out = capsys.readouterr().out
    assert 'Crucible shell 3.3.0' in out
    assert 'https://crucible.lbl.gov/api/v3' in out


@pytest.mark.parametrize('user, expected', [
    ({'first_name': 'Ada', 'last_name': 'Lovelace', 'username': 'ada'}, 'Ada Lovelace (@ada)'),
    ({'first_name': 'Ada', 'last_name': 'Lovelace'}, 'Ada Lovelace'),
    ({'username': 'ingest-bot'}, '@ingest-bot'),
])
def test_shell_welcome_names_the_user_with_their_username(user, expected):
    from types import SimpleNamespace
    from crucible.cli.shell import core
    from crucible.models import AccountAuthorization

    shell = core.CrucibleShell.__new__(core.CrucibleShell)
    shell.state = {'user_label': 'fallback', 'project': None, 'elevated': False}
    shell.client = SimpleNamespace(authorization=AccountAuthorization(platform_role='admin'))

    text = rows_text(shell._welcome_rows({'user_info': user}))

    user_line = next(line for line in text if line.startswith('User'))
    assert user_line.split(None, 1)[1] == f'{expected} · admin'
