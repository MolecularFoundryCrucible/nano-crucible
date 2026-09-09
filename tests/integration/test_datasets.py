"""Integration tests for client.datasets.*"""

import pytest


def test_dataset_list(client, project_id):
    ds = client.datasets.list(project_id=project_id, limit=5)
    assert isinstance(ds, list)


def test_dataset_count(client, project_id):
    n = client.datasets.count(project_id=project_id)
    assert isinstance(n, int) and n >= 0


def test_dataset_get(client, existing_dataset):
    dsid = existing_dataset['unique_id']
    ds = client.datasets.get(dsid, include_metadata=True)
    assert ds is not None
    assert ds.get('unique_id') == dsid


def test_dataset_search(client, test_tag, project_id):
    results = client.datasets.search(test_tag, project_id=project_id)
    assert isinstance(results, list)


def test_dataset_search_metadata(client):
    results = client.datasets.search_metadata('test', limit=5)
    assert isinstance(results, list)


def test_dataset_get_keywords(client, existing_dataset):
    kw = client.datasets.get_keywords(existing_dataset['unique_id'])
    assert isinstance(kw, list)


def test_dataset_get_thumbnails(client, existing_dataset):
    thumbs = client.datasets.get_thumbnails(existing_dataset['unique_id'])
    assert isinstance(thumbs, list)


def test_dataset_list_parents(client, existing_dataset):
    parents = client.datasets.list_parents(existing_dataset['unique_id'])
    assert isinstance(parents, list)


def test_dataset_list_children(client, existing_dataset):
    children = client.datasets.list_children(existing_dataset['unique_id'])
    assert isinstance(children, list)


def test_dataset_graph(client, existing_dataset):
    g = client.graphs.get(existing_dataset['unique_id'])
    assert isinstance(g, dict)


def test_dataset_search_metadata_on_resource(client, existing_dataset):
    results = client.datasets.search_metadata('test', limit=5)
    assert isinstance(results, list)


# ── create / update ───────────────────────────────────────────────────────────

def test_dataset_create_and_update(client, project_id, test_tag):
    from crucible.models import Dataset
    result = client.datasets.create(Dataset(
        dataset_name=f'{test_tag}-create-test',
        project_id=project_id,
        measurement='test',
    ))
    dsid = result.get('dsid')
    assert dsid

    updated = client.datasets.update(dsid, session_name='pytest-session')
    assert updated.get('session_name') == 'pytest-session'


def test_dataset_add_keyword(client, new_dataset):
    client.datasets.add_keyword(new_dataset, 'pytest-keyword')
    kw = client.datasets.get_keywords(new_dataset)
    words = [k.get('keyword', k) if isinstance(k, dict) else k for k in kw]
    assert 'pytest-keyword' in words


def test_dataset_link_parent_child(client, project_id, test_tag):
    from crucible.models import Dataset
    parent = client.datasets.create(Dataset(dataset_name=f'{test_tag}-parent', project_id=project_id)).get('dsid')
    child  = client.datasets.create(Dataset(dataset_name=f'{test_tag}-child',  project_id=project_id)).get('dsid')

    client.datasets.link(parent, child)
    children = client.datasets.list_children(parent)
    assert any(d.get('unique_id') == child for d in children)

    client.datasets.remove_child(parent, child)
    children = client.datasets.list_children(parent)
    assert not any(d.get('unique_id') == child for d in children)
