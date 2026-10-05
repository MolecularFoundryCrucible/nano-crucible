"""Unit coverage for the dataset and sample facets CLI commands."""

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest

from crucible.cli import dataset, sample


def make_parser(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    module.register_subcommand(subparsers)
    return parser


RESPONSE = {
    'field': 'measurement',
    'items': [{'value': 'xrd', 'label': 'XRD', 'count': 7}],
    'limit': 100,
    'next_cursor': None,
}


@pytest.fixture
def client():
    fake = MagicMock()
    fake.datasets.facets.return_value = RESPONSE
    fake.samples.facets.return_value = RESPONSE
    with patch('crucible.config.get_client', return_value=fake):
        yield fake


@pytest.mark.parametrize('module,name,field', [
    (dataset, 'dataset', 'measurement'),
    (sample, 'sample', 'sample_type'),
])
def test_field_is_forwarded_to_the_client(module, name, field, client, capsys):
    args = make_parser(module).parse_args([name, 'facets', field])

    args.func(args)

    operations = getattr(client, f'{name}s')
    assert operations.facets.call_args.args[0] == field
    assert 'XRD' in capsys.readouterr().out


def test_sort_direction_and_limit_are_forwarded(client):
    args = make_parser(dataset).parse_args([
        'dataset', 'facets', 'measurement',
        '--sort', 'count', '--direction', 'desc', '--limit', '5',
    ])

    args.func(args)

    kwargs = client.datasets.facets.call_args.kwargs
    assert kwargs['sort'] == 'count'
    assert kwargs['direction'] == 'desc'
    assert kwargs['limit'] == 5


def test_mine_maps_to_the_owner_affiliation(client):
    args = make_parser(dataset).parse_args(
        ['dataset', 'facets', 'measurement', '--mine'])

    args.func(args)

    assert client.datasets.facets.call_args.kwargs['affiliation'] == 'owner'


def test_project_filter_is_forwarded(client):
    args = make_parser(sample).parse_args(
        ['sample', 'facets', 'sample_type', '--project-id', 'demo'])

    args.func(args)

    assert client.samples.facets.call_args.kwargs['project_id'] == 'demo'


def test_json_output_is_the_raw_response(client, capsys):
    args = make_parser(dataset).parse_args(
        ['dataset', 'facets', 'measurement', '--json'])

    args.func(args)

    assert json.loads(capsys.readouterr().out) == RESPONSE


def test_empty_results_report_no_matches(client, capsys):
    client.datasets.facets.return_value = {'field': 'measurement', 'items': [],
                                           'limit': 100, 'next_cursor': None}
    args = make_parser(dataset).parse_args(['dataset', 'facets', 'measurement'])

    args.func(args)

    assert 'No datasets matched' in capsys.readouterr().out


def test_more_values_hint_is_shown_when_a_cursor_remains(client, capsys):
    client.datasets.facets.return_value = {**RESPONSE, 'next_cursor': 'token'}
    args = make_parser(dataset).parse_args(['dataset', 'facets', 'measurement'])

    args.func(args)

    assert 'More values available' in capsys.readouterr().out


def test_null_bucket_is_labelled(client, capsys):
    client.datasets.facets.return_value = {
        **RESPONSE,
        'items': [{'value': None, 'label': None, 'count': 4}],
    }
    args = make_parser(dataset).parse_args(['dataset', 'facets', 'measurement'])

    args.func(args)

    assert '(none)' in capsys.readouterr().out


@pytest.mark.parametrize('module,name,field', [
    (dataset, 'dataset', 'sample_type'),
    (sample, 'sample', 'instrument'),
])
def test_field_not_valid_for_the_resource_is_rejected(module, name, field):
    with pytest.raises(SystemExit):
        make_parser(module).parse_args([name, 'facets', field])
