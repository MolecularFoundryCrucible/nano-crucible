"""Integration tests for client.samples.*"""

import os
import tempfile


def test_sample_list(client, project_id):
    samples = client.samples.list(project_id=project_id, limit=5)
    assert isinstance(samples, list)


def test_sample_count(client, project_id):
    n = client.samples.count(project_id=project_id)
    assert isinstance(n, int) and n >= 0


def test_sample_get(client, existing_sample):
    sid = existing_sample[0]['unique_id']
    s = client.samples.get(sid, include_metadata=True)
    assert s is not None
    assert s.get('unique_id') == sid


def test_sample_search(client, test_tag, project_id):
    results = client.samples.search(test_tag, project_id=project_id)
    assert isinstance(results, list)


def test_sample_search_metadata(client):
    results = client.samples.search_metadata('test', limit=5)
    assert isinstance(results, list)


def test_sample_list_parents(client, existing_sample):
    parents = client.samples.list_parents(existing_sample[0]['unique_id'])
    assert isinstance(parents, list)


def test_sample_list_children(client, existing_sample):
    children = client.samples.list_children(existing_sample[0]['unique_id'])
    assert isinstance(children, list)


def test_sample_list_datasets(client, existing_sample):
    datasets = client.datasets.list(sample_mfid=existing_sample[0]['unique_id'])
    assert isinstance(datasets, list)


def test_sample_graph(client, existing_sample):
    g = client.graphs.get(existing_sample[0]['unique_id'])
    assert isinstance(g, dict)


def test_sample_download(client, existing_sample):
    out = tempfile.mkdtemp()
    try:
        paths = client.samples.download(existing_sample[0]['unique_id'], output_dir=out)
        assert paths and os.path.exists(paths[0])
    finally:
        import shutil
        shutil.rmtree(out)


# ── create / update / link ────────────────────────────────────────────────────

def test_sample_create_and_update(client, project_id, test_tag):
    from crucible.models import Sample
    s = client.samples.create(Sample(
        sample_name=f'{test_tag}-create-test',
        project_id=project_id,
        sample_type='test',
    ))
    sid = s.get('unique_id')
    assert sid

    updated = client.samples.update(sid, description='updated by pytest')
    assert updated.get('description') == 'updated by pytest'


def test_sample_link_parent_child(client, project_id, test_tag):
    from crucible.models import Sample
    parent = client.samples.create(Sample(sample_name=f'{test_tag}-parent', project_id=project_id))
    child  = client.samples.create(Sample(sample_name=f'{test_tag}-child',  project_id=project_id))
    pid, cid = parent.get('unique_id'), child.get('unique_id')

    client.samples.link(pid, cid)
    children = client.samples.list_children(pid)
    assert any(s.get('unique_id') == cid for s in children)

    client.samples.unlink(pid, cid)
    children = client.samples.list_children(pid)
    assert not any(s.get('unique_id') == cid for s in children)


def test_sample_dataset_link(client, new_sample, new_dataset):
    client.datasets.link_sample(new_dataset, new_sample)
    linked = client.datasets.list(sample_mfid=new_sample)
    assert any(d.get('unique_id') == new_dataset for d in linked)

    client.datasets.unlink_sample(new_dataset, new_sample)
    linked = client.datasets.list(sample_mfid=new_sample)
    assert not any(d.get('unique_id') == new_dataset for d in linked)
