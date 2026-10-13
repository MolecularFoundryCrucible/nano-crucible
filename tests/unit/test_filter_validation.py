"""Unit coverage for client-side rejection of unsupported query filters."""

from unittest.mock import MagicMock

import pytest

from crucible.resources.base import BaseResource
from crucible.resources.datasets import (
    DatasetOperations, DATASET_LIST_PARAMS, DATASET_FACET_PARAMS)
from crucible.resources.samples import (
    SampleOperations, SAMPLE_LIST_PARAMS, SAMPLE_FACET_PARAMS)


def make_datasets():
    client = MagicMock()
    return DatasetOperations(client), client._request


def make_samples():
    client = MagicMock()
    return SampleOperations(client), client._request


def test_known_params_pass_through_unchanged():
    params = {'measurement': 'xrd', 'limit': 5}
    assert BaseResource._validate_filter_params(
        params, DATASET_LIST_PARAMS, '/datasets') is params


def test_unknown_param_raises_before_any_request():
    resource, request = make_datasets()

    with pytest.raises(ValueError) as excinfo:
        resource.list(bogus_param='x')

    assert 'bogus_param' in str(excinfo.value)
    assert '/datasets' in str(excinfo.value)
    request.assert_not_called()


def test_error_suggests_the_closest_valid_name():
    resource, _ = make_datasets()

    with pytest.raises(ValueError, match="did you mean 'measurement'"):
        resource.list(measurment='xrd')


def test_sample_list_rejects_unknown_param():
    resource, request = make_samples()

    with pytest.raises(ValueError, match='bogus_param'):
        resource.list(bogus_param='x')

    request.assert_not_called()


def test_dataset_count_rejects_unknown_param():
    resource, request = make_datasets()

    with pytest.raises(ValueError, match='bogus_param'):
        resource.count(bogus_param='x')

    request.assert_not_called()


def test_sample_count_rejects_unknown_param():
    resource, request = make_samples()

    with pytest.raises(ValueError, match='bogus_param'):
        resource.count(bogus_param='x')

    request.assert_not_called()


def test_child_listing_is_not_validated_against_the_collection_params():
    resource, request = make_samples()
    request.return_value = {'total': 0, 'items': []}

    resource.list(parent_mfid='0td7evvtg5wb90005k1j97ak94',
                  relationship_type='is_part_of')

    assert request.called


@pytest.mark.parametrize('allowed', [
    DATASET_LIST_PARAMS, DATASET_FACET_PARAMS,
    SAMPLE_LIST_PARAMS, SAMPLE_FACET_PARAMS,
])
def test_allowed_sets_cover_the_shared_scoping_params(allowed):
    for name in ('project_id', 'project_mfid', 'project_scope',
                 'accessible_to_user', 'accessible_to_project'):
        assert name in allowed
