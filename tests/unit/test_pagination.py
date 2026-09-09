"""Unit coverage for shared client-side pagination."""

from unittest.mock import MagicMock, call

import pytest

from crucible.constants import API_PAGE_MAX
from crucible.resources.base import BaseResource
from crucible.resources.datasets import DatasetOperations
from crucible.resources.samples import SampleOperations


def make_resource():
    client = MagicMock()
    return BaseResource(client), client._request


def records(start, count):
    return [{'id': value} for value in range(start, start + count)]


def test_small_limit_is_sent_to_offset_endpoint():
    resource, request = make_resource()
    request.return_value = {'total': 50, 'items': records(0, 5)}

    result = resource._paginate('/users', {}, limit=5)

    request.assert_called_once_with('get', '/users', params={'limit': 5})
    assert result == records(0, 5)


def test_cursor_final_page_requests_only_remaining_records():
    resource, request = make_resource()
    request.side_effect = [
        {
            'items': records(0, API_PAGE_MAX),
            'next_cursor': 'next-page',
        },
        {
            'items': records(API_PAGE_MAX, 5),
            'next_cursor': 'unused-page',
        },
    ]

    result = resource._paginate('/datasets', {}, limit=API_PAGE_MAX + 5)

    assert request.call_args_list == [
        call('get', '/datasets', params={'limit': API_PAGE_MAX}),
        call(
            'get',
            '/datasets',
            params={'limit': 5, 'cursor': 'next-page'},
        ),
    ]
    assert len(result) == API_PAGE_MAX + 5


def test_offset_final_page_requests_only_remaining_records():
    resource, request = make_resource()
    request.side_effect = [
        {
            'total': API_PAGE_MAX + 100,
            'items': records(0, API_PAGE_MAX),
        },
        {
            'total': API_PAGE_MAX + 100,
            'items': records(API_PAGE_MAX, 5),
        },
    ]

    result = resource._paginate('/users', {}, limit=API_PAGE_MAX + 5)

    assert request.call_args_list == [
        call('get', '/users', params={'limit': API_PAGE_MAX}),
        call(
            'get',
            '/users',
            params={'limit': 5, 'offset': API_PAGE_MAX},
        ),
    ]
    assert len(result) == API_PAGE_MAX + 5


def test_zero_limit_avoids_request():
    resource, request = make_resource()

    assert resource._paginate('/users', {}, limit=0) == []
    request.assert_not_called()


def test_negative_limit_is_rejected():
    resource, request = make_resource()

    with pytest.raises(ValueError, match='non-negative'):
        resource._paginate('/users', {}, limit=-1)

    request.assert_not_called()


@pytest.mark.parametrize(
    ('operations_class', 'filter_name', 'endpoint'),
    [
        (DatasetOperations, 'sample_mfid', '/datasets'),
        (SampleOperations, 'dataset_mfid', '/samples'),
    ],
)
def test_relationship_filters_follow_collection_cursors(
        operations_class, filter_name, endpoint):
    client = MagicMock()
    client._request.side_effect = [
        {
            'items': records(0, API_PAGE_MAX),
            'next_cursor': 'relationship-page-2',
        },
        {
            'items': records(API_PAGE_MAX, 1),
            'next_cursor': None,
        },
    ]
    operations = operations_class(client)

    result = operations.list(
        **{filter_name: '0tkn2knjast3h0008nyq9zps2c'},
        limit=API_PAGE_MAX + 1,
    )

    assert client._request.call_args_list == [
        call(
            'get',
            endpoint,
            params={
                filter_name: '0tkn2knjast3h0008nyq9zps2c',
                'limit': API_PAGE_MAX,
            },
        ),
        call(
            'get',
            endpoint,
            params={
                filter_name: '0tkn2knjast3h0008nyq9zps2c',
                'limit': 1,
                'cursor': 'relationship-page-2',
            },
        ),
    ]
    assert len(result) == API_PAGE_MAX + 1
