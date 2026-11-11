"""Unit coverage for ingestion request filters."""

from unittest.mock import MagicMock

import pytest

from crucible.resources.ingestion import IngestionOperations


def _ops():
    client = MagicMock()
    client._request.return_value = {'items': [], 'total': 0}
    return client, IngestionOperations(client)


@pytest.mark.parametrize('kwargs', [
    {'dataset_mfid': 'D', 'file_mfid': 'F'},
    {'dsid': 'D', 'file_id': 'F'},
    {'dataset_mfid': 'D', 'dsid': 'D', 'file_mfid': 'F', 'file_id': 'F'},
])
def test_filters_use_the_mfid_names(kwargs):
    client, ops = _ops()

    ops.list(**kwargs)

    params = client._request.call_args.kwargs['params']
    assert {k: params[k] for k in ('dataset_mfid', 'file_mfid')} == {'dataset_mfid': 'D', 'file_mfid': 'F'}
    assert 'dataset_id' not in params and 'file_id' not in params


def test_positional_filters_keep_their_order():
    client, ops = _ops()

    ops.list('D', 'F')

    params = client._request.call_args.kwargs['params']
    assert (params['dataset_mfid'], params['file_mfid']) == ('D', 'F')


@pytest.mark.parametrize('kwargs', [
    {'dataset_mfid': 'D', 'dsid': 'X'},
    {'file_mfid': 'F', 'file_id': 'X'},
])
def test_conflicting_names_raise(kwargs):
    _, ops = _ops()

    with pytest.raises(ValueError, match='pass only one'):
        ops.list(**kwargs)


REQUEST = {'id': 7, 'status': 'complete', 'ingestion_class': 'XRDIngestor',
           'dataset_mfid': 'D', 'file_mfid': '0tkfile000000000000000000a',
           'time_created': '2026-11-01T10:00:00Z'}


@pytest.mark.parametrize('module', ['dataset', 'file'])
def test_ingestion_tables_show_the_file_and_creation_time(module, monkeypatch, capsys):
    import importlib
    from types import SimpleNamespace
    cli = importlib.import_module(f'crucible.cli.{module}')
    client = MagicMock()
    client.ingestions.list.return_value = [REQUEST]
    monkeypatch.setattr('crucible.config.get_client', lambda: client)

    cli._execute_ingestion(SimpleNamespace(dataset_id='D', file_id=REQUEST['file_mfid'], debug=False))

    out = capsys.readouterr().out
    assert '2026-11-01' in out
    if module == 'dataset':
        assert REQUEST['file_mfid'] in out
