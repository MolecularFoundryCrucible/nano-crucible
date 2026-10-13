"""Creating a record adds its first metadata with POST, which needs only CREATE.

A merging PATCH needs EDIT on the record, which a platform contributor
creating on someone else's behalf does not hold.
"""

from unittest.mock import MagicMock

import pytest

from crucible.models import Dataset, Sample
from crucible.resources.datasets import DatasetOperations
from crucible.resources.instruments import InstrumentOperations
from crucible.resources.projects import ProjectOperations
from crucible.resources.samples import SampleOperations

MFID = '0tkn2knjast3h0008nyq9zps2c'
METADATA = {'temperature': 300}


def metadata_calls(client):
    return [c for c in client._request.call_args_list if '/metadata' in str(c.args[1])]


def respond(record):
    def request(method, path, **kwargs):
        if method == 'get':
            return {'items': [], 'total': 0, 'next_cursor': None}
        return dict(record) if method == 'post' and '/metadata' not in path else {}
    return request


@pytest.mark.parametrize('create', [
    lambda c: DatasetOperations(c).create(Dataset(dataset_name='n', project_id='p', owner='alice'),
                                          scientific_metadata=METADATA),
    lambda c: SampleOperations(c).create(Sample(sample_name='n', project_id='p', owner='alice'),
                                         scientific_metadata=METADATA),
])
def test_create_posts_the_first_metadata(create):
    client = MagicMock()
    client._request.side_effect = respond({'unique_id': MFID})

    create(client)

    (call,) = metadata_calls(client)
    assert call.args == ('post', f'/resources/{MFID}/metadata')
    assert call.kwargs['json'] == METADATA
    assert 'params' not in call.kwargs


def test_project_and_instrument_create_post_the_first_metadata(monkeypatch):
    for operations, kwargs in ((ProjectOperations, dict(project_id='proj-a', title='t', organization='o',
                                                         project_lead_orcid='0000-0001-0000-0000')),
                               (InstrumentOperations, dict(instrument_id='inst', instrument_name='Inst'))):
        client = MagicMock()
        client._request.side_effect = respond({'unique_id': MFID, 'project_id': 'p', 'instrument_id': 'inst'})
        ops = operations(client)
        monkeypatch.setattr(ops, '_resource_mfid', lambda ref: MFID)
        if hasattr(ops, 'get'):
            monkeypatch.setattr(ops, 'get', lambda *a, **k: None, raising=False)

        ops.create(kwargs, scientific_metadata=METADATA)

        methods = [c.args[0] for c in metadata_calls(client)]
        assert methods == ['post'], operations.__name__
