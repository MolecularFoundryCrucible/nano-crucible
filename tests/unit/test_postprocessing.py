"""Unit coverage for dataset postprocessing pipelines and runs."""

import argparse
from unittest.mock import MagicMock

import pytest

from crucible.cli import postprocess as postprocess_cli
from crucible.resources.datasets import DatasetOperations
from crucible.resources.postprocessing import PostprocessingOperations


DATASET = '0tkn2knjast3h0008nyq9zps2c'
RUN = {
    'run_id': 17,
    'dataset_mfid': DATASET,
    'pipeline': 'mosaic_stitch',
    'parameters': {},
    'status': 'requested',
    'requested_by': '0000-0002-1825-0097',
    'requested_at': '2026-10-19T07:00:00.000000Z',
}


def datasets(response=RUN):
    client = MagicMock()
    client._request.return_value = response
    return DatasetOperations(client), client._request


def test_postprocess_posts_pipeline_and_parameters_without_retry():
    resource, request = datasets()

    run = resource.postprocess(DATASET, 'rga_analysis', parameters={'window': 5})

    args, kwargs = request.call_args
    assert args == ('post', f'/datasets/{DATASET}/postprocess')
    assert kwargs['json'] == {'pipeline': 'rga_analysis', 'parameters': {'window': 5}}
    assert kwargs['headers'] is None
    assert kwargs['retry'] is False
    assert run['run_id'] == 17


def test_postprocess_with_idempotency_key_sends_header_and_may_retry():
    resource, request = datasets()

    resource.postprocess(DATASET, 'mosaic_stitch', idempotency_key='flow-1:mosaic_stitch')

    kwargs = request.call_args.kwargs
    assert kwargs['headers'] == {'Idempotency-Key': 'flow-1:mosaic_stitch'}
    assert kwargs['json'] == {'pipeline': 'mosaic_stitch', 'parameters': {}}
    assert kwargs['retry'] is True




def runs(response=None):
    client = MagicMock()
    client._request.return_value = response if response is not None else {
        'items': [RUN], 'total': 1, 'limit': 100, 'offset': 0}
    return PostprocessingOperations(client), client._request


def test_pipelines_lists_names_and_schemas():
    resource, request = runs([{'name': 'mosaic_stitch', 'description': 'Stitch',
                               'parameters_schema': {'properties': {}}}])

    pipelines = resource.pipelines()

    assert request.call_args.args == ('get', '/pipelines')
    assert pipelines[0]['name'] == 'mosaic_stitch'


def test_list_forwards_filters():
    resource, request = runs()

    result = resource.list(dataset_mfid=DATASET, pipeline='mosaic_stitch', status='failed')

    args, kwargs = request.call_args
    assert args == ('get', '/postprocessing_runs')
    assert kwargs['params']['dataset_mfid'] == DATASET
    assert kwargs['params']['pipeline'] == 'mosaic_stitch'
    assert kwargs['params']['status'] == 'failed'
    assert result[0]['run_id'] == 17


def test_list_rejects_unknown_status():
    resource, request = runs()

    with pytest.raises(ValueError):
        resource.list(status='done')

    request.assert_not_called()


def test_get_and_update_use_run_routes():
    resource, request = runs(RUN)

    resource.get(17)
    assert request.call_args.args == ('get', '/postprocessing_runs/17')

    resource.update(17, 'failed', error='tile missing')
    args, kwargs = request.call_args
    assert args == ('patch', '/postprocessing_runs/17')
    assert kwargs['json'] == {'status': 'failed', 'error': 'tile missing'}


def test_update_rejects_requested_status():
    resource, request = runs(RUN)

    with pytest.raises(ValueError):
        resource.update(17, 'requested')

    request.assert_not_called()


def parse(argv):
    parser = argparse.ArgumentParser()
    postprocess_cli.register(parser.add_subparsers())
    return parser.parse_args(argv)


def test_cli_postprocess_merges_json_and_key_value_parameters(monkeypatch, capsys):
    client = MagicMock()
    client.datasets.postprocess.return_value = RUN
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse(['postprocess', DATASET, 'rga_analysis', '--params', '{"a": 1, "b": "x"}',
                  '--param', 'b=2', '--param', 'name=tile', '--idempotency-key', 'k1'])
    args.func(args)

    client.datasets.postprocess.assert_called_once_with(
        DATASET, 'rga_analysis', parameters={'a': 1, 'b': 2, 'name': 'tile'},
        idempotency_key='k1')
    assert 'mosaic_stitch' in capsys.readouterr().out


def test_cli_postprocess_rejects_malformed_param(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse(['postprocess', DATASET, 'rga_analysis', '--param', 'novalue'])
    with pytest.raises(SystemExit) as exc:
        args.func(args)

    assert exc.value.code == 1
    client.datasets.postprocess.assert_not_called()


def test_cli_list_runs_shows_runs(monkeypatch, capsys):
    client = MagicMock()
    client.postprocessing.list.return_value = [RUN]
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    args = parse(['list-runs', DATASET, '--status', 'requested'])
    args.func(args)

    kwargs = client.postprocessing.list.call_args.kwargs
    assert kwargs['dataset_mfid'] == DATASET
    assert kwargs['status'] == 'requested'
    assert 'mosaic_stitch' in capsys.readouterr().out
