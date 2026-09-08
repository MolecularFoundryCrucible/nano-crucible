"""Unit coverage for dataset and sample owner request and response contracts."""

import warnings
from unittest.mock import MagicMock

import pytest

from crucible.client import CrucibleClient
from crucible.models import (
    Dataset,
    Instrument,
    InstrumentReference,
    ProjectReference,
    PublicUser,
    ResourceCapabilities,
    Sample,
)
from crucible.resources.datasets import DatasetOperations
from crucible.resources.instruments import InstrumentOperations
from crucible.resources.samples import SampleOperations


MFID = '0tkn2knjast3h0008nyq9zps2c'
SECOND_MFID = '0td7evvtg5wb90005k1j97ak94'
ORCID = '0000-0001-6402-3752'
PUBLIC_OWNER = {
    'unique_id': ORCID,
    'username': 'roncofaber',
    'first_name': 'Fabrice',
    'last_name': 'Roncoroni',
}
CAPABILITIES = {
    'can_edit': True,
    'can_manage_access': True,
    'can_change_status': False,
    'can_transfer': False,
    'max_grant_role': 'editor',
}


def make_ops(operations_class, response):
    client = MagicMock()
    operations = operations_class(client)
    operations._request = MagicMock(return_value=response)
    return operations


@pytest.mark.parametrize('model', [Dataset, Sample, Instrument])
def test_owner_response_uses_public_user_model(model):
    resource = model.model_validate({
        'unique_id': MFID,
        'owner_orcid': ORCID,
        'owner': PUBLIC_OWNER,
    })

    assert isinstance(resource.owner, PublicUser)
    assert resource.model_dump()['owner'] == PUBLIC_OWNER


@pytest.mark.parametrize(
    ('operations_class', 'resource_name'),
    [(DatasetOperations, 'datasets'), (SampleOperations, 'samples')],
)
def test_get_requests_and_preserves_public_owner_by_default(operations_class, resource_name):
    response = {
        'unique_id': MFID,
        'owner_orcid': ORCID,
        'owner': PUBLIC_OWNER,
        'capabilities': CAPABILITIES,
    }
    operations = make_ops(operations_class, response)

    result = operations.get(MFID)

    operations._request.assert_called_once_with(
        'get',
        f'/{resource_name}/{MFID}',
        params={'include_owner': True},
    )
    assert result['owner'] == PUBLIC_OWNER
    assert result['capabilities'] == CAPABILITIES


@pytest.mark.parametrize(
    'model',
    [Dataset, Sample],
)
def test_dataset_and_sample_capabilities_are_typed(model):
    resource = model.model_validate({
        'unique_id': MFID,
        'capabilities': CAPABILITIES,
    })

    assert isinstance(resource.capabilities, ResourceCapabilities)
    assert resource.capabilities.can_change_status is False
    assert resource.capabilities.max_grant_role == 'editor'


def test_dataset_response_uses_typed_resource_references():
    resource = Dataset.model_validate({
        'unique_id': MFID,
        'instrument': {
            'unique_id': SECOND_MFID,
            'instrument_id': 'xrd-1',
            'instrument_name': 'High Resolution XRD',
        },
        'project': {
            'unique_id': SECOND_MFID,
            'project_id': 'project-one',
            'title': 'Project One',
        },
    })

    assert isinstance(resource.instrument, InstrumentReference)
    assert isinstance(resource.project, ProjectReference)
    assert resource.instrument.unique_id == SECOND_MFID
    assert resource.project.project_id == 'project-one'


def test_sample_response_uses_typed_project_reference():
    resource = Sample.model_validate({
        'unique_id': MFID,
        'sample_name': 'test',
        'project': {
            'unique_id': SECOND_MFID,
            'project_id': 'project-one',
            'title': 'Project One',
        },
    })

    assert isinstance(resource.project, ProjectReference)
    assert resource.project.unique_id == SECOND_MFID
    assert resource.project.project_id == 'project-one'


@pytest.mark.parametrize('model', [Dataset, Sample])
def test_scoped_collection_project_relation_is_typed(model):
    resource = model.model_validate({
        'unique_id': MFID,
        'project': None,
        'project_relation': 'shared',
    })

    assert resource.project is None
    assert resource.project_relation == 'shared'

    with pytest.raises(ValueError):
        model.model_validate({
            'unique_id': MFID,
            'project_relation': 'unrelated',
        })


@pytest.mark.parametrize(
    'operations_class',
    [DatasetOperations, SampleOperations],
)
def test_collection_results_accept_null_capabilities(operations_class):
    operations = make_ops(operations_class, None)
    operations._paginate = MagicMock(return_value=[{
        'unique_id': MFID,
        'capabilities': None,
    }])

    result = operations.list(limit=1)

    assert result[0]['capabilities'] is None


@pytest.mark.parametrize(
    ('operations_class', 'resource_name'),
    [(DatasetOperations, 'datasets'), (SampleOperations, 'samples')],
)
def test_get_can_suppress_owner_expansion(operations_class, resource_name):
    operations = make_ops(operations_class, {'unique_id': MFID, 'owner_orcid': ORCID})

    operations.get(MFID, include_owner=False)

    operations._request.assert_called_once_with(
        'get',
        f'/{resource_name}/{MFID}',
        params=None,
    )


def test_sample_get_can_suppress_legacy_dataset_expansion():
    operations = make_ops(SampleOperations, {'unique_id': MFID, 'datasets': None})

    result = operations.get(MFID, include_datasets=False)

    operations._request.assert_called_once_with(
        'get',
        f'/samples/{MFID}',
        params={'include_owner': True, 'include_datasets': False},
    )
    assert result['datasets'] is None


def test_generic_get_requests_owner_by_default():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client._request = MagicMock(return_value={
        'unique_id': MFID,
        'resource_type': 'dataset',
        'capabilities': CAPABILITIES,
    })

    result = client.get(MFID)

    client._request.assert_called_once_with(
        'get',
        f'/resources/{MFID}',
        params={'include_owner': True},
    )
    assert result['capabilities'] == CAPABILITIES


def test_generic_get_can_suppress_owner_expansion():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client._request = MagicMock(return_value={'unique_id': MFID, 'resource_type': 'dataset'})

    client.get(MFID, include_owner=False)

    client._request.assert_called_once_with('get', f'/resources/{MFID}', params=None)


def test_generic_get_can_suppress_legacy_sample_dataset_expansion():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client._request = MagicMock(return_value={
        'unique_id': MFID,
        'resource_type': 'sample',
        'datasets': None,
    })

    result = client.get(MFID, include_datasets=False)

    client._request.assert_called_once_with(
        'get',
        f'/resources/{MFID}',
        params={'include_owner': True, 'include_datasets': False},
    )
    assert result['datasets'] is None


def test_typed_generic_sample_get_propagates_include_datasets():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client.samples.get = MagicMock(return_value={'unique_id': MFID})

    client.get(MFID, resource_type='sample', include_datasets=False)

    client.samples.get.assert_called_once_with(
        MFID,
        include_links=False,
        include_metadata=False,
        include_owner=True,
        include_datasets=False,
    )


def test_typed_generic_sample_get_preserves_default_call_contract():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client.samples.get = MagicMock(return_value={'unique_id': MFID})

    client.get(MFID, resource_type='sample')

    client.samples.get.assert_called_once_with(
        MFID,
        include_links=False,
        include_metadata=False,
        include_owner=True,
    )


def test_instrument_get_requests_and_preserves_public_owner_by_default():
    response = {'unique_id': MFID, 'owner_orcid': ORCID, 'owner': PUBLIC_OWNER}
    operations = make_ops(InstrumentOperations, response)

    result = operations.get(instrument_mfid=MFID)

    operations._request.assert_called_once_with(
        'get', f'/instruments/{MFID}', params={'include_owner': True})
    assert result['owner'] == PUBLIC_OWNER


def test_typed_generic_instrument_get_propagates_include_owner():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client.instruments.get = MagicMock(return_value={'unique_id': MFID})

    client.get(MFID, resource_type='instrument', include_owner=False)

    client.instruments.get.assert_called_once_with(
        instrument_mfid=MFID,
        include_metadata=False,
        include_owner=False,
    )


def test_typed_generic_project_get_uses_project_mfid():
    client = CrucibleClient(api_url='https://example.invalid', api_key='test')
    client.projects.get = MagicMock(return_value={'unique_id': MFID})

    client.get(MFID, resource_type='project', include_metadata=True)

    client.projects.get.assert_called_once_with(
        project_mfid=MFID,
        include_metadata=True,
    )


def test_dataset_create_warns_for_owner_orcid_and_preserves_payload():
    operations = make_ops(DatasetOperations, {'unique_id': MFID})

    with pytest.warns(DeprecationWarning, match='Dataset.owner_orcid'):
        operations.create(Dataset(unique_id=MFID, dataset_name='test', owner_orcid=ORCID))

    assert operations._request.call_args.kwargs['json']['owner_orcid'] == ORCID


def test_sample_create_warns_for_owner_orcid_and_preserves_payload():
    operations = make_ops(SampleOperations, {'unique_id': MFID})

    with pytest.warns(DeprecationWarning, match='Sample.owner_orcid'):
        operations.create(Sample(unique_id=MFID, sample_name='test', owner_orcid=ORCID))

    assert operations._request.call_args.kwargs['json']['owner_orcid'] == ORCID


@pytest.mark.parametrize(
    ('operations_class', 'resource'),
    [
        (DatasetOperations, Dataset(
            unique_id=MFID,
            dataset_name='test',
            capabilities=CAPABILITIES,
        )),
        (SampleOperations, Sample(
            unique_id=MFID,
            sample_name='test',
            capabilities=CAPABILITIES,
        )),
    ],
)
def test_create_omits_response_capabilities(operations_class, resource):
    operations = make_ops(operations_class, {'unique_id': MFID})

    operations.create(resource)

    assert 'capabilities' not in operations._request.call_args.kwargs['json']


def test_dataset_create_omits_response_references():
    operations = make_ops(DatasetOperations, {'unique_id': MFID})
    dataset = Dataset(
        unique_id=MFID,
        dataset_name='test',
        instrument={
            'unique_id': SECOND_MFID,
            'instrument_id': 'xrd-1',
            'instrument_name': 'High Resolution XRD',
        },
        project={
            'unique_id': SECOND_MFID,
            'project_id': 'project-one',
        },
    )

    operations.create(dataset)

    payload = operations._request.call_args.kwargs['json']
    assert 'instrument' not in payload
    assert 'project' not in payload


def test_sample_create_omits_project_reference():
    operations = make_ops(SampleOperations, {'unique_id': MFID})
    sample = Sample(
        unique_id=MFID,
        sample_name='test',
        project={
            'unique_id': SECOND_MFID,
            'project_id': 'project-one',
        },
    )

    operations.create(sample)

    assert 'project' not in operations._request.call_args.kwargs['json']


def test_dataset_update_rejects_response_capabilities():
    operations = make_ops(DatasetOperations, {'unique_id': MFID})

    with pytest.raises(ValueError, match='response-only'):
        operations.update(MFID, capabilities=CAPABILITIES)

    operations._request.assert_not_called()


@pytest.mark.parametrize('field', ['instrument', 'project'])
def test_dataset_update_rejects_response_references(field):
    operations = make_ops(DatasetOperations, {'unique_id': MFID})

    with pytest.raises(ValueError, match=field):
        operations.update(MFID, **{field: {}})

    operations._request.assert_not_called()


@pytest.mark.parametrize(
    ('operations_class', 'resource'),
    [
        (DatasetOperations, Dataset(unique_id=MFID, dataset_name='test', owner='roncofaber')),
        (SampleOperations, Sample(unique_id=MFID, sample_name='test', owner='roncofaber')),
    ],
)
def test_create_prefers_flexible_owner_without_warning(operations_class, resource):
    operations = make_ops(operations_class, {'unique_id': MFID})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        operations.create(resource)

    assert not caught
    assert operations._request.call_args.kwargs['json']['owner'] == 'roncofaber'


@pytest.mark.parametrize(
    ('operations_class', 'resource'),
    [
        (DatasetOperations, Dataset(unique_id=MFID, dataset_name='test', owner=PUBLIC_OWNER)),
        (SampleOperations, Sample(unique_id=MFID, sample_name='test', owner=PUBLIC_OWNER)),
    ],
)
def test_create_rejects_expanded_owner_record(operations_class, resource):
    operations = make_ops(operations_class, {'unique_id': MFID})

    with pytest.raises(ValueError, match='string identifier'):
        operations.create(resource)

    operations._request.assert_not_called()
