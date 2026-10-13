"""Unit coverage for interactive prompts in dataset create."""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset


def parse(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    dataset.register_subcommand(subparsers)
    return parser.parse_args(['dataset', 'create', *argv])


@pytest.fixture
def created(monkeypatch):
    client = SimpleNamespace(
        datasets=SimpleNamespace(create=MagicMock(return_value={'unique_id': 'D' * 26})),
        projects=SimpleNamespace(get=lambda value: {'project_id': value}))
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers.resolve_project_context',
                        lambda args: ('my-project', 'config'))
    monkeypatch.setattr(dataset, '_show_dataset', lambda *a, **k: None, raising=False)
    return client.datasets.create


def answers(monkeypatch, values):
    queue = list(values)
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers._prompt_value',
                        lambda label, **kwargs: queue.pop(0))


def test_bare_create_on_a_terminal_prompts(monkeypatch, created):
    answers(monkeypatch, ['XRD scan 12', 'my-project', 'XRD', None, None])

    try:
        dataset._execute_create(parse([]))
    except SystemExit:
        pass

    record = created.call_args.args[0]
    assert record.dataset_name == 'XRD scan 12'
    assert record.measurement == 'XRD'
    assert record.project_id == 'my-project'


def test_scripts_are_not_prompted(monkeypatch, created):
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: False)
    monkeypatch.setattr('crucible.cli.helpers._prompt_value',
                        lambda *a, **k: pytest.fail('prompted'))

    try:
        dataset._execute_create(parse([]))
    except SystemExit:
        pass

    assert created.called


def test_a_given_name_skips_the_prompts(monkeypatch, created):
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers._prompt_value',
                        lambda *a, **k: pytest.fail('prompted'))

    try:
        dataset._execute_create(parse(['--name', 'given']))
    except SystemExit:
        pass

    assert created.call_args.args[0].dataset_name == 'given'
