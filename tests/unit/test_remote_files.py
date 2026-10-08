"""Unit tests for remote (non-GCS) file records - mocked, no live API.

Unlike tests/integration/, these don't hit a real server: the feature under
test (AssociatedFile.storage_backend/access_note) is new server-side and may
not be deployed everywhere tests/integration/ points at.
"""

import warnings

import pytest
from unittest.mock import MagicMock

from crucible.models import AssociatedFile, Dataset
from crucible.resources.datasets import DatasetOperations
from crucible.resources.files import FileOperations


@pytest.fixture
def dataset_ops():
    client = MagicMock()
    ops = DatasetOperations(client)
    ops._client = client
    client.files._parse.side_effect = lambda x: x
    return ops


@pytest.fixture
def file_ops():
    client = MagicMock()
    ops = FileOperations(client)
    ops._client = client
    return ops


class TestAssociatedFileModel:
    def test_defaults(self):
        af = AssociatedFile(filename='x.dat')
        assert af.storage_backend == 'gcs'
        assert af.access_note is None

    def test_preserves_new_fields_and_extra(self):
        af = AssociatedFile.model_validate({
            'filename': 'x.dat', 'storage_backend': 'globus',
            'access_note': 'ask NERSC', 'some_future_field': 'value',
        })
        dumped = af.model_dump()
        assert dumped['storage_backend'] == 'globus'
        assert dumped['access_note'] == 'ask NERSC'
        assert dumped['some_future_field'] == 'value'  # extra='allow'


class TestAddRemoteFile:
    def test_rejects_gcs_backend(self, dataset_ops):
        af = AssociatedFile(filename='x.dat', storage_backend='gcs')
        with pytest.raises(ValueError):
            dataset_ops.add_remote_file('ds-1', af)

    def test_rejects_missing_backend(self, dataset_ops):
        af = AssociatedFile(filename='x.dat', storage_backend=None)
        with pytest.raises(ValueError):
            dataset_ops.add_remote_file('ds-1', af)

    def test_without_storage_path_only_posts(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'mfid': 'mf-1'})
        af = AssociatedFile(filename='x.dat', storage_backend='globus')

        result = dataset_ops.add_remote_file('ds-1', af)

        dataset_ops._request.assert_called_once()
        method, endpoint = dataset_ops._request.call_args.args
        assert (method, endpoint) == ('post', '/datasets/ds-1/files')
        assert 'storage_path' not in dataset_ops._request.call_args.kwargs['json']
        dataset_ops._client.files.update.assert_not_called()
        assert result == {'mfid': 'mf-1'}

    def test_with_storage_path_posts_then_patches(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'mfid': 'mf-1'})
        dataset_ops._client.files.update = MagicMock(
            return_value={'mfid': 'mf-1', 'storage_path': 'https://globus/x'})
        af = AssociatedFile(filename='x.dat', storage_backend='globus',
                            storage_path='https://globus/x')

        result = dataset_ops.add_remote_file('ds-1', af)

        assert 'storage_path' not in dataset_ops._request.call_args.kwargs['json']
        dataset_ops._client.files.update.assert_called_once_with(
            'mf-1', storage_path='https://globus/x')
        assert result['storage_path'] == 'https://globus/x'


class TestCreateFilesDispatch:
    def test_str_upload_true_uses_add_file(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock(return_value={'associated_file': {'mfid': 'mf-1'}})

        result = dataset_ops.create(Dataset(dataset_name='t'), files=['local.dat'])

        dataset_ops.add_file.assert_called_once()
        assert result['dataset_mfid'] == 'ds-1'
        assert result['dsid'] == 'ds-1'
        assert result['files'] == [{'associated_file': {'mfid': 'mf-1'}}]

    def test_associated_file_always_uses_add_remote_file(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock()
        dataset_ops.add_remote_file = MagicMock(return_value={'mfid': 'mf-2'})
        af = AssociatedFile(filename='r.dat', storage_backend='globus')

        result = dataset_ops.create(Dataset(dataset_name='t'), files=[af], upload_files=True)

        dataset_ops.add_file.assert_not_called()
        dataset_ops.add_remote_file.assert_called_once_with('ds-1', af)
        assert result['files'] == [{'mfid': 'mf-2'}]

    def test_str_upload_false_catalogs_by_absolute_path(self, dataset_ops, tmp_path):
        f = tmp_path / 'data.csv'
        f.write_text('a,b,c')
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock()
        dataset_ops.add_remote_file = MagicMock(return_value={'mfid': 'mf-3'})

        dataset_ops.create(Dataset(dataset_name='t'), files=[str(f)], upload_files=False)

        dataset_ops.add_file.assert_not_called()
        dataset_ops.add_remote_file.assert_called_once()
        _, remote = dataset_ops.add_remote_file.call_args.args
        assert remote.storage_backend == 'local'
        assert remote.storage_path == str(f.resolve())
        assert remote.size == f.stat().st_size

    def test_mixed_str_and_associated_file(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock(return_value={'associated_file': {'mfid': 'mf-local'}})
        dataset_ops.add_remote_file = MagicMock(return_value={'mfid': 'mf-remote'})
        af = AssociatedFile(filename='r.dat', storage_backend='globus')

        result = dataset_ops.create(Dataset(dataset_name='t'), files=['local.dat', af])

        assert result['files'] == [
            {'associated_file': {'mfid': 'mf-local'}},
            {'mfid': 'mf-remote'},
        ]

    def test_files_to_upload_still_works_with_deprecation_warning(self, dataset_ops):
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock(return_value={'associated_file': {}})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            dataset_ops.create(Dataset(dataset_name='t'), files_to_upload=['a.dat'])

        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        dataset_ops.add_file.assert_called_once()

    def test_files_and_files_to_upload_together_raises(self, dataset_ops):
        with pytest.raises(ValueError):
            dataset_ops.create(Dataset(dataset_name='t'), files=['a'], files_to_upload=['b'])


class TestFileDownloadNonGcs:
    def test_raises_clear_error_for_non_gcs(self, file_ops):
        file_ops.get = MagicMock(return_value={
            'mfid': 'mf-1', 'storage_backend': 'globus',
            'storage_path': 'https://globus/x', 'access_note': 'ask NERSC',
        })

        with pytest.raises(RuntimeError, match="globus"):
            file_ops.download('mf-1')

    def test_gcs_not_yet_ingested_still_raises_as_before(self, file_ops):
        file_ops.get = MagicMock(return_value={
            'mfid': 'mf-1', 'storage_backend': 'gcs', 'storage_path': None,
        })

        with pytest.raises(RuntimeError, match="not been ingested"):
            file_ops.download('mf-1')

    def test_missing_storage_backend_defaults_to_gcs(self, file_ops):
        """Records from before this field existed shouldn't be misclassified."""
        file_ops.get = MagicMock(return_value={'mfid': 'mf-1', 'storage_path': None})

        with pytest.raises(RuntimeError, match="not been ingested"):
            file_ops.download('mf-1')


def test_create_warns_when_only_instrument_name_identifies_the_instrument():
    import warnings
    from unittest.mock import MagicMock
    from crucible.models import Dataset
    from crucible.resources.datasets import DatasetOperations

    ops = DatasetOperations(MagicMock())
    ops._request = MagicMock(return_value={'unique_id': 'D' * 26})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        ops.create(Dataset(dataset_name='x', instrument_name='Titan'))
        ops.create(Dataset(dataset_name='y', instrument_name='Titan', instrument_id='titan'))

    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert sum('instrument_name' in m for m in messages) == 1


def test_list_warns_on_instrument_name_filter():
    import pytest
    from unittest.mock import MagicMock
    from crucible.resources.datasets import DatasetOperations

    ops = DatasetOperations(MagicMock())
    ops._paginate = MagicMock(return_value=[])
    with pytest.warns(DeprecationWarning, match='instrument_name'):
        ops.list(instrument_name='Titan')
