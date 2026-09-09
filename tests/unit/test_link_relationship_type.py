"""Unit coverage for link relationship_type and the renamed 'direction' field.

Links are stored parent -> child. 'direction' says which end of that edge a
linked resource is *relative to the one you asked about*, so it is computed
per query and flips depending on which end you read from. 'relationship_type'
is stored on the link row and is always oriented child-relative-to-parent.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import dataset as dataset_cli
from crucible.cli import link as link_cli
from crucible.cli import sample as sample_cli
from crucible.constants import RELATIONSHIP_TYPES
from crucible.resources.datasets import DatasetOperations
from crucible.resources.samples import SampleOperations


PARENT = '0tkn2knjast3h0008nyq9zps2c'
CHILD = '0td7evvtg5wb90005k1j97ak94'


def _dataset_ops():
    client = MagicMock()
    ops = DatasetOperations(client)
    ops._request = MagicMock(return_value={})
    return ops


def _sample_ops():
    client = MagicMock()
    ops = SampleOperations(client)
    ops._request = MagicMock(return_value={})
    return ops


# ── Write path ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('relationship_type', RELATIONSHIP_TYPES)
def test_dataset_link_sends_relationship_type(relationship_type):
    ops = _dataset_ops()
    ops.link(PARENT, CHILD, relationship_type)
    ops._request.assert_called_once_with(
        'post', f'/datasets/{PARENT}/children/{CHILD}',
        params={'relationship_type': relationship_type})


@pytest.mark.parametrize('relationship_type', RELATIONSHIP_TYPES)
def test_sample_link_sends_relationship_type(relationship_type):
    ops = _sample_ops()
    ops.link(PARENT, CHILD, relationship_type)
    ops._request.assert_called_once_with(
        'post', f'/samples/{PARENT}/children/{CHILD}',
        params={'relationship_type': relationship_type})


@pytest.mark.parametrize('call', [
    lambda: _dataset_ops(),
    lambda: _sample_ops(),
])
def test_link_without_type_sends_no_params(call):
    """A bare re-link must not send relationship_type at all.

    The server overwrites the stored type with whatever it is given, so
    sending the parameter unconditionally would blank an existing type on a
    re-link that only meant "make sure this link exists".
    """
    ops = call()
    if isinstance(ops, DatasetOperations):
        ops.link(PARENT, CHILD)
    else:
        ops.link(PARENT, CHILD)
    _, kwargs = ops._request.call_args
    assert 'params' not in kwargs


# ── Read/filter path ──────────────────────────────────────────────────────────

def test_list_children_filters_by_relationship_type():
    ops = _dataset_ops()
    ops._paginate = MagicMock(return_value=[])
    ops.list_children(PARENT, relationship_type='is_part_of')
    params = ops._paginate.call_args[0][1]
    assert params['relationship_type'] == 'is_part_of'


def test_list_parents_omits_filter_when_unset():
    ops = _sample_ops()
    ops._paginate = MagicMock(return_value=[])
    ops.list_parents(CHILD)
    params = ops._paginate.call_args[0][1]
    assert 'relationship_type' not in params


# ── client.link() dispatch ────────────────────────────────────────────────────

def _client_with_types(parent_type, child_type):
    from crucible.client import CrucibleClient

    client = CrucibleClient.__new__(CrucibleClient)
    client.get_resource_type = lambda mfid: (
        parent_type if mfid == PARENT else child_type)
    client.datasets = MagicMock()
    client.samples = MagicMock()
    return client


def test_client_link_forwards_type_to_datasets():
    client = _client_with_types('dataset', 'dataset')
    client.link(PARENT, CHILD, 'is_derived_from')
    client.datasets.link.assert_called_once_with(
        PARENT, CHILD, 'is_derived_from')


def test_client_link_forwards_type_to_samples():
    client = _client_with_types('sample', 'sample')
    client.link(PARENT, CHILD, 'is_part_of')
    client.samples.link.assert_called_once_with(PARENT, CHILD, 'is_part_of')


def test_client_link_rejects_type_on_dataset_sample_pair():
    """A dataset/sample association is undirected, so no type applies."""
    client = _client_with_types('dataset', 'sample')
    with pytest.raises(ValueError, match='relationship_type'):
        client.link(PARENT, CHILD, 'is_part_of')
    client.datasets.add_sample.assert_not_called()


def test_client_link_allows_dataset_sample_pair_without_type():
    client = _client_with_types('dataset', 'sample')
    client.link(PARENT, CHILD)
    client.datasets.link_sample.assert_called_once_with(PARENT, CHILD)


def test_get_links_adds_legacy_relationship_alias():
    client = _client_with_types('dataset', 'dataset')
    client._request = MagicMock(return_value=[
        {'unique_id': CHILD, 'direction': 'target'},
        {'unique_id': PARENT, 'direction': 'source'},
    ])

    links = client.get_links(PARENT)

    assert [link['relationship'] for link in links] == ['child', 'parent']


def test_get_links_normalizes_legacy_relationship_response():
    client = _client_with_types('dataset', 'sample')
    client._request = MagicMock(return_value=[
        {'unique_id': CHILD, 'relationship': 'associated'},
    ])

    links = client.get_links(PARENT)

    assert links[0]['direction'] == 'undirected'


# ── CLI ───────────────────────────────────────────────────────────────────────

def test_cli_link_rejects_type_for_sample_to_dataset(caplog):
    args = SimpleNamespace(dataset=PARENT, sample=CHILD, parent=None, child=None,
                           relationship_type='is_part_of')
    with pytest.raises(SystemExit) as exc:
        link_cli.execute(args)
    assert exc.value.code == 1
    assert '--relationship-type' in caplog.text


@pytest.mark.parametrize(('module', 'resource'), [
    (dataset_cli, 'datasets'),
    (sample_cli, 'samples'),
])
def test_cli_link_passes_type_through(module, resource, monkeypatch):
    client = MagicMock()
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda *a, **k: client)
    args = SimpleNamespace(parent=PARENT, child=CHILD,
                           relationship_type='is_derived_from', json=False)
    module._execute_link(args)
    method = (client.datasets.link if resource == 'datasets'
              else client.samples.link)
    method.assert_called_once_with(PARENT, CHILD, 'is_derived_from')


@pytest.mark.parametrize(('module', 'namespace', 'id_attr'), [
    (dataset_cli, 'datasets', 'dataset_id'),
    (sample_cli, 'samples', 'sample_id'),
])
@pytest.mark.parametrize('which', ['list_parents', 'list_children'])
def test_cli_listings_forward_relationship_type(module, namespace, id_attr,
                                                which, monkeypatch):
    client = MagicMock()
    getattr(getattr(client, namespace), which).return_value = []
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda *a, **k: client)

    args = SimpleNamespace(**{id_attr: PARENT}, limit=100,
                           relationship_type='is_part_of', json=False)
    getattr(module, f'_execute_{which}')(args)

    getattr(getattr(client, namespace), which).assert_called_once_with(
        PARENT, limit=100, relationship_type='is_part_of')


def test_cli_listing_flag_is_optional(monkeypatch):
    """Omitting the flag passes None, which the client turns into no filter."""
    client = MagicMock()
    client.datasets.list_children.return_value = []
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda *a, **k: client)

    dataset_cli._execute_list_children(
        SimpleNamespace(dataset_id=PARENT, limit=100,
                        relationship_type=None, json=False))

    client.datasets.list_children.assert_called_once_with(
        PARENT, limit=100, relationship_type=None)


# ── Display ───────────────────────────────────────────────────────────────────

def _links(peer_type):
    return [
        {'unique_id': 'p1', 'resource_type': peer_type, 'name': 'Parent',
         'direction': 'source', 'relationship_type': 'is_derived_from'},
        {'unique_id': 'c1', 'resource_type': peer_type, 'name': 'Child',
         'direction': 'target', 'relationship_type': None},
    ]


def test_direction_partitions_links_for_dataset_display(capsys):
    """'source' is a parent of the queried dataset, 'target' a child."""
    links = _links('dataset') + [
        {'unique_id': 's1', 'resource_type': 'sample', 'name': 'Samp',
         'direction': 'undirected', 'relationship_type': None},
    ]
    dataset_cli._show_dataset({'unique_id': PARENT, 'dataset_name': 'D'},
                              client=MagicMock(), graph=True, links=links)
    out = capsys.readouterr().out
    assert 'Parents (1)' in out
    assert 'Children (1)' in out
    assert 'Linked Samples (1)' in out
    # Type shown where stored, dim dash where the link predates typing.
    assert 'is_derived_from' in out
    assert '—' in out


def test_direction_partitions_links_for_sample_display(capsys):
    """'source' is a parent of the queried sample, 'target' a child."""
    links = _links('sample') + [
        {'unique_id': 'd1', 'resource_type': 'dataset', 'name': 'Data',
         'direction': 'undirected', 'relationship_type': None},
    ]
    sample_cli._show_sample({'unique_id': PARENT, 'sample_name': 'S'},
                            client=MagicMock(), graph=True, links=links)
    out = capsys.readouterr().out
    assert 'Parents (1)' in out
    assert 'Children (1)' in out
    assert 'Linked Datasets (1)' in out
    assert 'is_derived_from' in out


def test_tree_annotates_only_real_edges(capsys):
    """A contracted edge spans several links, so it must not claim a type.

    'tree' hides off-type nodes and promotes their children to the nearest
    visible parent. The resulting a -> c pair is not a stored link, so no
    single relationship_type describes it.
    """
    from crucible.cli import tree as tree_cli

    nodes_by_id = {
        'a': {'id': 'a', 'entity_type': 'dataset', 'name': 'A'},
        'b': {'id': 'b', 'entity_type': 'dataset', 'name': 'B'},
        'c': {'id': 'c', 'entity_type': 'dataset', 'name': 'C'},
    }
    adj = {'a': ['b', 'c'], 'b': [], 'c': []}
    link_types = {('a', 'b'): 'is_part_of'}  # a -> c was contracted, so absent

    tree_cli._print_node('b', nodes_by_id, adj, depth=1, max_depth=None,
                         visited=set(), project_id=None, base_url=None,
                         link_types=link_types, parent_id='a')
    tree_cli._print_node('c', nodes_by_id, adj, depth=1, max_depth=None,
                         visited=set(), project_id=None, base_url=None,
                         link_types=link_types, parent_id='a')
    out = capsys.readouterr().out
    b_line, c_line = [l for l in out.splitlines() if l.strip()]
    assert 'is_part_of' in b_line
    assert 'is_part_of' not in c_line


def test_format_relationship_type_renders_dash_when_absent():
    from crucible.cli.helpers import format_relationship_type

    assert 'is_part_of' in format_relationship_type(
        {'relationship_type': 'is_part_of'})
    assert '—' in format_relationship_type({'relationship_type': None})
    assert '—' in format_relationship_type({})
