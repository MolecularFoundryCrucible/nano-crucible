"""
Integration tests for scientific metadata operations on all resource types.

API behaviour:
- PATCH  /resources/{id}/metadata  → deep merge, creates if absent, always safe
- POST   /resources/{id}/metadata  → create (409 if exists); overwrite=true replaces
- GET    /resources/{id}/metadata  → {unique_id, scientific_metadata} or null (200)

Both PATCH and POST return {unique_id, scientific_metadata: dict}.
"""

import pytest


def _md(result):
    """Extract scientific_metadata dict from a resource response."""
    if result is None:
        return {}
    if isinstance(result, dict) and 'scientific_metadata' in result:
        return result.get('scientific_metadata') or {}
    return {}


# ── datasets ──────────────────────────────────────────────────────────────────

def test_dataset_patch_creates_if_absent(client, new_dataset):
    """PATCH always safe — creates metadata when none exists."""
    result = client.datasets.update_scientific_metadata(
        new_dataset, {'key': 'value', 'number': 42}
    )
    md = _md(result)
    assert md.get('key') == 'value'
    assert md.get('number') == 42


def test_dataset_patch_merges(client, new_dataset):
    """PATCH merges without losing existing keys."""
    client.datasets.update_scientific_metadata(new_dataset, {'a': 1})
    result = client.datasets.update_scientific_metadata(new_dataset, {'b': 2})
    md = _md(result)
    assert md.get('a') == 1
    assert md.get('b') == 2


def test_dataset_post_overwrite_replaces(client, new_dataset):
    """POST with overwrite=true replaces the entire metadata dict."""
    client.datasets.update_scientific_metadata(new_dataset, {'will_be_gone': True})
    result = client.datasets.replace_scientific_metadata(new_dataset, {'fresh_key': 'fresh'})
    md = _md(result)
    assert md.get('fresh_key') == 'fresh'
    assert 'will_be_gone' not in md


def test_dataset_post_conflicts_without_overwrite(client, project_id, test_tag):
    """POST without overwrite returns 409 when metadata already exists."""
    import requests
    from crucible.models import Dataset
    r = client.datasets.create(Dataset(
        dataset_name=f'{test_tag}-conflict-test', project_id=project_id
    ))
    dsid = r['dsid']
    # Create metadata first
    client.datasets.replace_scientific_metadata(dsid, {'first': True})
    # Second POST without overwrite should 409
    try:
        client.datasets._request('post', f'/resources/{dsid}/metadata',
                                  json={'second': True})
        pytest.fail("Expected 409 Conflict")
    except requests.exceptions.HTTPError as e:
        assert e.response.status_code == 409


def test_dataset_get_metadata(client, new_dataset):
    """GET returns {unique_id, scientific_metadata} after metadata exists."""
    client.datasets.update_scientific_metadata(new_dataset, {'readable': 'yes'})
    result = client.datasets.get_scientific_metadata(new_dataset)
    md = _md(result)
    assert md.get('readable') == 'yes'


def test_dataset_get_metadata_null_when_absent(client, project_id, test_tag):
    """GET should return null (200) for a resource with no metadata."""
    from crucible.models import Dataset
    r = client.datasets.create(Dataset(
        dataset_name=f'{test_tag}-no-meta', project_id=project_id
    ))
    result = client.datasets.get_scientific_metadata(r['dsid'])
    assert result is None or _md(result) == {}


def test_dataset_create_with_metadata(client, project_id, test_tag):
    """Datasets can be created with scientific_metadata in one call."""
    from crucible.models import Dataset
    result = client.datasets.create(
        Dataset(dataset_name=f'{test_tag}-meta-create', project_id=project_id),
        scientific_metadata={'created_with': 'one_call', 'value': 99},
    )
    dsid = result['dsid']
    r = client.datasets.get_scientific_metadata(dsid)
    md = _md(r)
    assert md.get('created_with') == 'one_call'
    assert md.get('value') == 99


# ── samples ───────────────────────────────────────────────────────────────────

def test_sample_patch_creates_and_merges(client, new_sample):
    result = client.samples.update_scientific_metadata(
        new_sample, {'sample_key': 'val', 'temp_k': 300}
    )
    md = _md(result)
    assert md.get('sample_key') == 'val'
    assert md.get('temp_k') == 300

    result = client.samples.update_scientific_metadata(new_sample, {'extra': 'added'})
    md = _md(result)
    assert md.get('sample_key') == 'val'
    assert md.get('extra') == 'added'


def test_sample_post_overwrite_replaces(client, new_sample):
    client.samples.update_scientific_metadata(new_sample, {'old': True})
    result = client.samples.replace_scientific_metadata(new_sample, {'new_only': 'fresh'})
    md = _md(result)
    assert md.get('new_only') == 'fresh'
    assert 'old' not in md


def test_sample_get_metadata(client, new_sample):
    client.samples.update_scientific_metadata(new_sample, {'check': 'value'})
    result = client.samples.get_scientific_metadata(new_sample)
    md = _md(result)
    assert md.get('check') == 'value'


# ── instruments ───────────────────────────────────────────────────────────────

def test_instrument_patch_metadata(client):
    instruments = client.instruments.list(limit=1)
    if not instruments:
        pytest.skip("no instruments available")
    iid = instruments[0].get('unique_id')
    try:
        result = client.instruments.update_scientific_metadata(
            iid, {'instrument_meta': 'test_value'}
        )
        md = _md(result)
        assert md.get('instrument_meta') == 'test_value'
    except Exception as e:
        if '403' in str(e):
            pytest.skip("no write access to instrument")
        raise


def test_instrument_get_metadata(client):
    instruments = client.instruments.list(limit=1)
    if not instruments:
        pytest.skip("no instruments available")
    iid = instruments[0].get('unique_id')
    try:
        client.instruments.update_scientific_metadata(iid, {'check': 'value'})
        result = client.instruments.get_scientific_metadata(iid)
        md = _md(result)
        assert md.get('check') == 'value'
    except Exception as e:
        if '403' in str(e):
            pytest.skip("no write access to instrument")
        raise


# ── public/private toggle ─────────────────────────────────────────────────────

def test_dataset_public_toggle(client, new_dataset):
    grant = client.datasets.set_public(new_dataset)
    assert grant.permission == 'viewer'
    client.datasets.set_private(new_dataset)


def test_sample_public_toggle(client, new_sample):
    grant = client.samples.set_public(new_sample)
    assert grant.permission == 'viewer'
    client.samples.set_private(new_sample)
