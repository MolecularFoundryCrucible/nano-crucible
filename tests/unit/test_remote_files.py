"""Unit tests for remote (non-GCS) file records - mocked, no live API.

Unlike tests/integration/, these don't hit a real server: the feature under
test (AssociatedFile.storage_backend/access_note) is new server-side and may
not be deployed everywhere tests/integration/ points at.
"""

import hashlib

import pytest
import requests
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

    def test_with_storage_path_posts_once(self, dataset_ops):
        dataset_ops._request = MagicMock(
            return_value={'mfid': 'mf-1', 'storage_path': 'https://globus/x'})
        af = AssociatedFile(filename='x.dat', storage_backend='globus',
                            storage_path='https://globus/x')

        result = dataset_ops.add_remote_file('ds-1', af)

        assert dataset_ops._request.call_args.kwargs['json']['storage_path'] == 'https://globus/x'
        dataset_ops._client.files.update.assert_not_called()
        assert result['storage_path'] == 'https://globus/x'

    def test_repeat_with_new_location_patches_the_path(self, dataset_ops):
        dataset_ops._request = MagicMock(
            return_value={'mfid': 'mf-1', 'storage_path': 'https://globus/old'})
        dataset_ops._client.files.update = MagicMock(
            return_value={'mfid': 'mf-1', 'storage_path': 'https://globus/new'})
        af = AssociatedFile(filename='x.dat', storage_backend='globus',
                            storage_path='https://globus/new')

        result = dataset_ops.add_remote_file('ds-1', af)

        dataset_ops._client.files.update.assert_called_once_with(
            'mf-1', storage_path='https://globus/new')
        assert result['storage_path'] == 'https://globus/new'

    @staticmethod
    def _conflict(code='filename_exists'):
        response = MagicMock(status_code=409)
        response.json.return_value = {'detail': {
            'code': code, 'file_mfid': 'mf-old', 'etag': '"e"', 'message': 'Filename already exists'}}
        return requests.exceptions.HTTPError('409 Conflict', response=response)

    def test_conflict_raises_without_replace(self, dataset_ops):
        dataset_ops._client.replace_existing = False
        dataset_ops._request = MagicMock(side_effect=self._conflict())
        af = AssociatedFile(filename='x.dat', storage_backend='globus', size=3, sha256_hash='b')

        with pytest.raises(requests.exceptions.HTTPError):
            dataset_ops.add_remote_file('ds-1', af)

        dataset_ops._client.files.update.assert_not_called()

    @pytest.mark.parametrize('flag', ['argument', 'client'])
    def test_conflict_with_replace_updates_the_existing_record(self, dataset_ops, flag):
        dataset_ops._client.replace_existing = flag == 'client'
        dataset_ops._request = MagicMock(side_effect=self._conflict())
        dataset_ops._client.files.update = MagicMock(return_value={'mfid': 'mf-old'})
        af = AssociatedFile(filename='x.dat', storage_backend='globus', size=3,
                            sha256_hash='b', storage_path='https://globus/x',
                            access_note='ask')

        result = dataset_ops.add_remote_file('ds-1', af, replace=flag == 'argument')

        dataset_ops._client.files.update.assert_called_once_with(
            'mf-old', storage_path='https://globus/x', storage_backend='globus',
            access_note='ask', size=3, sha256_hash='b')
        assert result == {'mfid': 'mf-old'}

    def test_replace_does_not_swallow_other_conflicts(self, dataset_ops):
        dataset_ops._request = MagicMock(side_effect=self._conflict('something_else'))
        af = AssociatedFile(filename='x.dat', storage_backend='globus')

        with pytest.raises(requests.exceptions.HTTPError):
            dataset_ops.add_remote_file('ds-1', af, replace=True)


class TestFromLocalFiles:
    def test_names_files_relative_to_their_common_folder(self, tmp_path):
        for folder in ('freq_001', 'freq_002'):
            (tmp_path / folder).mkdir()
            (tmp_path / folder / 'kpoints.json').write_text(folder)

        records = AssociatedFile.from_local_files(
            [str(tmp_path / 'freq_001' / 'kpoints.json'),
             str(tmp_path / 'freq_002' / 'kpoints.json')],
            storage_backend='nersc', access_note='ask')

        assert [r.filename for r in records] == ['freq_001/kpoints.json', 'freq_002/kpoints.json']
        assert records[0].storage_path == str((tmp_path / 'freq_001' / 'kpoints.json').resolve())
        assert records[0].size == len('freq_001')
        assert records[0].sha256_hash == hashlib.sha256(b'freq_001').hexdigest()
        assert {r.storage_backend for r in records} == {'nersc'}
        assert {r.access_note for r in records} == {'ask'}

    def test_a_single_file_is_named_by_its_basename(self, tmp_path):
        f = tmp_path / 'data.csv'
        f.write_text('a')

        assert AssociatedFile.from_local_files([str(f)])[0].filename == 'data.csv'

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            AssociatedFile.from_local_files([str(tmp_path / 'missing.dat')])


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

    def test_str_upload_false_catalogs_with_hash_and_relative_name(self, dataset_ops, tmp_path):
        f = tmp_path / 'data.csv'
        f.write_text('a,b,c')
        dataset_ops._request = MagicMock(return_value={'unique_id': 'ds-1'})
        dataset_ops.add_file = MagicMock()
        dataset_ops.add_remote_file = MagicMock(return_value={'mfid': 'mf-3'})

        dataset_ops.create(Dataset(dataset_name='t'), files=[str(f)], upload_files=False)

        dataset_ops.add_file.assert_not_called()
        dataset_ops.add_remote_file.assert_called_once()
        _, remote = dataset_ops.add_remote_file.call_args.args
        assert remote.filename == 'data.csv'
        assert remote.storage_backend == 'local'
        assert remote.storage_path == str(f.resolve())
        assert remote.size == f.stat().st_size
        assert remote.sha256_hash == hashlib.sha256(b'a,b,c').hexdigest()

    def test_str_upload_false_missing_file_fails_before_creating(self, dataset_ops, tmp_path):
        dataset_ops._request = MagicMock()

        with pytest.raises(FileNotFoundError):
            dataset_ops.create(Dataset(dataset_name='t'),
                               files=[str(tmp_path / 'missing.csv')], upload_files=False)

        dataset_ops._request.assert_not_called()

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




