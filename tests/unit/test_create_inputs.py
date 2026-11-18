"""samples.create() and datasets.create() take a model or a dict, never loose fields."""

from unittest.mock import MagicMock

import pytest

from crucible import RemovedError
from crucible.models import Dataset, Sample
from crucible.resources.datasets import DatasetOperations
from crucible.resources.samples import SampleOperations

FIELDS = {'project_id': 'my-project', 'description': 'thin film'}


def _ops(operations_class, mfid):
    operations = operations_class(MagicMock())
    operations._request = MagicMock(return_value={'unique_id': mfid})
    return operations


def _first_body(operations):
    return operations._request.call_args_list[0].kwargs['json']


@pytest.mark.parametrize('operations_class, model, name_field, mfid', [
    (SampleOperations, Sample, 'sample_name', 'S' * 26),
    (DatasetOperations, Dataset, 'dataset_name', 'D' * 26),
])
def test_a_dict_sends_what_the_model_sends(operations_class, model, name_field, mfid):
    fields = {name_field: 'film-01', 'unique_id': mfid, **FIELDS}
    from_model, from_dict = _ops(operations_class, mfid), _ops(operations_class, mfid)

    from_model.create(model(**fields))
    from_dict.create(dict(fields))

    assert _first_body(from_dict) == _first_body(from_model)
    assert _first_body(from_dict)[name_field] == 'film-01'


def test_sample_create_still_refuses_loose_fields():
    operations = _ops(SampleOperations, 'S' * 26)

    with pytest.raises(RemovedError, match='as a Sample or a dict'):
        operations.create(sample_name='film-01', project_id='my-project')
    operations._request.assert_not_called()


@pytest.mark.parametrize('operations_class, wrong', [
    (SampleOperations, ['film-01']),
    (DatasetOperations, 'film-01'),
])
def test_other_types_raise_a_type_error(operations_class, wrong):
    operations = _ops(operations_class, 'X' * 26)

    with pytest.raises(TypeError, match='or a dict'):
        operations.create(wrong)
    operations._request.assert_not_called()


def test_a_dict_is_checked_like_the_model():
    operations = _ops(DatasetOperations, 'D' * 26)

    with pytest.raises(RemovedError, match='owner_orcid'):
        operations.create({'dataset_name': 't', 'owner_orcid': '0000-0001-6402-3752'})
    operations._request.assert_not_called()
