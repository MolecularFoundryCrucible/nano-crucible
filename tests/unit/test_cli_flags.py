"""Unit coverage for canonical CLI flags and compatibility aliases."""

import argparse
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset, file as file_cli, project, sample, upload
from crucible.parsers import BaseParser


def make_parser(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    module.register_subcommand(subparsers)
    return parser


@pytest.mark.parametrize('flag', ['--project-id', '-p'])
def test_dataset_search_accepts_canonical_project_flags(flag):
    args = make_parser(dataset).parse_args([
        'dataset', 'search', 'query', flag, 'project-one',
    ])

    assert args.project_id == 'project-one'


@pytest.mark.parametrize('flag', ['--project', '-pid'])
def test_dataset_search_warns_for_legacy_project_flags(flag, capsys):
    args = make_parser(dataset).parse_args([
        'dataset', 'search', 'query', flag, 'project-one',
    ])

    assert args.project_id == 'project-one'
    assert (
        f'Warning: {flag} is deprecated; use --project-id instead.'
        in capsys.readouterr().err
    )


def test_sample_create_uses_canonical_type_flag():
    args = make_parser(sample).parse_args([
        'sample', 'create', '--type', 'substrate',
    ])

    assert args.sample_type == 'substrate'


def test_sample_create_warns_for_legacy_type_flag(capsys):
    args = make_parser(sample).parse_args([
        'sample', 'create', '--sample-type', 'substrate',
    ])

    assert args.sample_type == 'substrate'
    assert (
        'Warning: --sample-type is deprecated; use --type instead.'
        in capsys.readouterr().err
    )


def test_project_create_uses_canonical_short_flag():
    args = make_parser(project).parse_args([
        'project', 'create', '-i', 'project-one',
    ])

    assert args.project_id == 'project-one'


def test_project_create_warns_for_legacy_short_flag(capsys):
    args = make_parser(project).parse_args([
        'project', 'create', '-id', 'project-one',
    ])

    assert args.project_id == 'project-one'
    assert (
        'Warning: -id is deprecated; use --project-id instead.'
        in capsys.readouterr().err
    )


def test_legacy_upload_project_flag_remains_compatible(capsys):
    args = make_parser(upload).parse_args([
        'upload', '-i', 'data.csv', '-pid', 'project-one',
    ])

    assert args.project_id == 'project-one'
    assert (
        'Warning: -pid is deprecated; use --project-id instead.'
        in capsys.readouterr().err
    )


def test_dataset_create_accepts_no_input():
    args = make_parser(dataset).parse_args([
        'dataset', 'create', '--project-id', 'project-one', '--name', 'Planned experiment',
    ])

    assert args.input is None


def test_dataset_create_accepts_typed_project_and_instrument_selectors():
    args = make_parser(dataset).parse_args([
        'dataset', 'create',
        '--project-id', 'project-one',
        '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
        '--instrument-id', 'xrd-one',
        '--instrument-mfid', '0tk8pf1me0h3h0003fp91vr037',
    ])

    assert args.project_id == 'project-one'
    assert args.project_mfid == '0tkn2knjast3h0008nyq9zps2c'
    assert args.instrument_id == 'xrd-one'
    assert args.instrument_mfid == '0tk8pf1me0h3h0003fp91vr037'


def test_sample_create_accepts_matching_project_selectors():
    args = make_parser(sample).parse_args([
        'sample', 'create',
        '--project-id', 'project-one',
        '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
    ])

    assert args.project_id == 'project-one'
    assert args.project_mfid == '0tkn2knjast3h0008nyq9zps2c'


@pytest.mark.parametrize('module', [dataset, sample])
def test_resource_list_accepts_project_mfid_and_scope(module):
    args = make_parser(module).parse_args([
        module.__name__.rsplit('.', 1)[-1], 'list',
        '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
        '--project-scope', 'shared',
    ])

    assert args.project_mfid == '0tkn2knjast3h0008nyq9zps2c'
    assert args.project_scope == 'shared'


@pytest.mark.parametrize('module', [dataset, sample])
def test_resource_list_rejects_conflicting_project_selectors(module):
    with pytest.raises(SystemExit):
        make_parser(module).parse_args([
            module.__name__.rsplit('.', 1)[-1], 'list',
            '--project-id', 'project-one',
            '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
        ])


@pytest.mark.parametrize('flag', ['--yes', '-y'])
def test_file_delete_accepts_confirmation_flag(flag):
    args = make_parser(file_cli).parse_args([
        'file', 'delete', '0tf7evvtg5wb90005k1j97ak94', flag,
    ])

    assert args.yes is True


@pytest.mark.parametrize(
    'option',
    [
        ['--type', 'lammps'],
        ['--ingestor', 'ExampleIngestor'],
        ['--no-upload'],
        ['--backend', 'globus'],
        ['--access-note', 'Shared path'],
    ],
)
def test_dataset_create_rejects_file_options_without_input(option, caplog):
    args = make_parser(dataset).parse_args([
        'dataset', 'create', '--project-id', 'project-one', *option,
    ])

    with pytest.raises(SystemExit) as exit_info:
        args.func(args)

    assert exit_info.value.code == 1
    assert 'require --input FILE' in caplog.text


def test_dataset_create_without_files_uses_direct_client(monkeypatch):
    client = MagicMock()
    client.projects.get.return_value = {'project_id': 'project-one'}
    client.datasets.create.return_value = {'created_record': {}}
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    args = make_parser(dataset).parse_args([
        'dataset', 'create', '--project-id', 'project-one', '--name', 'Planned experiment',
        '--metadata', '{"temperature": 300}', '--keywords', 'planned,draft',
    ])

    args.func(args)

    created_dataset = client.datasets.create.call_args.args[0]
    assert created_dataset.dataset_name == 'Planned experiment'
    assert created_dataset.project_id == 'project-one'
    client.datasets.create.assert_called_once_with(
        created_dataset,
        scientific_metadata={'temperature': 300},
        keywords=['planned', 'draft'],
        files=[],
    )


def test_dataset_create_with_mfids_does_not_apply_project_default(monkeypatch):
    client = MagicMock()
    client.datasets.create.return_value = {'created_record': {}}
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    args = make_parser(dataset).parse_args([
        'dataset', 'create', '--name', 'Planned experiment',
        '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
        '--instrument-mfid', '0tk8pf1me0h3h0003fp91vr037',
    ])

    args.func(args)

    created_dataset = client.datasets.create.call_args.args[0]
    assert created_dataset.project_id is None
    assert created_dataset.project_mfid == '0tkn2knjast3h0008nyq9zps2c'
    assert created_dataset.instrument_mfid == '0tk8pf1me0h3h0003fp91vr037'


def test_parser_preserves_creation_selectors():
    parsed = BaseParser(
        project_id='project-one',
        project_mfid='0tkn2knjast3h0008nyq9zps2c',
        instrument_id='xrd-one',
        instrument_mfid='0tk8pf1me0h3h0003fp91vr037',
    ).to_dataset()

    assert parsed.project_id == 'project-one'
    assert parsed.project_mfid == '0tkn2knjast3h0008nyq9zps2c'
    assert parsed.instrument_id == 'xrd-one'
    assert parsed.instrument_mfid == '0tk8pf1me0h3h0003fp91vr037'


def test_parser_new_selectors_preserve_legacy_positional_arguments():
    parsed = BaseParser([], 'project-one', '0000-0001-6402-3752')

    assert parsed.project_id == 'project-one'
    assert parsed.owner_orcid == '0000-0001-6402-3752'


def test_sample_create_with_project_mfid_does_not_apply_project_default(monkeypatch):
    client = MagicMock()
    client.samples.create.return_value = {
        'unique_id': '0td7evvtg5wb90005k1j97ak94',
        'sample_name': 'Sample',
    }
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(sample, '_show_sample', MagicMock())
    args = make_parser(sample).parse_args([
        'sample', 'create', '--name', 'Sample',
        '--project-mfid', '0tkn2knjast3h0008nyq9zps2c',
    ])

    args.func(args)

    created_sample = client.samples.create.call_args.args[0]
    assert created_sample.project_id is None
    assert created_sample.project_mfid == '0tkn2knjast3h0008nyq9zps2c'


def test_dataset_add_thumbnail_dispatches_local_image(monkeypatch, tmp_path, capsys):
    image_path = tmp_path / 'preview.png'
    image_path.write_bytes(b'png bytes')
    client = MagicMock()
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    args = make_parser(dataset).parse_args([
        'dataset', 'add-thumbnail',
        '0tkn2knjast3h0008nyq9zps2c', str(image_path),
        '--name', 'overview.png',
    ])

    args.func(args)

    client.datasets.add_thumbnail.assert_called_once_with(
        '0tkn2knjast3h0008nyq9zps2c',
        str(image_path),
        thumbnail_name='overview.png',
    )
    assert 'Added thumbnail overview.png' in capsys.readouterr().out


@pytest.mark.parametrize(
    ('module', 'command', 'visible', 'hidden'),
    [
        (dataset, ['dataset', 'search'], '--project-id ID, -p ID', '--project ID'),
        (sample, ['sample', 'create'], '--type TYPE, -t TYPE', '--sample-type TYPE'),
        (project, ['project', 'create'], '--project-id ID, -i ID', ', -id ID'),
    ],
)
def test_help_hides_legacy_flags(module, command, visible, hidden, capsys):
    with pytest.raises(SystemExit) as exit_info:
        make_parser(module).parse_args(command + ['--help'])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert visible in output
    assert hidden not in output
