"""Unit coverage for the ordering, visibility, and time-range list filters."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from crucible.resources.datasets import DatasetOperations
from crucible.resources.samples import SampleOperations


def make(cls):
    client = MagicMock()
    resource = cls(client)
    client._request.return_value = {'items': [], 'next_cursor': None}
    return resource, client._request


def sent_params(request):
    return request.call_args.kwargs['params']


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_defaults_send_no_new_parameters(cls):
    resource, request = make(cls)

    resource.list(limit=5)

    params = sent_params(request)
    for name in ('sort', 'direction', 'visibility', 'affiliation',
                 'include_total', 'creation_time_gte',
                 'creation_time_lte', 'modification_time_gte',
                 'modification_time_lte'):
        assert name not in params


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_sort_and_direction_are_sent(cls):
    resource, request = make(cls)

    resource.list(limit=5, sort='created', direction='desc')

    params = sent_params(request)
    assert params['sort'] == 'created'
    assert params['direction'] == 'desc'


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_direction_without_sort_is_rejected_locally(cls):
    resource, request = make(cls)

    with pytest.raises(ValueError, match='direction requires sort'):
        resource.list(direction='desc')

    request.assert_not_called()


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_unknown_sort_is_rejected(cls):
    resource, _ = make(cls)

    with pytest.raises(ValueError, match='sort must be one of'):
        resource.list(sort='bogus')


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_unknown_visibility_is_rejected(cls):
    resource, _ = make(cls)

    with pytest.raises(ValueError, match='visibility must be one of'):
        resource.list(visibility='secret')


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_datetime_bounds_are_normalized_to_iso(cls):
    resource, request = make(cls)

    resource.list(creation_time_gte=datetime(2026, 1, 2, 3, 4, 5))

    assert sent_params(request)['creation_time_gte'] == '2026-01-02T03:04:05'


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_string_bounds_pass_through(cls):
    resource, request = make(cls)

    resource.list(modification_time_lte='2026-01-02T00:00:00Z')

    assert sent_params(request)['modification_time_lte'] == '2026-01-02T00:00:00Z'


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_invalid_time_bound_is_rejected(cls):
    resource, _ = make(cls)

    with pytest.raises(ValueError, match='creation_time_gte must be'):
        resource.list(creation_time_gte=12345)


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_affiliation_accepts_a_string_or_sequence(cls):
    resource, request = make(cls)

    resource.list(affiliation='owner')
    assert sent_params(request)['affiliation'] == ['owner']

    resource.list(affiliation=['owner'])
    assert sent_params(request)['affiliation'] == ['owner']


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_unknown_affiliation_is_rejected(cls):
    resource, _ = make(cls)

    with pytest.raises(ValueError, match='affiliation values must be one of'):
        resource.list(affiliation='reviewer')


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_include_total_is_sent(cls):
    resource, request = make(cls)

    resource.list(include_total=True)

    assert sent_params(request)['include_total'] is True


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_include_total_false_is_sent_explicitly(cls):
    resource, request = make(cls)

    resource.list(include_total=False)

    assert sent_params(request)['include_total'] is False


def test_sample_child_listing_rejects_collection_only_filters():
    resource, request = make(SampleOperations)

    with pytest.raises(ValueError, match='only by the top-level sample list'):
        resource.list(parent_mfid='0td7evvtg5wb90005k1j97ak94', sort='created')

    request.assert_not_called()
