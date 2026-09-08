"""Unit coverage for dataset CLI fields and filters."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

from crucible.cli import dataset as dataset_cli
from crucible.cli.dataset import _dataset_updatable_fields


def test_dataset_cli_excludes_frozen_instrument_assignment():
    fields = _dataset_updatable_fields()

    assert "data_format" in fields
    assert "instrument_id" not in fields
    assert "instrument_name" not in fields


def test_dataset_list_parser_accepts_instrument_mfid():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    dataset_cli._register_list(subparsers)

    args = parser.parse_args([
        'list',
        '--instrument-mfid',
        '0tkn2knjast3h0008nyq9zps2c',
    ])

    assert args.instrument_mfid == '0tkn2knjast3h0008nyq9zps2c'


def test_dataset_list_instrument_filter_ignores_configured_project(monkeypatch, capsys):
    datasets = SimpleNamespace(list=MagicMock(return_value=[]))
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: SimpleNamespace(datasets=datasets),
    )
    monkeypatch.setattr(
        'crucible.config.config._data',
        {'current_project': 'configured-project'},
    )
    args = SimpleNamespace(
        project_id=None,
        instrument_mfid='0tkn2knjast3h0008nyq9zps2c',
        measurement=None,
        keyword=None,
        session=None,
        data_format=None,
        data_type=None,
        instrument_name=None,
        limit=10,
        include=None,
        exclude=None,
        json=False,
        group_by=None,
        debug=False,
    )

    dataset_cli._execute_list(args)

    datasets.list.assert_called_once_with(
        limit=10,
        instrument_mfid='0tkn2knjast3h0008nyq9zps2c',
    )
    assert 'instrument 0tkn2knjast3h0008nyq9zps2c' in capsys.readouterr().out


def test_dataset_list_uses_shell_project_before_config(monkeypatch, capsys):
    datasets = SimpleNamespace(list=MagicMock(return_value=[]))
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: SimpleNamespace(datasets=datasets),
    )
    monkeypatch.setattr(
        'crucible.config.config._data',
        {'current_project': 'configured-project'},
    )
    args = SimpleNamespace(
        project_id=None,
        instrument_mfid=None,
        measurement=None,
        keyword=None,
        session=None,
        data_format=None,
        data_type=None,
        instrument_name=None,
        limit=10,
        include=None,
        exclude=None,
        json=False,
        group_by=None,
        debug=False,
        _shell_state={
            'project': 'shell-project',
            'project_source': 'config file',
        },
    )

    dataset_cli._execute_list(args)

    datasets.list.assert_called_once_with(project_id='shell-project', limit=10)
    assert 'Datasets · shell-project' in capsys.readouterr().out
