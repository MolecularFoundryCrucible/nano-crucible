"""Unit coverage for typed resource access selectors."""

from unittest.mock import MagicMock

import pytest

from crucible.models import Dataset, Sample
from crucible.resources.datasets import DatasetOperations
from crucible.resources.projects import ProjectOperations
from crucible.resources.samples import SampleOperations


PROJECT_MFID = '0tkn2knjast3h0008nyq9zps2c'
INSTRUMENT_MFID = '0tk8pf1me0h3h0003fp91vr037'


@pytest.mark.parametrize(
    ('operations_class', 'resource', 'endpoint', 'expected'),
    [
        (
            DatasetOperations,
            Dataset(
                dataset_name='test',
                project_id='project-a',
                project_mfid=PROJECT_MFID,
                instrument_id='xrd-one',
                instrument_mfid=INSTRUMENT_MFID,
            ),
            '/datasets',
            {
                'project_id': 'project-a',
                'project_mfid': PROJECT_MFID,
                'instrument_id': 'xrd-one',
                'instrument_mfid': INSTRUMENT_MFID,
            },
        ),
        (
            SampleOperations,
            Sample(
                sample_name='test',
                project_id='project-a',
                project_mfid=PROJECT_MFID,
            ),
            '/samples',
            {
                'project_id': 'project-a',
                'project_mfid': PROJECT_MFID,
            },
        ),
    ],
)
def test_create_preserves_matching_id_and_mfid_selectors(
        operations_class, resource, endpoint, expected):
    operations = operations_class(MagicMock())
    operations._request = MagicMock(return_value={'unique_id': PROJECT_MFID})

    operations.create(resource)

    payload = operations._request.call_args.kwargs['json']
    assert operations._request.call_args.args[:2] == ('post', endpoint)
    assert {key: payload[key] for key in expected} == expected


@pytest.mark.parametrize(
    ('operations_class', 'endpoint'),
    [
        (DatasetOperations, '/datasets'),
        (SampleOperations, '/samples'),
        (ProjectOperations, '/projects'),
    ],
)
def test_lists_with_repeated_user_and_project_selectors(operations_class, endpoint):
    client = MagicMock()
    operations = operations_class(client)
    operations._request = MagicMock(return_value={
        'total': 0,
        'limit': 5,
        'offset': 0,
        'items': [],
    })

    operations.list(
        accessible_to_user=['alice', 'bob'],
        accessible_to_project=['project-a'],
        limit=5,
    )

    operations._request.assert_called_once_with(
        'get',
        endpoint,
        params={
            'accessible_to_user': ['alice', 'bob'],
            'accessible_to_project': ['project-a'],
            'limit': 5,
        },
    )


def test_rejects_more_than_ten_selectors():
    operations = DatasetOperations(MagicMock())

    with pytest.raises(ValueError, match='At most 10'):
        operations.list(accessible_to_user=[str(i) for i in range(11)])


def test_sample_relationship_filter_accepts_access_selectors():
    operations = SampleOperations(MagicMock())
    operations._paginate = MagicMock(return_value=[])

    operations.list(dataset_mfid='dataset', accessible_to_user='alice')

    operations._paginate.assert_called_once_with(
        '/samples',
        {'accessible_to_user': ['alice'], 'dataset_mfid': 'dataset'},
        100,
        0,
    )


def test_dataset_list_filters_by_instrument_mfid():
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value={
        'total': 0,
        'limit': 5,
        'offset': 0,
        'items': [],
    })

    operations.list(instrument_mfid='0tkn2knjast3h0008nyq9zps2c', limit=5)

    operations._request.assert_called_once_with(
        'get',
        '/datasets',
        params={
            'instrument_mfid': '0tkn2knjast3h0008nyq9zps2c',
            'limit': 5,
        },
    )


def test_dataset_relationship_filter_accepts_instrument_and_access_filters():
    operations = DatasetOperations(MagicMock())
    operations._paginate = MagicMock(return_value=[])

    operations.list(
        sample_mfid='0tkn2knjast3h0008nyq9zps2c',
        instrument_mfid='0tk8pf1me0h3h0003fp91vr037',
        accessible_to_project='project-a',
    )

    operations._paginate.assert_called_once_with(
        '/datasets',
        {
            'accessible_to_project': ['project-a'],
            'sample_mfid': '0tkn2knjast3h0008nyq9zps2c',
            'instrument_mfid': '0tk8pf1me0h3h0003fp91vr037',
        },
        100,
        0,
    )


@pytest.mark.parametrize(
    'operations_class',
    [DatasetOperations, SampleOperations],
)
@pytest.mark.parametrize(
    ('selector', 'scope'),
    [
        ({'project_id': 'project-a'}, 'all'),
        ({'project_mfid': PROJECT_MFID}, 'shared'),
    ],
)
def test_resource_lists_send_typed_project_scope(
        operations_class, selector, scope):
    operations = operations_class(MagicMock())
    operations._paginate = MagicMock(return_value=[])

    operations.list(**selector, project_scope=scope)

    operations._paginate.assert_called_once_with(
        f'/{"datasets" if operations_class is DatasetOperations else "samples"}',
        {**selector, 'project_scope': scope},
        100,
        0,
    )


@pytest.mark.parametrize(
    'operations_class',
    [DatasetOperations, SampleOperations],
)
def test_project_scope_requires_a_project_selector(operations_class):
    operations = operations_class(MagicMock())

    with pytest.raises(ValueError, match='requires project_id or project_mfid'):
        operations.list(project_scope='all')


@pytest.mark.parametrize(
    'operations_class',
    [DatasetOperations, SampleOperations],
)
def test_project_scope_accepts_matching_selector_pair_for_server_validation(
        operations_class):
    operations = operations_class(MagicMock())
    operations._paginate = MagicMock(return_value=[])

    operations.list(
        project_id='project-a',
        project_mfid=PROJECT_MFID,
        project_scope='all',
    )

    operations._paginate.assert_called_once_with(
        f'/{"datasets" if operations_class is DatasetOperations else "samples"}',
        {
            'project_id': 'project-a',
            'project_mfid': PROJECT_MFID,
            'project_scope': 'all',
        },
        100,
        0,
    )


@pytest.mark.parametrize(
    'operations_class',
    [DatasetOperations, SampleOperations],
)
def test_project_scope_validates_scope_and_mfid(operations_class):
    operations = operations_class(MagicMock())

    with pytest.raises(ValueError, match='assigned, shared, all'):
        operations.list(project_id='project-a', project_scope='invalid')

    with pytest.raises(ValueError, match='exact 26-character MFID'):
        operations.list(project_mfid='not-an-mfid')


def test_dataset_count_sends_project_scope():
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value={'total': 4})

    assert operations.count(project_id='project-a', project_scope='all') == 4
    operations._request.assert_called_once_with(
        'get',
        '/datasets',
        params={'project_id': 'project-a', 'project_scope': 'all', 'limit': 1},
    )


def test_nested_sample_children_reject_project_scope():
    operations = SampleOperations(MagicMock())

    with pytest.raises(ValueError, match='top-level sample list'):
        operations.list(parent_mfid=PROJECT_MFID, project_id='project-a')
