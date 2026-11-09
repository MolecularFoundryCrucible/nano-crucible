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
