"""Unit coverage for dataset and sample facet grouping."""

from unittest.mock import MagicMock

import pytest

from crucible.resources.datasets import DatasetOperations
from crucible.resources.samples import SampleOperations


def make(cls, response=None):
    client = MagicMock()
    resource = cls(client)
    client._request.return_value = response or {
        'field': 'measurement',
        'items': [{'value': 'xrd', 'label': 'XRD', 'count': 3}],
        'limit': 100,
        'next_cursor': None,
    }
    return resource, client._request


def test_dataset_facets_calls_the_facet_endpoint():
    resource, request = make(DatasetOperations)

    result = resource.facets('measurement')

    request.assert_called_once_with(
        'get', '/datasets/facets', params={'field': 'measurement', 'limit': 100})
    assert result['items'][0]['count'] == 3


def test_sample_facets_calls_the_facet_endpoint():
    resource, request = make(SampleOperations)

    resource.facets('sample_type')

    request.assert_called_once_with(
        'get', '/samples/facets', params={'field': 'sample_type', 'limit': 100})


@pytest.mark.parametrize('cls,field', [
    (DatasetOperations, 'measurement'),
    (SampleOperations, 'sample_type'),
])
def test_sort_direction_and_cursor_are_sent(cls, field):
    resource, request = make(cls)

    resource.facets(field, limit=5, sort='count', direction='desc',
                    cursor='token')

    params = request.call_args.kwargs['params']
    assert params['sort'] == 'count'
    assert params['direction'] == 'desc'
    assert params['cursor'] == 'token'
    assert params['limit'] == 5


def test_facet_direction_alone_is_allowed():
    resource, request = make(DatasetOperations)

    resource.facets('measurement', direction='desc')

    params = request.call_args.kwargs['params']
    assert params['direction'] == 'desc'
    assert 'sort' not in params


def test_unknown_field_is_rejected_before_any_request():
    resource, request = make(DatasetOperations)

    with pytest.raises(ValueError, match='field must be one of'):
        resource.facets('bogus')

    request.assert_not_called()


def test_sample_rejects_a_dataset_only_field():
    resource, _ = make(SampleOperations)

    with pytest.raises(ValueError, match='field must be one of'):
        resource.facets('instrument')


def test_unknown_facet_sort_is_rejected():
    resource, _ = make(DatasetOperations)

    with pytest.raises(ValueError, match='sort must be one of'):
        resource.facets('measurement', sort='created')


def test_unknown_filter_is_rejected():
    resource, request = make(DatasetOperations)

    with pytest.raises(ValueError, match='bogus_param'):
        resource.facets('measurement', bogus_param='x')

    request.assert_not_called()


def test_list_only_filters_are_rejected_for_facets():
    resource, _ = make(DatasetOperations)

    with pytest.raises(ValueError, match='keyword'):
        resource.facets('measurement', keyword='alpha')


def test_filters_restrict_the_contributing_records():
    resource, request = make(DatasetOperations)

    resource.facets('measurement', project_id='demo')

    assert request.call_args.kwargs['params']['project_id'] == 'demo'


def test_typed_reference_on_a_bucket_is_preserved():
    resource, _ = make(DatasetOperations, response={
        'field': 'instrument',
        'items': [{
            'value': '0sh6zrzxhnz8k000k7pwq0s2t8',
            'label': 'titanx',
            'count': 7,
            'instrument': {'unique_id': '0sh6zrzxhnz8k000k7pwq0s2t8',
                           'instrument_name': 'titanx'},
        }],
        'limit': 100,
        'next_cursor': 'more',
    })

    result = resource.facets('instrument')

    assert result['items'][0]['instrument']['instrument_name'] == 'titanx'
    assert result['next_cursor'] == 'more'
