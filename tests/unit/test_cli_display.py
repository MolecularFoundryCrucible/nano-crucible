"""Unit coverage for shared CLI resource presentation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import access_group as access_group_cli
from crucible.cli import dataset as dataset_cli
from crucible.cli import deletion as deletion_cli
from crucible.cli import helpers
from crucible.cli import instrument as instrument_cli
from crucible.cli import get as get_cli
from crucible.cli import open as open_cli
from crucible.cli import project as project_cli
from crucible.cli import sample as sample_cli
from crucible.cli import service_account as service_account_cli
from crucible.cli import shell as shell_cli
from crucible.cli import term
from crucible.cli import user as user_cli


MFID = '0tkn2knjast3h0008nyq9zps2c'


@pytest.mark.parametrize(('execute', 'args', 'expected'), [
    (
        project_cli._execute_list_join_requests,
        SimpleNamespace(project_id='project-slug', status=None, limit=100),
        'No join requests found.',
    ),
    (
        access_group_cli._execute_list,
        SimpleNamespace(status='pending', group_name=None, requester_id=None, limit=100),
        'No join requests found.',
    ),
    (
        access_group_cli._execute_mine,
        SimpleNamespace(status='pending', limit=100),
        'No join requests found.',
    ),
    (
        service_account_cli._execute_list,
        SimpleNamespace(limit=100, json=False),
        'No service accounts found.',
    ),
    (
        deletion_cli._execute_list_deleted,
        SimpleNamespace(resource_id=None, requester_id=None, reviewer_id=None, limit=100),
        'No deleted resources found.',
    ),
])
def test_empty_listings_name_their_subject(execute, args, expected, monkeypatch, capsys):
    client = SimpleNamespace(
        projects=SimpleNamespace(list_join_requests=lambda *args, **kwargs: []),
        access_groups=SimpleNamespace(list_join_requests=lambda **kwargs: []),
        account=SimpleNamespace(join_requests=lambda **kwargs: []),
        service_accounts=SimpleNamespace(list=lambda **kwargs: []),
        deletions=SimpleNamespace(list_deleted=lambda **kwargs: []),
    )
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    execute(args)

    output = capsys.readouterr().out
    assert expected in output
    assert 'None found.' not in output
    assert 'No records found.' not in output


@pytest.mark.parametrize(('value', 'expected'), [
    (True, 'yes'),
    (False, 'no'),
    (None, '-'),
])
def test_nullable_boolean_formatting(value, expected):
    assert term.fmt_bool(value) == expected


def test_success_message_uses_text_and_respects_json(monkeypatch, capsys):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    term.success('Project created')
    term.success('Hidden', SimpleNamespace(json=True))

    output = capsys.readouterr().out
    assert '\033[32mSuccess:\033[0m Project created' in output
    assert 'Hidden' not in output


@pytest.mark.parametrize(('status', 'expected'), [
    ('success', 'OK'),
    ('warning', 'WARNING'),
    ('error', 'ERROR'),
    ('info', 'INFO'),
])
def test_status_markers_use_words_when_redirected(status, expected, monkeypatch):
    monkeypatch.setattr(term, '_interactive', lambda stream=None: False)

    assert term.status_marker(status) == expected


def test_status_markers_use_symbols_in_interactive_output(monkeypatch):
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)

    assert term.status_marker('success') == '✓'
    assert term.status_marker('error') == '×'


def test_project_members_sort_by_role_then_name():
    members = [
        {'username': 'zoe', 'first_name': 'Zoe', 'role': 'viewer'},
        {'username': 'amy', 'first_name': 'Amy', 'role': 'editor'},
        {'username': 'ben', 'first_name': 'Ben', 'role': 'admin'},
        {'username': 'ann', 'first_name': 'Ann', 'role': 'admin'},
        {'username': 'lee', 'first_name': 'Lee', 'role': 'owner'},
        {'username': 'cal', 'first_name': 'Cal', 'role': 'contributor'},
    ]

    ordered = helpers.sort_members(members)

    assert [(member['role'], member['username']) for member in ordered] == [
        ('owner', 'lee'),
        ('admin', 'ann'),
        ('admin', 'ben'),
        ('editor', 'amy'),
        ('contributor', 'cal'),
        ('viewer', 'zoe'),
    ]


@pytest.mark.parametrize(('role', 'code'), [
    ('owner', '38;5;220'),
    ('admin', '35'),
    ('editor', '34'),
    ('contributor', None),
    ('viewer', '90'),
])
def test_project_role_labels_follow_semantic_palette(role, code, monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    display_role = 'lead' if role == 'owner' else role
    expected = f'\033[{code}m{display_role}\033[0m' if code else display_role
    assert term.role_label(role) == expected


def test_acl_owner_permission_keeps_canonical_label(monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    assert term.permission_label('owner') == '\033[38;5;220mowner\033[0m'


def test_project_role_labels_remain_plain_when_redirected(monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: False)

    assert term.role_label('admin') == 'admin'


def test_person_names_use_all_given_name_initials():
    assert term.fmt_name({
        'first_name': 'Jean Pierre',
        'last_name': 'Dupont',
    }) == 'J. P. Dupont'


def test_orcid_user_ids_link_to_explorer(monkeypatch):
    from crucible.config import config

    orcid = '0000-0001-6402-3752'
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')

    rendered = term.user_id_link(orcid)

    assert f'https://example.org/explore/user/{orcid}' in rendered
    assert 'orcid.org' not in rendered
    assert '\033[36m' in rendered
    assert '\033[4m' in rendered


def test_navigation_and_identifier_styles_distinguish_clickability(monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)

    linked = term.navigation_link('Project One', 'https://example.org/project')
    identifier = term.identifier_link('project-one')

    assert '\033[36m' in linked
    assert '\033[4m' in linked
    assert '\033]8;;https://example.org/project\007' in linked
    assert identifier == '\033[36mproject-one\033[0m'


def test_dataset_file_labels_reserve_cyan_for_download_links(monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)

    remote = dataset_cli._format_file_label({
        'name': 'remote.dat',
        'backend': 'globus',
        'ingested': True,
        'url': None,
    })
    downloadable = dataset_cli._format_file_label({
        'name': 'result.dat',
        'backend': 'gcs',
        'ingested': True,
        'url': 'https://example.org/download',
    })

    assert '\033[36m' not in remote
    assert '\033[2m(globus)\033[0m' in remote
    assert '\033[36m' in downloadable
    assert '\033[4m' in downloadable


def test_hyphenated_given_names_preserve_each_initial():
    assert term.fmt_name({
        'first_name': 'Jean-Pierre',
        'last_name': 'Dupont',
    }) == 'J.-P. Dupont'


def test_shell_toolbar_restores_context_symbols(monkeypatch):
    from prompt_toolkit.formatted_text import fragment_list_to_text, to_formatted_text

    shell = shell_cli.CrucibleShell.__new__(shell_cli.CrucibleShell)
    shell.state = {
        'project': 'example-project',
        'session': 'deprecated-session',
        'user_label': 'Test User',
        'api_label': 'api: testapi-staging',
        'api_attention': True,
        'debug': False,
    }
    app = SimpleNamespace(output=SimpleNamespace(
        get_size=lambda: SimpleNamespace(columns=100)))
    monkeypatch.setattr('prompt_toolkit.application.get_app', lambda: app)

    rendered = fragment_list_to_text(to_formatted_text(shell._toolbar()))

    assert '🔬 example-project' in rendered
    assert '🧸 Test User' in rendered
    assert '🔗 api: testapi-staging' in rendered
    assert rendered.count('│') == 3
    assert 'deprecated-session' not in rendered


def test_shell_toolbar_uses_brand_palette_without_completion_styles(monkeypatch):
    monkeypatch.setattr(term, '_COLOR_ENABLED', True)

    rules = shell_cli._shell_style_rules()

    assert rules['bottom-toolbar'] == 'noinherit bg:#031e2d fg:#a8c4cd'
    assert rules['tb-project'] == 'noinherit bg:#a8c4cd fg:#031e2d'
    assert rules['tb-separator'] == 'noinherit bg:#031e2d fg:#ff6600'
    assert rules['tb-api-attention'] == 'noinherit bg:#031e2d fg:#ff6600 bold'
    assert rules['tb-debug'] == 'noinherit bg:#ff6600 fg:#031e2d bold'
    assert not any(name.startswith('completion-menu') for name in rules)


def test_shell_uses_true_color_when_terminal_advertises_it(monkeypatch):
    from prompt_toolkit.output import ColorDepth

    monkeypatch.setattr(term, '_COLOR_ENABLED', True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.delenv('PROMPT_TOOLKIT_COLOR_DEPTH', raising=False)
    monkeypatch.setenv('COLORTERM', 'truecolor')

    assert shell_cli._shell_color_depth() == ColorDepth.DEPTH_24_BIT


def test_shell_respects_explicit_prompt_toolkit_color_depth(monkeypatch):
    from prompt_toolkit.output import ColorDepth

    monkeypatch.setattr(term, '_COLOR_ENABLED', True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.setenv('PROMPT_TOOLKIT_COLOR_DEPTH', 'DEPTH_8_BIT')
    monkeypatch.setenv('COLORTERM', 'truecolor')

    assert shell_cli._shell_color_depth() == ColorDepth.DEPTH_8_BIT


def test_shell_leaves_color_depth_automatic_without_true_color(monkeypatch):
    monkeypatch.setattr(term, '_COLOR_ENABLED', True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.delenv('PROMPT_TOOLKIT_COLOR_DEPTH', raising=False)
    monkeypatch.delenv('COLORTERM', raising=False)

    assert shell_cli._shell_color_depth() is None


def test_shell_banner_is_packaged_and_uses_requested_colors():
    banner = shell_cli._load_shell_banner()
    fragments = shell_cli._shell_banner_fragments('_%=.\n.=_%')
    styles = {style for style, _text in fragments}

    assert len(banner.splitlines()) == 16
    assert {len(line) for line in banner.splitlines()} == {16}
    assert any('#a8c4cd' in style for style in styles)
    assert any('#031e2d' in style for style in styles)
    assert any('#ff6600' in style for style in styles)
    assert any('#eeeeee' in style for style in styles)
    assert all('#ffffff' not in style for style in styles)
    assert any(text == '▀' for _style, text in fragments)


def test_shell_banner_contains_its_own_boundary():
    banner = shell_cli._load_shell_banner()
    rows = shell_cli._shell_banner_rows(banner)
    panel = shell_cli._shell_banner_panel(banner)

    assert len(rows) == 16
    assert {len(row) for row in rows} == {16}
    assert len(panel.splitlines()) == 8
    assert {shell_cli._vlen(line) for line in panel.splitlines()} == {16}
    assert set(rows[0]) == {'_'}
    assert set(rows[-1]) == {'_'}


def test_shell_banner_panel_has_consistent_width():
    panel = shell_cli._shell_banner_panel('%%\n%')

    lines = panel.splitlines()
    assert lines == ['█▀']
    assert {shell_cli._vlen(line) for line in lines} == {2}


def test_shell_banner_panel_has_requested_edge_padding():
    rows = shell_cli._shell_banner_rows(shell_cli._load_shell_banner())

    assert set(rows[0]) == {'_'}
    assert set(rows[-1]) == {'_'}
    assert all(row.startswith('_') for row in rows)
    assert all(row.endswith('_') for row in rows)


def test_shell_banner_is_centered_by_display_width():
    panel = shell_cli._shell_banner_panel('%%')

    assert shell_cli._shell_banner_left_margin(panel, 14) == 6
    assert shell_cli._shell_banner_left_margin(panel, 7) == 2


def test_shell_banner_centering_keeps_outer_margin_uncolored():
    fragments = list(shell_cli._shell_banner_fragments('%%', left_margin=3))

    assert fragments[0] == ('', '   ')
    assert '#a8c4cd' in fragments[1][0]


def test_shell_banner_pixel_material_counts_match_source_pattern():
    banner = shell_cli._load_shell_banner()

    assert banner.count('%') == 127
    assert banner.count('=') == 18
    assert banner.count('.') == 9
    assert banner.count('_') == 102


def test_shell_banner_is_skipped_on_narrow_terminals(monkeypatch):
    monkeypatch.setattr(
        shell_cli,
        '_load_shell_banner',
        lambda: pytest.fail('Narrow terminals should not load the banner.'),
    )

    assert shell_cli._print_shell_banner(15) is False


def test_shell_toolbar_marks_custom_api_and_debug(monkeypatch):
    from prompt_toolkit.formatted_text import to_formatted_text

    monkeypatch.setattr(term, '_COLOR_ENABLED', True)
    shell = shell_cli.CrucibleShell.__new__(shell_cli.CrucibleShell)
    shell.state = {
        'project': 'example-project',
        'user_label': 'Test User',
        'api_label': 'api: testapi-staging',
        'api_attention': True,
        'debug': True,
    }
    app = SimpleNamespace(output=SimpleNamespace(
        get_size=lambda: SimpleNamespace(columns=100)))
    monkeypatch.setattr('prompt_toolkit.application.get_app', lambda: app)

    fragments = to_formatted_text(shell._toolbar())

    assert ('class:tb-api-attention', ' 🔗 api: testapi-staging ') in fragments
    assert ('class:tb-debug', ' DEBUG ') in fragments
    assert sum(text.count('│') for _, text in fragments) == 4


def test_shell_api_attention_is_reserved_for_nondefault_endpoints(monkeypatch):
    from crucible.config import config
    from crucible.config.config import Config

    monkeypatch.setattr(config, '_data', {'api_url': Config.DEFAULT_API_URL})
    assert helpers.fetch_api_attention() is False

    monkeypatch.setattr(config, '_data', {
        'api_url': 'https://crucible.lbl.gov/testapi-staging',
    })
    assert helpers.fetch_api_attention() is True


def test_project_context_precedence(monkeypatch):
    from crucible.config import config

    monkeypatch.setattr(config, '_data', {'current_project': 'configured-project'})
    monkeypatch.setattr(config, '_sources', {'current_project': 'config file'})
    args = SimpleNamespace(_shell_state={
        'project': 'shell-project',
        'project_source': 'config file',
    })

    assert helpers.resolve_project_context(args, 'argument-project') == (
        'argument-project', 'argument')
    assert helpers.resolve_project_context(args) == ('shell-project', 'config file')
    assert helpers.resolve_project_context() == ('configured-project', 'config file')


def test_environment_project_context_warns(monkeypatch):
    from crucible.config import config

    monkeypatch.setattr(config, '_data', {'current_project': 'environment-project'})
    monkeypatch.setattr(config, '_sources', {'current_project': 'environment'})

    with pytest.warns(FutureWarning, match='CRUCIBLE_CURRENT_PROJECT'):
        assert helpers.resolve_project_context() == (
            'environment-project', 'environment')


def test_shell_use_remembers_and_unuse_clears_project(
        monkeypatch, capsys):
    set_value = MagicMock()
    unset_value = MagicMock()
    monkeypatch.delenv('CRUCIBLE_CURRENT_PROJECT', raising=False)
    monkeypatch.setattr('crucible.cli.config.set_config_value', set_value)
    monkeypatch.setattr('crucible.cli.config.unset_config_value', unset_value)
    shell = shell_cli.CrucibleShell.__new__(shell_cli.CrucibleShell)
    shell.client = SimpleNamespace(projects=SimpleNamespace(get=MagicMock(return_value={
        'project_id': 'shell-project',
        'title': 'Shell Project',
    })))
    shell.state = {
        'project': 'configured-project',
        'project_source': 'config file',
    }

    assert shell._dispatch('use shell-project') is True
    assert shell.state['project'] == 'shell-project'
    assert shell.state['project_source'] == 'config file'
    set_value.assert_called_once_with('current_project', 'shell-project')

    assert shell._dispatch('unuse') is True
    assert shell.state['project'] is None
    assert shell.state['project_source'] is None
    unset_value.assert_called_once_with('current_project')
    output = capsys.readouterr().out
    assert 'Using project: shell-project - Shell Project (remembered)' in output
    assert 'Cleared current project.' in output


def test_shell_project_selection_is_blocked_by_environment(monkeypatch, capsys):
    monkeypatch.setenv('CRUCIBLE_CURRENT_PROJECT', 'environment-project')
    set_value = MagicMock()
    monkeypatch.setattr('crucible.cli.config.set_config_value', set_value)
    shell = shell_cli.CrucibleShell.__new__(shell_cli.CrucibleShell)
    shell.client = SimpleNamespace(projects=SimpleNamespace(get=MagicMock()))
    shell.state = {
        'project': 'environment-project',
        'project_source': 'environment',
    }

    assert shell._dispatch('use another-project') is True

    shell.client.projects.get.assert_not_called()
    set_value.assert_not_called()
    assert 'CRUCIBLE_CURRENT_PROJECT controls the current project' in capsys.readouterr().err


def test_shell_html_removes_styles_when_color_is_disabled(monkeypatch):
    from prompt_toolkit.formatted_text import to_formatted_text

    monkeypatch.setattr(term, '_COLOR_ENABLED', False)

    fragments = to_formatted_text(
        shell_cli._shell_html('<ansicyan><b>project-one</b></ansicyan>'))

    assert fragments == [('', 'project-one')]


def test_shell_toolbar_style_is_monochrome_when_color_is_disabled(monkeypatch):
    monkeypatch.setattr(term, '_COLOR_ENABLED', False)

    rules = shell_cli._shell_style_rules()

    assert set(rules.values()) == {'noinherit'}


def test_project_detail_distinguishes_slug_and_mfid_and_shows_empty_members(capsys):
    project_cli._show_project({
        'unique_id': MFID,
        'project_id': 'project-slug',
        'title': 'Project',
        'organization': 'LBNL',
        'status': 'active',
        'creation_time': '2026-09-01T12:00:00+00:00',
        'modification_time': '2026-09-01T13:00:00+00:00',
        'members': [],
    }, include_members=True)

    output = capsys.readouterr().out
    assert 'Project ID' in output
    assert 'project-slug' in output
    assert 'MFID' in output
    assert MFID in output
    assert 'Created' in output
    assert 'Modified' in output
    assert 'Members (0)' in output
    assert 'No members found.' in output


def test_project_detail_links_only_canonical_mfid(monkeypatch, capsys):
    from crucible.config import config

    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')

    project_cli._show_project({
        'unique_id': MFID,
        'project_id': 'project-slug',
        'title': 'Project Title',
    })

    output = capsys.readouterr().out
    assert output.count('https://example.org/explore/project-slug/') == 1
    assert '\033[1mProject Title\033[0m' in output


def test_project_detail_sorts_and_colors_member_roles(monkeypatch, capsys):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    project_cli._show_project({
        'unique_id': MFID,
        'project_id': 'project-slug',
        'members': [
            {'username': 'viewer-user', 'first_name': 'Viewer', 'role': 'viewer'},
            {'username': 'lead-user', 'first_name': 'Lead', 'role': 'owner'},
            {'username': 'admin-user', 'first_name': 'Admin', 'role': 'admin'},
        ],
    }, include_members=True)

    output = capsys.readouterr().out
    assert output.index('lead-user') < output.index('admin-user') < output.index('viewer-user')
    assert '\033[38;5;220mlead\033[0m' in output
    assert '\033[35madmin\033[0m' in output
    assert '\033[90mviewer\033[0m' in output


def test_instrument_detail_distinguishes_slug_and_mfid(capsys):
    instrument_cli._show_instrument({
        'unique_id': MFID,
        'instrument_id': 'instrument-slug',
        'instrument_name': 'Instrument',
        'status': 'maintenance',
    })

    output = capsys.readouterr().out
    assert 'Instrument ID' in output
    assert 'instrument-slug' in output
    assert 'MFID' in output
    assert MFID in output
    assert 'maintenance' in output


def test_instrument_detail_links_only_canonical_mfid(monkeypatch, capsys):
    from crucible.config import config

    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')

    instrument_cli._show_instrument({
        'unique_id': MFID,
        'instrument_id': 'instrument-slug',
        'instrument_name': 'Instrument Name',
    })

    output = capsys.readouterr().out
    assert output.count(f'https://example.org/explore/instrument/{MFID}') == 1
    assert '\033[1mInstrument Name\033[0m' in output


def test_user_detail_links_only_canonical_id(monkeypatch, capsys):
    from crucible.config import config

    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')

    user_cli._show_user({
        'unique_id': MFID,
        'username': 'user-slug',
        'first_name': 'Test',
        'last_name': 'User',
    })

    output = capsys.readouterr().out
    assert output.count(f'https://example.org/explore/user/{MFID}') == 1
    assert 'T. User' in output


@pytest.mark.parametrize(('show', 'record'), [
    (
        lambda record: dataset_cli._show_dataset(
            record,
            SimpleNamespace(),
            prefetched={'keywords': [], 'af_list': [], 'link_map': {}},
        ),
        {'unique_id': MFID, 'dataset_name': 'Dataset', 'public': None},
    ),
    (
        lambda record: sample_cli._show_sample(record, SimpleNamespace()),
        {'unique_id': MFID, 'sample_name': 'Sample', 'public': None},
    ),
])
def test_missing_public_value_is_not_rendered_as_false(show, record, capsys):
    show(record)

    public_line = next(
        line for line in capsys.readouterr().out.splitlines() if 'Public' in line)
    assert public_line.rstrip().endswith('-')


@pytest.mark.parametrize(
    ('module', 'namespace', 'resource_attr', 'record', 'type_label'),
    [
        (
            dataset_cli,
            {
                'measurement': None,
                'keyword': None,
                'session': None,
                'data_format': None,
                'data_type': None,
                'instrument_name': None,
                'instrument_mfid': None,
                'include': None,
                'exclude': None,
            },
            'datasets',
            {
                'unique_id': MFID,
                'dataset_name': 'Shared Dataset',
                'measurement': 'XRD',
                'project': None,
                'project_relation': 'shared',
            },
            'Measurement',
        ),
        (
            sample_cli,
            {
                'name': None,
                'sample_type': None,
                'include_metadata': False,
                'include': None,
                'exclude': None,
            },
            'samples',
            {
                'unique_id': MFID,
                'sample_name': 'Shared Sample',
                'sample_type': 'wafer',
                'project': None,
                'project_relation': 'shared',
            },
            'Type',
        ),
    ],
)
def test_scoped_resource_lists_show_relation_and_unassigned_project(
        module, namespace, resource_attr, record, type_label, monkeypatch, capsys):
    operation = SimpleNamespace(list=MagicMock(return_value=[record]))
    client = SimpleNamespace(**{resource_attr: operation})
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    args = SimpleNamespace(
        project_id=None,
        project_mfid=MFID,
        project_scope='all',
        limit=10,
        json=False,
        group_by='none',
        debug=False,
        **namespace,
    )

    module._execute_list(args)

    operation.list.assert_called_once_with(
        limit=10,
        project_mfid=MFID,
        project_scope='all',
        **({'include_metadata': False} if resource_attr == 'samples' else {}),
    )
    output = capsys.readouterr().out
    assert 'PROJECT' in output
    assert 'RELATION' in output
    assert 'shared' in output
    assert type_label.upper() in output


def test_dataset_detail_prefers_embedded_reference_labels(capsys):
    dataset_cli._show_dataset(
        {
            'unique_id': MFID,
            'dataset_name': 'Dataset',
            'instrument_name': 'Legacy Instrument',
            'project_id': 'legacy-project',
            'instrument': {
                'unique_id': MFID,
                'instrument_id': 'xrd-1',
                'instrument_name': 'Current Instrument',
            },
            'project': {
                'unique_id': MFID,
                'project_id': 'current-project',
                'title': 'Current Project',
            },
        },
        SimpleNamespace(),
        prefetched={'keywords': [], 'af_list': [], 'link_map': {}},
    )

    output = capsys.readouterr().out
    assert 'Current Instrument' in output
    assert 'Current Project' in output
    assert 'Legacy Instrument' not in output
    assert 'legacy-project' not in output
    assert output.count(MFID) == 1


def test_sample_detail_uses_embedded_project_reference(capsys):
    sample_cli._show_sample(
        {
            'unique_id': MFID,
            'sample_name': 'Sample',
            'project_id': 'legacy-project',
            'project': {
                'unique_id': '0td7evvtg5wb90005k1j97ak94',
                'project_id': 'current-project',
                'title': 'Current Project',
            },
        },
        SimpleNamespace(),
    )

    output = capsys.readouterr().out
    assert 'Current Project' in output
    assert 'current-project' in output
    assert 'legacy-project' not in output
    assert '0td7evvtg5wb90005k1j97ak94' not in output


def test_dataset_reference_fields_link_to_explorer(monkeypatch, capsys):
    from crucible.config import config

    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    instrument_mfid = '0td7evvtg5wb90005k1j97ak94'

    dataset_cli._show_dataset(
        {
            'unique_id': MFID,
            'dataset_name': 'Dataset',
            'project': {
                'unique_id': '0tp7evvtg5wb90005k1j97ak94',
                'project_id': 'project-one',
                'title': 'Project One',
            },
            'instrument': {
                'unique_id': instrument_mfid,
                'instrument_id': 'xrd-1',
                'instrument_name': 'XRD One',
            },
        },
        SimpleNamespace(),
        prefetched={'keywords': [], 'af_list': [], 'link_map': {}},
    )

    output = capsys.readouterr().out
    project_link = '\033]8;;https://example.org/explore/project-one/\007'
    instrument_link = f'\033]8;;https://example.org/explore/instrument/{instrument_mfid}\007'
    assert output.count(project_link) == 1
    assert output.count(instrument_link) == 1


def test_generic_get_dispatches_project_detail(monkeypatch):
    project = {
        'unique_id': MFID,
        'resource_type': 'project',
        'project_id': 'project-one',
    }
    client = SimpleNamespace(get=MagicMock(return_value=project))
    show_project = MagicMock()
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(project_cli, '_show_project', show_project)

    get_cli.execute(SimpleNamespace(
        resource_id=MFID,
        output=None,
        verbose=False,
        graph=True,
        include_metadata=False,
        qr=False,
        debug=False,
    ))

    show_project.assert_called_once_with(project, include_metadata=False)


@pytest.mark.parametrize(('resource', 'expected'), [
    (
        {
            'unique_id': MFID,
            'resource_type': 'project',
            'project_id': 'project-one',
        },
        'https://example.org/explore/project-one/',
    ),
    (
        {
            'unique_id': MFID,
            'resource_type': 'instrument',
            'instrument_id': 'xrd-one',
        },
        f'https://example.org/explore/instrument/{MFID}',
    ),
])
def test_open_uses_resource_specific_explorer_route(
        resource, expected, monkeypatch, capsys):
    from crucible.config import config

    client = SimpleNamespace(get=MagicMock(return_value=resource))
    monkeypatch.setattr(config, '_client', client)
    monkeypatch.setitem(
        config._data, 'graph_explorer_url', 'https://example.org/explore')

    open_cli.execute(SimpleNamespace(mfid=MFID, print_url=True))

    assert capsys.readouterr().out.strip() == expected


def test_dataset_detail_falls_back_to_flat_reference_fields(capsys):
    dataset_cli._show_dataset(
        {
            'unique_id': MFID,
            'dataset_name': 'Dataset',
            'instrument_name': 'Legacy Instrument',
            'project_id': 'legacy-project',
            'instrument': None,
            'project': None,
        },
        SimpleNamespace(),
        prefetched={'keywords': [], 'af_list': [], 'link_map': {}},
    )

    output = capsys.readouterr().out
    assert 'Legacy Instrument' in output
    assert 'legacy-project' in output


def test_table_fits_terminal_and_preserves_protected_identifiers(monkeypatch, capsys):
    slug = 'i' * 25
    monkeypatch.setattr(term, '_table_output_width', lambda: 80)

    term.table(
        [(
            'A long instrument display name',
            slug,
            MFID,
            'A long owner display name',
            'maintenance',
        )],
        ['Name', 'Instrument ID', 'MFID', 'Owner', 'Status'],
        max_widths=[24, 25, 26, 25, 12],
        min_widths=[4, 25, 26, 5, 6],
    )

    lines = capsys.readouterr().out.splitlines()
    assert all(term._dlen(line) <= 80 for line in lines)
    assert slug in lines[1]
    assert MFID in lines[1]


def test_instrument_search_displays_slug_instead_of_manufacturer(monkeypatch, capsys):
    results = [{
        'unique_id': MFID,
        'instrument_id': 'xrd-beamline',
        'instrument_name': 'XRD Instrument',
        'instrument_type': 'diffractometer',
        'manufacturer': 'Manufacturer omitted from search',
    }]
    operations = SimpleNamespace(search=MagicMock(return_value=results))
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: SimpleNamespace(instruments=operations),
    )

    instrument_cli._execute_search(SimpleNamespace(
        query='xrd',
        limit=20,
        status=None,
        json=False,
        debug=False,
    ))

    output = capsys.readouterr().out
    assert 'INSTRUMENT ID' in output
    assert 'xrd-beamline' in output
    assert 'Manufacturer omitted from search' not in output


def test_table_preserves_full_username_when_space_permits(monkeypatch, capsys):
    username = 'u' * 24
    monkeypatch.setattr(term, '_table_output_width', lambda: 80)

    term.table(
        [(username, 'A long user display name', MFID)],
        ['Username', 'Name', 'ID'],
        max_widths=[24, 25, 26],
        min_widths=[24, 4, 26],
    )

    lines = capsys.readouterr().out.splitlines()
    assert all(term._dlen(line) <= 80 for line in lines)
    assert username in lines[1]
    assert MFID in lines[1]


def test_table_truncates_protected_columns_only_when_required(monkeypatch, capsys):
    monkeypatch.setattr(term, '_table_output_width', lambda: 50)

    term.table(
        [('A long name', 'instrument-identifier-25', MFID, 'Owner', 'active')],
        ['Name', 'Instrument ID', 'MFID', 'Owner', 'Status'],
        max_widths=[24, 25, 26, 25, 12],
        min_widths=[4, 25, 26, 5, 6],
    )

    lines = capsys.readouterr().out.splitlines()
    assert all(term._dlen(line) <= 50 for line in lines)
    assert '…' in lines[1]


def test_table_without_minimums_remains_responsive(monkeypatch, capsys):
    monkeypatch.setattr(term, '_table_output_width', lambda: 30)

    term.table(
        [('A long descriptive value', 'Another long value')],
        ['First', 'Second'],
        max_widths=[30, 30],
    )

    assert all(
        term._dlen(line) <= 30
        for line in capsys.readouterr().out.splitlines()
    )


def test_table_preserves_hyperlink_sequences_when_truncating(monkeypatch, capsys):
    monkeypatch.setattr(term, '_table_output_width', lambda: 24)
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    url = 'https://example.org/resource'
    linked = term.navigation_link('a-very-long-resource-name', url, emphasized=True)

    term.table(
        [(linked, 'complete')],
        ['Resource', 'Status'],
        max_widths=[30, 10],
    )

    output = capsys.readouterr().out
    assert f'\033]8;;{url}\007' in output
    assert '\033]8;;\007' in output
    assert '\033[1m' in output
    assert '\033[36m' in output
    assert '\033[4m' in output
    assert all(term._dlen(line) <= 24 for line in output.splitlines())


def test_table_preserves_non_link_color_when_truncating(monkeypatch, capsys):
    monkeypatch.setattr(term, '_table_output_width', lambda: 12)
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    term.table(
        [(term.cyan('long-identifier'),)],
        ['MFID'],
        max_widths=[20],
    )

    output = capsys.readouterr().out
    assert '\033[36m' in output
    assert '…' in output


def test_redirected_table_width_is_deterministic(monkeypatch):
    monkeypatch.setattr(
        term.sys,
        'stdout',
        SimpleNamespace(isatty=lambda: False),
    )

    assert term._table_output_width() == 100


def test_interactive_table_width_uses_terminal_size(monkeypatch):
    monkeypatch.setattr(
        term.sys,
        'stdout',
        SimpleNamespace(isatty=lambda: True),
    )
    monkeypatch.setattr(
        term.shutil,
        'get_terminal_size',
        lambda fallback: SimpleNamespace(columns=72),
    )

    assert term._table_output_width() == 72
