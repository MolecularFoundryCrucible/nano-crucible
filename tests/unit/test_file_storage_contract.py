"""Unit coverage for file names, download safety, and storage error hints."""

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
