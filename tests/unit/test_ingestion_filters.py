"""Unit coverage for ingestion request filters."""

from unittest.mock import MagicMock

from crucible.resources.ingestion import IngestionOperations


def test_filters_send_the_new_and_deprecated_names():
    client = MagicMock()
    client._request.return_value = {'items': [], 'total': 0}

    IngestionOperations(client).list(dsid='D', file_id='F')

    params = client._request.call_args.kwargs['params']
    assert params['dataset_mfid'] == params['dataset_id'] == 'D'
    assert params['file_mfid'] == params['file_id'] == 'F'
