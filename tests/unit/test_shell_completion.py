"""Unit coverage for interactive shell completion."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

from prompt_toolkit.document import Document

from crucible.cli import dataset, instrument, project, sample, user
from crucible.cli.shell import _CrucibleCompleter


MFID = '0tkn2knjast3h0008nyq9zps2c'


def make_completer(client=None, state=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    for module in (dataset, instrument, project, sample, user):
        module.register_subcommand(subparsers)
    return _CrucibleCompleter(
        parser,
        client=client,
        projects=[('cached-project', 'Cached Project')],
        state=state or {},
    )


def complete(completer, text):
    document = Document(text=text, cursor_position=len(text))
    return [item.text.strip() for item in completer.get_completions(document, None)]


def make_client():
    return SimpleNamespace(
        projects=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'project_id': 'project-one',
            'title': 'Project One',
        }])),
        instruments=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'instrument_id': 'xrd-one',
            'instrument_name': 'XRD One',
        }])),
        datasets=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': MFID,
            'dataset_name': 'Perovskite Dataset',
        }])),
        samples=SimpleNamespace(search=MagicMock(return_value=[])),
        users=SimpleNamespace(search=MagicMock(return_value=[{
            'unique_id': '0000-0001-6402-3752',
            'username': 'roncofaber',
            'first_name': 'Fabrice',
            'last_name': 'Roncoroni',
        }])),
    )


def test_flags_remain_available_after_project_positionals():
    completions = complete(make_completer(), 'project get project-one --i')

    assert '--include-members' in completions
    assert '--include-metadata' in completions


def test_flag_completion_hides_deprecated_aliases():
    completions = complete(make_completer(), 'sample create --')

    assert '--project-id' in completions
    assert '--type' in completions
    assert '--sample-type' not in completions
    assert '-pid' not in completions


def test_project_flag_values_use_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset search perovskite --project-id pro',
    )

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_project_mfid_flag_values_use_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'sample list --project-mfid pro',
    )

    assert MFID in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_project_positionals_use_project_search():
    client = make_client()

    completions = complete(make_completer(client), 'project get pro')

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_instrument_positionals_use_instrument_search():
    client = make_client()

    completions = complete(make_completer(client), 'instrument get xrd')

    assert 'xrd-one' in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_instrument_mfid_flags_use_instrument_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset list --instrument-mfid xrd',
    )

    assert MFID in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_dataset_create_instrument_id_uses_instrument_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'dataset create --instrument-id xrd',
    )

    assert 'xrd-one' in completions
    client.instruments.search.assert_called_once_with('xrd', limit=20)


def test_dataset_positionals_use_scoped_dataset_search():
    client = make_client()

    completions = complete(
        make_completer(client, state={'project': 'project-one'}),
        'dataset get per',
    )

    assert MFID in completions
    client.datasets.search.assert_called_once_with(
        'per', project_id='project-one')


def test_user_flags_use_user_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        'project add-user project-one --user ron',
    )

    assert 'roncofaber' in completions
    client.users.search.assert_called_once_with('ron')


def test_reassignment_target_uses_project_search():
    client = make_client()

    completions = complete(
        make_completer(client),
        f'dataset reassign-project {MFID} pro',
    )

    assert 'project-one' in completions
    client.projects.search.assert_called_once_with('pro', limit=20)


def test_parent_flag_uses_resource_search_not_project_search():
    client = make_client()

    completions = complete(
        make_completer(client, state={'project': 'project-one'}),
        'dataset link --parent per',
    )

    assert MFID in completions
    client.datasets.search.assert_called_once_with(
        'per', project_id='project-one')
    client.projects.search.assert_not_called()


def test_fixed_flag_choices_are_completed():
    completions = complete(
        make_completer(),
        'instrument search xrd --status m',
    )

    assert completions == ['maintenance']


def test_project_scope_choices_are_completed():
    completions = complete(
        make_completer(),
        'dataset list --project-scope s',
    )

    assert completions == ['shared']
