"""Unit coverage for waiting on ingestion: callers get the terminal record."""

from unittest.mock import MagicMock

from crucible.resources.datasets import DatasetOperations
from crucible.resources.files import FileOperations

TERMINAL = {'id': 7, 'status': 'complete'}


def test_request_ingestion_returns_the_waited_record():
    client = MagicMock()
    client._request.return_value = {'id': 7, 'status': 'requested'}
    client._wait_for_request_completion.return_value = TERMINAL

    result = FileOperations(client).request_ingestion('F', wait_for_response=True)

    assert result == TERMINAL
    client._wait_for_request_completion.assert_called_once_with(7)


def test_request_ingestion_without_waiting_returns_the_new_request():
    client = MagicMock()
    client._request.return_value = {'id': 7, 'status': 'requested'}

    result = FileOperations(client).request_ingestion('F')

    assert result['status'] == 'requested'
    client._wait_for_request_completion.assert_not_called()


def test_create_reports_the_waited_ingestion_records(monkeypatch):
    from crucible.models import Dataset

    client = MagicMock()
    client.ingestions.wait.return_value = TERMINAL
    datasets = DatasetOperations(client)
    monkeypatch.setattr(datasets, '_request', MagicMock(return_value={'unique_id': 'D' * 26}))
    monkeypatch.setattr(datasets, 'add_file', MagicMock(return_value={
        'associated_file': {'mfid': 'F'}, 'ingestion_request': {'id': 7, 'status': 'requested'}}))

    result = datasets.create(Dataset(dataset_name='n', project_id='p'), files=['a.txt'],
                             wait_for_ingestion_response=True)

    assert result['files'][0]['ingestion_request'] == TERMINAL
