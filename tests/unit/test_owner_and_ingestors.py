"""Unit coverage for --owner on create commands and --ingestor completion."""

import argparse
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset, helpers, sample


@pytest.fixture
def fresh_ingestors(tmp_path, monkeypatch):
    from crucible.config import config
    monkeypatch.setattr(helpers, '_ingestor_names', None)
    monkeypatch.setitem(config._data, 'cache_dir', str(tmp_path))
    yield tmp_path
    helpers._ingestor_names = None


def test_ingestor_names_come_from_the_api_and_are_cached(fresh_ingestors):
    client = MagicMock()
    client._request.return_value = ['ZIngestor', 'AIngestor']

    assert helpers.ingestor_names(client) == ['AIngestor', 'ZIngestor']
    helpers._ingestor_names = None
    client._request.side_effect = AssertionError('should use the cache')
    assert helpers.ingestor_names(client) == ['AIngestor', 'ZIngestor']


def test_stale_cache_is_refreshed(fresh_ingestors):
    client = MagicMock()
    client._request.return_value = ['Old']
    helpers.ingestor_names(client)
    cache = next(fresh_ingestors.glob('ingestors-*.json'))
    old = time.time() - 2 * helpers._INGESTOR_CACHE_SECONDS
    os.utime(cache, (old, old))
    helpers._ingestor_names = None
    client._request.return_value = ['New']

    assert helpers.ingestor_names(client) == ['New']
    assert json.loads(cache.read_text()) == ['New']


def test_unreachable_api_falls_back_to_the_built_in_list(fresh_ingestors):
    from crucible.constants import AVAILABLE_INGESTORS
    client = MagicMock()
    client._request.side_effect = ConnectionError()

    assert helpers.ingestor_names(client) == list(AVAILABLE_INGESTORS)


def test_shell_completes_ingestors_fuzzily(fresh_ingestors, monkeypatch):
    from prompt_toolkit.document import Document
    from crucible.cli.shell.completer import CrucibleCompleter

    monkeypatch.setattr(helpers, '_ingestor_names', ['AFMIngestor', 'VeloxEmdIngestor', 'H5Ingestor'])
    parser = argparse.ArgumentParser()
    dataset.register_subcommand(parser.add_subparsers(dest='resource'))
    completer = CrucibleCompleter(parser, client=MagicMock(), state={})

    text = 'dataset add-file X -i f.emd --ingestor vemd'
    options = [c.text.strip() for c in completer.get_completions(Document(text), None)]

    assert options == ['VeloxEmdIngestor']


def parse(module, argv):
    parser = argparse.ArgumentParser()
    module.register_subcommand(parser.add_subparsers(dest='command'))
    return parser.parse_args(argv)


def test_sample_create_sends_the_owner(monkeypatch):
    client = SimpleNamespace(samples=SimpleNamespace(create=MagicMock(return_value={'unique_id': 'S'})),
                             projects=SimpleNamespace(get=lambda v: {'project_id': v}))
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr(sample, '_show_sample', lambda *a, **k: None)
    args = parse(sample, ['sample', 'create', '--name', 'n', '--project-id', 'p', '--owner', 'alice'])

    args.func(args)

    assert client.samples.create.call_args.args[0].owner == 'alice'


def test_dataset_create_sends_the_owner(monkeypatch):
    client = SimpleNamespace(datasets=SimpleNamespace(create=MagicMock(return_value={'unique_id': 'D'})))
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: False)
    args = parse(dataset, ['dataset', 'create', '--name', 'n', '--project-id', 'p', '--owner', 'alice'])

    try:
        args.func(args)
    except SystemExit:
        pass

    assert client.datasets.create.call_args.args[0].owner == 'alice'


def test_parsers_carry_the_owner_into_the_dataset():
    from crucible.parsers.base import BaseParser

    parser = BaseParser(project_id='p')
    parser.owner = 'alice'

    assert parser.to_dataset().owner == 'alice'
