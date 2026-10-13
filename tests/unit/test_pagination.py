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


def test_offset_envelope_with_a_null_cursor_still_fetches_every_page():
    resource, request = make_resource()

    def respond(method, endpoint, params):
        start = params.get('offset', 0)
        return {'total': API_PAGE_MAX + 5, 'limit': params['limit'], 'offset': start,
                'next_cursor': None,
                'items': records(start, min(params['limit'], API_PAGE_MAX + 5 - start))}

    request.side_effect = respond

    result = resource._paginate('/users/x/projects', {}, limit=None)

    assert result == records(0, API_PAGE_MAX + 5)


def test_cursor_listing_reports_more_when_stopped_at_the_limit():
    resource, request = make_resource()
    request.return_value = {'items': records(0, 5), 'next_cursor': 'more', 'total': 40}

    result = resource._paginate('/datasets', {}, limit=5)

    assert result == records(0, 5)
    assert result.has_more is True
    assert result.total == 40


def test_cursor_listing_without_a_cursor_has_no_more():
    resource, request = make_resource()
    request.return_value = {'items': records(0, 3), 'next_cursor': None}

    result = resource._paginate('/datasets', {}, limit=5)

    assert result.has_more is False
    assert result.total is None


@pytest.mark.parametrize('total, limit, has_more', [(50, 5, True), (5, 5, False), (3, 5, False)])
def test_offset_listing_reports_more_from_the_total(total, limit, has_more):
    resource, request = make_resource()
    request.return_value = {'total': total, 'items': records(0, min(total, limit))}

    result = resource._paginate('/users', {}, limit=limit)

    assert result.has_more is has_more
    assert result.total == total


def test_list_result_like_keeps_the_metadata():
    from crucible.resources.base import ListResult

    result = ListResult.like(ListResult([1, 2], has_more=True, total=9), [str(n) for n in [1, 2]])

    assert result == ['1', '2']
    assert (result.has_more, result.total) == (True, 9)


def test_dataset_list_keeps_list_metadata():
    client = MagicMock()
    client._request.return_value = {
        'items': [{'unique_id': '0' * 26, 'dataset_name': 'a'}],
        'next_cursor': 'more', 'total': 12}

    result = DatasetOperations(client).list(limit=1)

    assert result.has_more is True and result.total == 12


def test_cursor_listing_can_start_from_a_cursor_and_reports_the_next_one():
    resource, request = make_resource()
    request.return_value = {'items': records(5, 5), 'next_cursor': 'page-3', 'total': 40}

    result = resource._paginate('/datasets', {}, limit=5, cursor='page-2')

    request.assert_called_once_with('get', '/datasets', params={'limit': 5, 'cursor': 'page-2'})
    assert result.next_cursor == 'page-3'
    assert result.next_offset is None


def test_offset_listing_reports_the_next_offset():
    resource, request = make_resource()
    request.return_value = {'total': 40, 'items': records(10, 5)}

    result = resource._paginate('/users', {}, limit=5, offset=10)

    assert result.next_offset == 15
    assert result.start == 10
    assert result.next_cursor is None


def test_finished_listings_have_no_continuation():
    resource, request = make_resource()
    request.return_value = {'total': 3, 'items': records(0, 3)}

    result = resource._paginate('/users', {}, limit=5)

    assert result.next_offset is None and result.next_cursor is None


def test_every_paginating_method_accepts_a_cursor():
    import ast
    import pathlib

    import crucible.resources as package
    root = pathlib.Path(package.__file__).parent
    missing = []
    for path in root.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name != '_paginate' and any(
                    isinstance(call, ast.Call) and getattr(call.func, 'attr', '') == '_paginate'
                    for call in ast.walk(node)):
                names = [a.arg for a in node.args.args + node.args.kwonlyargs]
                if 'cursor' not in names:
                    missing.append(f'{path.name}:{node.name}')
    assert missing == []


def test_last_page_after_a_cursor_does_not_switch_to_offsets():
    resource, request = make_resource()
    request.return_value = {'items': records(0, 2), 'next_cursor': None, 'total': 40}

    result = resource._paginate('/datasets', {}, limit=5, cursor='last')

    assert request.call_count == 1
    assert result.has_more is False and result.next_cursor is None
