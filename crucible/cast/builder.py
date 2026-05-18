#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cast builder - programmatic .crux recipe construction.

Wraps existing Dataset/Sample objects without modifying them,
tracks relationships, and can either serialize to a .crux file
or execute directly against the Crucible API.

Usage::

    from crucible.cast import Cast

    cast = Cast()
    ds1 = cast.add(dataset1)
    ds2 = cast.add(dataset2)
    smp = cast.add(sample1)

    ds1.add_child(ds2)
    ds1.add_sample(smp)

    cast.write("experiment.crux")          # create/overwrite
    cast.write("experiment.crux", append=True)  # append to existing

HPC incremental workflow::

    # job 1
    cast = Cast()
    cast.add(simulation_dataset).write("run.crux")

    # job 2
    cast = Cast.from_file("run.crux")      # stubs from existing file
    n_sim = cast.node("simulation_dataset")
    n_post = cast.add(postprocess_dataset)
    n_post.add_parent(n_sim)
    cast.write("run.crux", append=True)

    # final step
    # crucible cast run.crux
"""

import fcntl
import json
import logging
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import yaml

from .loader import _slugify, _unique_id, load
from .models import CastConfig, CastDataset, CastSample, CastPlan, Link
from .executor import CastExecutor

logger = logging.getLogger(__name__)


class CastDatasetNode:
    """Thin wrapper around a Dataset that tracks cast relationships."""

    def __init__(self, dataset, local_id: str, *, server_id: str = None, stub: bool = False):
        self._dataset    = dataset
        self.local_id    = local_id
        self._server_id  = server_id  # known server ID (from lock or unique_id)
        self._is_stub    = stub        # True = loaded from file, not re-written
        self._children: List['CastDatasetNode'] = []
        self._parents:  List['CastDatasetNode'] = []
        self._samples:  List['CastSampleNode']  = []

    def _ref(self) -> dict:
        sid = self._server_id or (self._dataset.unique_id if self._dataset else None)
        return {'mfid': sid} if sid else {'ref': self.local_id}

    def to_cast_doc(self) -> Optional[dict]:
        """Return the top-level YAML document, or None for stubs and existing server entities."""
        if self._is_stub:
            return None
        ds = self._dataset
        if ds and ds.unique_id:
            return None
        body = {k: v for k, v in {
            'id':          self.local_id,
            'name':        ds.dataset_name,
            'measurement': ds.measurement,
            'instrument':  ds.instrument_name,
            'session':     ds.session_name,
            'data_format': ds.data_format,
            'public':      ds.public or None,
            'project_id':  ds.project_id,
            'timestamp':   str(ds.timestamp) if ds.timestamp else None,
        }.items() if v is not None}
        if self._children:
            body['children'] = [n._ref() for n in self._children]
        if self._parents:
            body['parents']  = [n._ref() for n in self._parents]
        if self._samples:
            body['samples']  = [n._ref() for n in self._samples]
        return {'dataset': body}

    def add_child(self, node: 'CastDatasetNode') -> 'CastDatasetNode':
        if node not in self._children:
            self._children.append(node)
        if self not in node._parents:
            node._parents.append(self)
        return self

    def add_parent(self, node: 'CastDatasetNode') -> 'CastDatasetNode':
        if node not in self._parents:
            self._parents.append(node)
        if self not in node._children:
            node._children.append(self)
        return self

    def add_sample(self, node: 'CastSampleNode') -> 'CastDatasetNode':
        if node not in self._samples:
            self._samples.append(node)
        if self not in node._datasets:
            node._datasets.append(self)
        return self

    def to_cast_dataset(self) -> CastDataset:
        ds = self._dataset
        return CastDataset(
            name=ds.dataset_name,
            measurement=ds.measurement,
            instrument=ds.instrument_name,
            data_format=ds.data_format,
            session=ds.session_name,
            public=ds.public or False,
            timestamp=str(ds.timestamp) if ds.timestamp else None,
            project_id=ds.project_id,
        )


class CastSampleNode:
    """Thin wrapper around a Sample that tracks cast relationships."""

    def __init__(self, sample, local_id: str, *, server_id: str = None, stub: bool = False):
        self._sample     = sample
        self.local_id    = local_id
        self._server_id  = server_id
        self._is_stub    = stub
        self._children: List['CastSampleNode']  = []
        self._parents:  List['CastSampleNode']  = []
        self._datasets: List['CastDatasetNode'] = []

    def _ref(self) -> dict:
        sid = self._server_id or (self._sample.unique_id if self._sample else None)
        return {'mfid': sid} if sid else {'ref': self.local_id}

    def to_cast_doc(self) -> Optional[dict]:
        """Return the top-level YAML document, or None for stubs and existing server entities."""
        if self._is_stub:
            return None
        smp = self._sample
        if smp and smp.unique_id:
            return None
        body = {k: v for k, v in {
            'id':          self.local_id,
            'name':        smp.sample_name,
            'type':        smp.sample_type,
            'description': smp.description,
            'timestamp':   str(smp.timestamp) if smp.timestamp else None,
            'project_id':  smp.project_id,
        }.items() if v is not None}
        if self._children:
            body['children'] = [n._ref() for n in self._children]
        if self._parents:
            body['parents']  = [n._ref() for n in self._parents]
        if self._datasets:
            body['datasets'] = [n._ref() for n in self._datasets]
        return {'sample': body}

    def add_child(self, node: 'CastSampleNode') -> 'CastSampleNode':
        if node not in self._children:
            self._children.append(node)
        if self not in node._parents:
            node._parents.append(self)
        return self

    def add_parent(self, node: 'CastSampleNode') -> 'CastSampleNode':
        if node not in self._parents:
            self._parents.append(node)
        if self not in node._children:
            node._children.append(self)
        return self

    def add_dataset(self, node: 'CastDatasetNode') -> 'CastSampleNode':
        if node not in self._datasets:
            self._datasets.append(node)
        if self not in node._samples:
            node._samples.append(self)
        return self

    def to_cast_sample(self) -> CastSample:
        smp = self._sample
        return CastSample(
            name=smp.sample_name,
            type=smp.sample_type,
            description=smp.description,
            timestamp=str(smp.timestamp) if smp.timestamp else None,
            project_id=smp.project_id,
        )


class Cast:
    """
    Programmatic .crux recipe builder.

    Wraps Dataset/Sample objects, tracks relationships, and can either
    serialize to a .crux file or execute directly against the Crucible API.
    """

    def __init__(self, config: CastConfig = None):
        self._config        = config or CastConfig()
        self._nodes:        List[Union[CastDatasetNode, CastSampleNode]]      = []
        self._id_map:       Dict[int, Union[CastDatasetNode, CastSampleNode]] = {}
        self._local_id_map: Dict[str, Union[CastDatasetNode, CastSampleNode]] = {}
        self._seen:         Set[str]                                           = set()

    @classmethod
    def from_file(cls, path) -> 'Cast':
        """
        Load an existing .crux file and rebuild its node structure as stubs.

        Stubs carry their local_id (and server_id from the lock file if present)
        but produce no output on write() - only newly added entities are written.
        Use cast.node(local_id) to retrieve stubs for cross-referencing.
        """
        path = Path(path)
        plan = load(path)
        cast = cls(config=plan.config)

        lock_ids = _read_lock_ids(path.with_suffix(path.suffix + '.lock'))

        for local_id in plan.datasets:
            cast._register_node(CastDatasetNode(
                None, local_id, server_id=lock_ids.get(local_id), stub=True
            ))

        for local_id in plan.samples:
            cast._register_node(CastSampleNode(
                None, local_id, server_id=lock_ids.get(local_id), stub=True
            ))

        for local_id, server_id in plan.prefilled.items():
            if local_id not in cast._local_id_map:
                cast._register_node(CastDatasetNode(
                    None, local_id, server_id=server_id, stub=True
                ))

        for link in plan.links:
            src = cast._local_id_map.get(link.source)
            tgt = cast._local_id_map.get(link.target)
            if src is None or tgt is None:
                continue
            if link.kind == 'dataset_child' and isinstance(src, CastDatasetNode):
                if tgt not in src._children: src._children.append(tgt)
                if src not in tgt._parents:  tgt._parents.append(src)
            elif link.kind == 'dataset_sample':
                if isinstance(src, CastDatasetNode) and isinstance(tgt, CastSampleNode):
                    if tgt not in src._samples:   src._samples.append(tgt)
                    if src not in tgt._datasets:  tgt._datasets.append(src)
            elif link.kind == 'sample_child' and isinstance(src, CastSampleNode):
                if tgt not in src._children: src._children.append(tgt)
                if src not in tgt._parents:  tgt._parents.append(src)

        logger.info(
            f"Loaded {len(plan.datasets)} dataset stub(s), "
            f"{len(plan.samples)} sample stub(s) from {path.name}"
        )
        return cast

    def _register_node(self, node: Union[CastDatasetNode, CastSampleNode]):
        self._nodes.append(node)
        self._local_id_map[node.local_id] = node
        self._seen.add(node.local_id)

    def add(self, entity) -> Union[CastDatasetNode, CastSampleNode]:
        """Register a Dataset or Sample and return its cast node."""
        eid = id(entity)
        if eid in self._id_map:
            return self._id_map[eid]

        from crucible.models import Dataset, Sample

        if isinstance(entity, Dataset):
            name = entity.dataset_name or 'dataset'
            local_id = _unique_id(_slugify(name), self._seen)
            node: Union[CastDatasetNode, CastSampleNode] = CastDatasetNode(entity, local_id)
        elif isinstance(entity, Sample):
            name = entity.sample_name or 'sample'
            local_id = _unique_id(_slugify(name), self._seen)
            node = CastSampleNode(entity, local_id)
        else:
            raise TypeError(f"Expected Dataset or Sample, got {type(entity).__name__}")

        self._id_map[eid] = node
        self._register_node(node)
        return node

    def node(self, local_id: str) -> Optional[Union[CastDatasetNode, CastSampleNode]]:
        """Look up a node by its local_id. Returns None with a warning if not found."""
        n = self._local_id_map.get(local_id)
        if n is None:
            warnings.warn(
                f"No node with local_id '{local_id}' found in this Cast",
                stacklevel=2,
            )
        return n

    def write(self, path, append: bool = False) -> None:
        """
        Serialize registered entities to a .crux file.

        Args:
            path:   Path to the .crux file.
            append: If True, append new documents to an existing file using
                    a file lock to prevent concurrent writes. Stubs (entities
                    loaded via from_file) are never re-written.
        """
        docs = [d for n in self._nodes if (d := n.to_cast_doc()) is not None]
        if not docs:
            logger.warning("No new entities to write - all nodes are stubs or server-side entities")
            return

        path = Path(path)

        if not append:
            with open(path, 'w') as f:
                yaml.dump_all(docs, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return

        lock_file = path.with_suffix(path.suffix + '.lck')
        with open(lock_file, 'w') as lf:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    f"Another process is writing to {path}. "
                    f"If this is stale, delete {lock_file} and retry."
                )
            try:
                with open(path, 'a') as f:
                    if path.stat().st_size > 0:
                        f.write('---\n')
                    yaml.dump_all(docs, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
        lock_file.unlink(missing_ok=True)

    def apply(self, client, lock_path: Path = None, dry_run: bool = False) -> Dict[str, str]:
        """Build a CastPlan in memory and execute - no file needed."""
        plan = self._to_cast_plan(lock_path)
        return CastExecutor(plan).apply(client, dry_run=dry_run)

    def _to_cast_plan(self, lock_path: Optional[Path] = None) -> CastPlan:
        datasets:  Dict[str, CastDataset] = {}
        samples:   Dict[str, CastSample]  = {}
        prefilled: Dict[str, str]         = {}
        links:     List[Link]             = []

        for node in self._nodes:
            if isinstance(node, CastDatasetNode):
                sid = node._server_id or (node._dataset.unique_id if node._dataset else None)
                if sid:
                    prefilled[node.local_id] = sid
                elif node._dataset:
                    datasets[node.local_id] = node.to_cast_dataset()
                for child in node._children:
                    links.append(Link('dataset_child', node.local_id, child.local_id))
                for parent in node._parents:
                    links.append(Link('dataset_child', parent.local_id, node.local_id))
                for smp in node._samples:
                    links.append(Link('dataset_sample', node.local_id, smp.local_id))
            else:
                sid = node._server_id or (node._sample.unique_id if node._sample else None)
                if sid:
                    prefilled[node.local_id] = sid
                elif node._sample:
                    samples[node.local_id] = node.to_cast_sample()
                for child in node._children:
                    links.append(Link('sample_child', node.local_id, child.local_id))
                for parent in node._parents:
                    links.append(Link('sample_child', parent.local_id, node.local_id))
                for ds in node._datasets:
                    links.append(Link('dataset_sample', ds.local_id, node.local_id))

        links = list(dict.fromkeys(links))

        lp = lock_path or Path('.cast.lock')
        return CastPlan(
            config=self._config,
            datasets=datasets,
            samples=samples,
            links=links,
            lock_path=lp,
            base_dir=lp.parent,
            prefilled=prefilled,
        )


def _read_lock_ids(lock_path: Path) -> Dict[str, str]:
    """Read server IDs from a lock file, returning {} on any failure."""
    if not lock_path.exists():
        return {}
    try:
        with open(lock_path) as f:
            data = json.load(f)
        return {
            lid: (entry['server_id'] if isinstance(entry, dict) else entry)
            for lid, entry in data.get('ids', {}).items()
        }
    except (json.JSONDecodeError, KeyError):
        logger.warning(f"Could not read lock file {lock_path} - server IDs unavailable")
        return {}
