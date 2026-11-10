"""
Shared pytest fixtures for nano-crucible integration tests.

These tests write to a live Crucible API. They run only when both
CRUCIBLE_TEST_API_URL (use staging, never production) and
CRUCIBLE_TEST_API_KEY are set; otherwise every test is skipped.

Run all:        pytest tests/integration/
Run one module: pytest tests/integration/test_datasets.py -v
"""

import os
import tempfile

import pytest

PROJECT_ID = 'crucible-test'
TEST_TAG   = 'v3-client-test'


@pytest.fixture(scope='session')
def client():
    from crucible.client import CrucibleClient
    api_url = os.environ.get('CRUCIBLE_TEST_API_URL')
    api_key = os.environ.get('CRUCIBLE_TEST_API_KEY')
    if not api_url or not api_key:
        pytest.skip("set CRUCIBLE_TEST_API_URL and CRUCIBLE_TEST_API_KEY to run integration tests")
    return CrucibleClient(api_url=api_url, api_key=api_key)


@pytest.fixture(scope='session')
def project_id():
    return PROJECT_ID


@pytest.fixture(scope='session')
def test_tag():
    return TEST_TAG


@pytest.fixture(scope='session')
def existing_dataset(client):
    datasets = client.datasets.list(project_id=PROJECT_ID, limit=1)
    if not datasets:
        pytest.skip("No existing datasets in crucible-test")
    return datasets[0]


@pytest.fixture(scope='session')
def existing_sample(client):
    samples = client.samples.list(project_id=PROJECT_ID, limit=2)
    if not samples:
        pytest.skip("No existing samples in crucible-test")
    return samples


@pytest.fixture(scope='session')
def new_dataset(client):
    """Create a dataset once for the session, reused across modules."""
    from crucible.models import Dataset
    result = client.datasets.create(Dataset(
        dataset_name=f'{TEST_TAG}-dataset',
        project_id=PROJECT_ID,
        measurement='test',
    ))
    return result.get('dataset_mfid')


@pytest.fixture(scope='session')
def new_sample(client):
    """Create a sample once for the session, reused across modules."""
    from crucible.models import Sample
    s = client.samples.create(Sample(
        sample_name=f'{TEST_TAG}-sample',
        project_id=PROJECT_ID,
        sample_type='test',
        description='Created by v3 client integration test',
    ))
    return s.get('unique_id')


@pytest.fixture
def tmp_file():
    """Yield a small random temp file path, delete after test."""
    tmp = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
    tmp.write(os.urandom(1024 * 8))
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except FileNotFoundError:
        pass
