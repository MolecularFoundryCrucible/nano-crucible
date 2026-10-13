"""Unit coverage for ingestion request filters."""

from unittest.mock import MagicMock

from crucible.resources.ingestion import IngestionOperations


def test_filters_use_the_mfid_names():
    client = MagicMock()
    client._request.return_value = {'items': [], 'total': 0}

    IngestionOperations(client).list(dsid='D', file_id='F')

    params = client._request.call_args.kwargs['params']
    assert {k: params[k] for k in ('dataset_mfid', 'file_mfid')} == {'dataset_mfid': 'D', 'file_mfid': 'F'}
    assert 'dataset_id' not in params and 'file_id' not in params
