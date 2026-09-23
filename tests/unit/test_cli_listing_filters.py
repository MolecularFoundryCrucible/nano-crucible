"""Unit coverage for the shared CLI listing filters."""

import argparse

import pytest

from crucible.cli import dataset, sample
from crucible.cli.helpers import listing_filter_kwargs


def make_parser(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='resource')
    module.register_subcommand(subparsers)
    return parser


@pytest.mark.parametrize('module', [dataset, sample])
def test_defaults_produce_no_filter_keywords(module):
    args = make_parser(module).parse_args([module.__name__.split('.')[-1], 'list'])

    assert listing_filter_kwargs(args) == {}


@pytest.mark.parametrize('module', [dataset, sample])
def test_sort_and_direction_are_collected(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args(
        [name, 'list', '--sort', 'created', '--direction', 'asc'])

    assert listing_filter_kwargs(args) == {'sort': 'created', 'direction': 'asc'}


@pytest.mark.parametrize('module', [dataset, sample])
def test_mine_maps_to_the_owner_affiliation(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args([name, 'list', '--mine'])

    assert listing_filter_kwargs(args) == {'affiliation': 'owner'}


@pytest.mark.parametrize('module', [dataset, sample])
def test_time_bounds_are_collected(module):
    name = module.__name__.split('.')[-1]
    args = make_parser(module).parse_args([
        name, 'list', '--created-after', '2026-01-01',
        '--modified-before', '2026-06-01',
    ])

    assert listing_filter_kwargs(args) == {
        'creation_time_gte': '2026-01-01',
        'modification_time_lte': '2026-06-01',
    }


@pytest.mark.parametrize('module', [dataset, sample])
def test_invalid_sort_is_rejected_by_argparse(module):
    name = module.__name__.split('.')[-1]

    with pytest.raises(SystemExit):
        make_parser(module).parse_args([name, 'list', '--sort', 'bogus'])
