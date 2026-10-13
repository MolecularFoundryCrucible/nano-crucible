"""Unit coverage for typo suggestions and API error hints."""

from types import SimpleNamespace

import pytest
import requests

from crucible.cli import helpers
from crucible.cli.parser import SuggestingArgumentParser


def make_parser():
    parser = SuggestingArgumentParser(prog='crucible')
    parser.add_argument('--debug', action='store_true')
    subparsers = parser.add_subparsers(dest='command')
    dataset = subparsers.add_parser('dataset')
    dataset_sub = dataset.add_subparsers(dest='subcommand')
    listing = dataset_sub.add_parser('list')
    listing.add_argument('--limit', type=int)
    listing.add_argument('--measurement')
    dataset_sub.add_parser('get')
    subparsers.add_parser('sample')
    return parser


def error_for(argv, capsys):
    with pytest.raises(SystemExit):
        make_parser().parse_args(argv)
    return capsys.readouterr().err


def test_mistyped_command_suggests_the_closest(capsys):
    err = error_for(['datset'], capsys)

    assert err == "crucible: error: 'datset' is not a crucible command. Did you mean 'dataset'?\n"


def test_mistyped_subcommand_suggests_the_closest(capsys):
    err = error_for(['dataset', 'lsit'], capsys)

    assert err == ("crucible dataset: error: 'lsit' is not a crucible dataset command. "
                   "Did you mean 'list'?\n")


def test_unknown_command_points_to_help(capsys):
    err = error_for(['zzzzzz'], capsys)

    assert err == ("crucible: error: 'zzzzzz' is not a crucible command. "
                   "Run 'crucible --help' to see them.\n")


def test_invalid_option_values_keep_their_choices(capsys):
    parser = SuggestingArgumentParser(prog='crucible')
    parser.add_argument('--scope', choices=['assigned', 'shared', 'all'])
    with pytest.raises(SystemExit):
        parser.parse_args(['--scope', 'shard'])

    err = capsys.readouterr().err
    assert "choose from" in err and "Did you mean 'shared'?" in err


def test_mistyped_flag_suggests_one_from_that_command(capsys):
    err = error_for(['dataset', 'list', '--limt', '5'], capsys)

    assert "Did you mean '--limit'?" in err


def http_error(status, detail=None):
    response = SimpleNamespace(status_code=status, reason='Reason', text='',
                               json=lambda: {'detail': detail} if detail else {})
    return requests.HTTPError(response=response)


@pytest.mark.parametrize('error, fragment', [
    (http_error(401), 'crucible config init'),
    (http_error(403), 'crucible whoami'),
    (http_error(404), 'identifier'),
    (http_error(422, [{'loc': ['query', 'sort'], 'msg': 'Extra inputs are not permitted',
                       'type': 'extra_forbidden'}]), 'older API'),
    (requests.exceptions.ConnectTimeout(), 'read_timeout'),
    (requests.exceptions.ConnectionError(), 'network'),
])
def test_api_errors_carry_a_hint(error, fragment):
    assert fragment in helpers.format_cli_error('listing datasets', error)['hint']


def test_other_errors_have_no_hint():
    assert 'hint' not in helpers.format_cli_error('x', http_error(500))


def test_hint_is_printed_after_the_details(capsys):
    helpers.print_cli_error({'type': 'http_error', 'message': 'Failed.', 'details': [],
                             'status': 401, 'hint': 'Run crucible config init.'})

    assert capsys.readouterr().err.rstrip().endswith('Run crucible config init.')
