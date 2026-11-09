"""Unit coverage for file names, download safety, and storage error hints."""

import io
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from crucible.cli import helpers
from crucible.constants import GCS_BUCKET_PREFIX
from crucible.utils.io import safe_output_path, storage_display_name

DSID = '0tkn2knjast3h0008nyq9zps2c'


@pytest.mark.parametrize('path, filename, expected', [
    (f'{GCS_BUCKET_PREFIX}{DSID}/raw/scan.h5', 'scan.h5', 'raw/scan.h5'),
    (f'{GCS_BUCKET_PREFIX}{DSID}/_files/0abc', 'raw/scan.h5', 'raw/scan.h5'),
    (f'{GCS_BUCKET_PREFIX}{DSID}/_files/0abc', None, '_files/0abc'),
    (f'mf-crucible-multipart-staging/uploads/{DSID}/79c1/content',
     'spectral_libraries/nist_library.db', 'spectral_libraries/nist_library.db'),
])
def test_display_name_uses_the_record_filename_for_new_multipart_objects(path, filename, expected):
    record = {'storage_path': path, 'filename': filename, 'dataset_mfid': DSID}

    assert storage_display_name(record, DSID) == expected
    assert storage_display_name(record) == expected


@pytest.mark.parametrize('path', [f'{GCS_BUCKET_PREFIX}{DSID}/scan.h5', f'{GCS_BUCKET_PREFIX}{DSID}/_files/0abc'])
def test_display_name_reduces_an_absolute_legacy_filename(tmp_path, path):
    record = {'storage_path': path, 'filename': '/mnt/gcs/api-uploads/scan.h5', 'dataset_mfid': DSID}

    name = storage_display_name(record, DSID)

    assert name == 'scan.h5'
    assert safe_output_path(str(tmp_path), name) == str(tmp_path / 'scan.h5')


@pytest.mark.parametrize('name', ['../escape.txt', '/etc/passwd', 'a/../../b'])
def test_output_paths_cannot_leave_the_target_folder(tmp_path, name):
    with pytest.raises(ValueError, match='outside'):
        safe_output_path(str(tmp_path), name)


def test_output_paths_keep_subfolders(tmp_path):
    assert safe_output_path(str(tmp_path), 'raw/scan.h5') == str(tmp_path / 'raw' / 'scan.h5')


def test_bulk_download_warns_about_files_without_a_link(tmp_path, caplog):
    from crucible.resources.gcs.download import download_dataset_files

    files = [{'mfid': 'f1', 'storage_backend': 'gcs',
              'storage_path': f'{GCS_BUCKET_PREFIX}{DSID}/a.txt'}]
    with caplog.at_level(logging.WARNING):
        result = download_dataset_files(MagicMock(), DSID, str(tmp_path), {'f1': None}, files)

    assert result == []
    assert "Skipping 'a.txt'" in caplog.text


def http_error(status, detail):
    response = SimpleNamespace(status_code=status, reason='Reason', text='',
                               json=lambda: {'detail': detail})
    return requests.HTTPError(response=response)


@pytest.mark.parametrize('status, detail, fragment', [
    (409, {'code': 'storage_location_invalid', 'reason': 'outside_dataset',
           'message': 'File storage location is not valid: outside_dataset'}, 'stored location'),
    (422, 'storage_path is assigned by the upload API for GCS files', 'set by the upload'),
    (422, 'size and sha256_hash are determined by the stored object for GCS files',
     'set by the upload'),
])
def test_storage_errors_carry_a_hint(status, detail, fragment):
    assert fragment in helpers.format_cli_error('x', http_error(status, detail))['hint']


@pytest.mark.parametrize('call, endpoint', [
    (lambda c: c.files.get_download_link('f1', disposition='inline'), '/files/f1/download_link'),
    (lambda c: c.datasets.get_download_links(DSID, disposition='inline'),
     f'/datasets/{DSID}/download_links'),
])
def test_download_links_accept_a_disposition(call, endpoint):
    from crucible.resources.datasets import DatasetOperations
    from crucible.resources.files import FileOperations

    client = MagicMock()
    client._request.return_value = {'url': 'u', 'f1': 'u'}
    client.files = FileOperations(client)
    client.datasets = DatasetOperations(client)

    call(client)

    args, kwargs = client._request.call_args
    assert args[1] == endpoint
    assert kwargs['params'] == {'disposition': 'inline'}


def test_signed_url_downloads_never_send_the_api_key(tmp_path, monkeypatch):
    from crucible.client import CrucibleClient
    from crucible.resources.gcs.download import download_dataset_files

    sent = []

    def send(adapter, request, **kwargs):
        sent.append(request)
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(b'data')
        response.url = request.url
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', send)
    client = CrucibleClient('https://example.test/api/v3', 'secret-key')
    files = [{'mfid': 'f1', 'storage_backend': 'gcs',
              'storage_path': f'{GCS_BUCKET_PREFIX}{DSID}/a.txt'}]

    download_dataset_files(client, DSID, str(tmp_path),
                           {'f1': 'https://storage.example.test/a.txt?sig=x'}, files)

    assert (tmp_path / 'a.txt').read_bytes() == b'data'
    assert [r.url for r in sent] == ['https://storage.example.test/a.txt?sig=x']
    assert 'Authorization' not in sent[0].headers
    api_request = client._session.prepare_request(
        requests.Request('GET', 'https://example.test/api/v3/account'))
    assert api_request.headers['Authorization'] == 'Bearer secret-key'


def test_file_download_uses_the_unauthenticated_storage_session(tmp_path):
    from crucible.resources.files import FileOperations

    client = MagicMock()
    operations = FileOperations(client)
    operations.get = MagicMock(return_value={
        'storage_backend': 'gcs', 'filename': 'a.txt',
        'storage_path': f'{GCS_BUCKET_PREFIX}{DSID}/a.txt'})
    operations.get_download_link = MagicMock(return_value='https://storage.example.test/a')
    client._storage_session.get.return_value.iter_content.return_value = [b'data']

    operations.download('f1', output_dir=str(tmp_path))

    client._storage_session.get.assert_called_once_with('https://storage.example.test/a', stream=True)
    client._session.get.assert_not_called()
