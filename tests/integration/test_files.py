"""Integration tests for file upload, download, and ingestion."""

import pytest


def test_file_list_global(client):
    files = client.files.list(limit=5)
    assert isinstance(files, list)


def test_dataset_list_files(client, new_dataset):
    files = client.datasets.list_files(new_dataset)
    assert isinstance(files, list)


def test_dataset_get_download_links(client, new_dataset):
    link_map = client.datasets.get_download_links(new_dataset)
    assert isinstance(link_map, dict)


def test_file_upload(client, new_dataset, tmp_file):
    result = client.datasets.add_file(new_dataset, tmp_file)
    af = result.get('associated_file', {})
    assert af.get('mfid'), "upload must return a file mfid"


@pytest.fixture(scope='module')
def uploaded_file(client, new_dataset):
    """Upload a file and return its mfid for use by other tests in this module."""
    import os, tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
    tmp.write(os.urandom(1024 * 8))
    tmp.close()
    try:
        result = client.datasets.add_file(new_dataset, tmp.name)
        return result.get('associated_file', {}).get('mfid')
    except Exception:
        return None
    finally:
        os.unlink(tmp.name)


def test_file_get(client, uploaded_file):
    if not uploaded_file:
        pytest.skip("upload failed")
    f = client.files.get(uploaded_file)
    assert f.get('mfid') == uploaded_file


def test_file_get_download_link(client, uploaded_file):
    if not uploaded_file:
        pytest.skip("upload failed")
    f = client.files.get(uploaded_file)
    if not f.get('storage_path'):
        pytest.skip("file not yet ingested")
    url = client.files.get_download_link(uploaded_file)
    assert url.startswith('https://')


def test_file_download(client, uploaded_file, tmp_path):
    if not uploaded_file:
        pytest.skip("upload failed")
    f = client.files.get(uploaded_file)
    if not f.get('storage_path'):
        pytest.skip("file not yet ingested")
    path = client.files.download(uploaded_file, output_dir=str(tmp_path))
    assert (tmp_path / path.split('/')[-1]).exists()


def test_ingestion_list_by_dataset(client, new_dataset):
    reqs = client.ingestions.list(dsid=new_dataset)
    assert isinstance(reqs, list)


def test_ingestion_list_by_file(client, uploaded_file):
    if not uploaded_file:
        pytest.skip("upload failed")
    reqs = client.ingestions.list(file_id=uploaded_file)
    assert isinstance(reqs, list)


def test_ingestion_get(client, new_dataset):
    reqs = client.ingestions.list(dsid=new_dataset)
    if not reqs:
        pytest.skip("no ingestion requests available")
    r = client.ingestions.get(reqs[0]['id'])
    assert r.get('id') == reqs[0]['id']
