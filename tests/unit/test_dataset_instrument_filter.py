"""Unit coverage for filtering datasets by instrument slug."""

from unittest.mock import MagicMock

import pytest

from crucible.resources.datasets import DatasetOperations

TITAN = '0abcdefghjkmnpqrstvwxyz012'


def make(instrument=None):
    client = MagicMock()
    client.instruments.get.return_value = (
        {'unique_id': TITAN} if instrument is None else instrument)
    client._request.return_value = {
        'items': [], 'next_cursor': None, 'total': 0,
        'field': 'measurement', 'limit': 100,
    }
    return DatasetOperations(client), client


def sent_params(client):
    return client._request.call_args.kwargs['params']


@pytest.mark.parametrize('call', [
    lambda ds: ds.list(instrument_id='Titan'),
    lambda ds: ds.count(instrument_id='Titan'),
    lambda ds: ds.facets('measurement', instrument_id='Titan'),
])
def test_slug_is_sent_as_its_mfid(call):
    datasets, client = make()

    call(datasets)

    client.instruments.get.assert_called_once_with(
        instrument_id='Titan', include_owner=False)
    params = sent_params(client)
    assert params['instrument_mfid'] == TITAN
    assert 'instrument_id' not in params


def test_matching_slug_and_mfid_are_accepted():
    datasets, client = make()

    datasets.list(instrument_id='titan', instrument_mfid=TITAN)

    assert sent_params(client)['instrument_mfid'] == TITAN


def test_conflicting_slug_and_mfid_are_rejected():
    datasets, client = make()

    with pytest.raises(ValueError, match='different instruments'):
        datasets.list(instrument_id='titan', instrument_mfid='1' * 26)
    client._request.assert_not_called()


def test_unknown_slug_is_rejected():
    datasets, client = make(instrument={})

    with pytest.raises(ValueError, match="Instrument 'nope' not found"):
        datasets.list(instrument_id='nope')
    client._request.assert_not_called()
