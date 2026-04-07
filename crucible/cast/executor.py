#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executor for CastPlan - creates entities and applies links via the Crucible API.

Lock file format (JSON, written next to the .crux file as <name>.crux.lock):
{
    "ids": {
        "local_id": {
            "server_id": "ds-abc123",
            "hash": "a3f9...",
            "files": {"relative/path/to/file.dm4": "sha256hex..."},
            "ingestion_id": 42
        },
        ...
    },
    "links": ["dataset_child:raw:processed", ...]
}

The entity hash is computed from the entity's definition at creation time. On re-run,
if the hash changed, the entity is skipped with a warning so the user can decide
whether to update it manually.

File uploads and ingestion requests are tracked separately: a re-run after a partial
failure will skip already-uploaded files and skip re-requesting ingestion.
"""

import fcntl
import hashlib
import json
import logging
import os
import socket
from contextlib import contextmanager
from typing import Dict, List, Optional

from .models import CastPlan, Link

logger = logging.getLogger(__name__)


def _hash_entity(entity) -> str:
    """Stable SHA-256 hash of an entity's definition (excluding its local id)."""
    data = entity.model_dump(exclude={'id'})
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _file_sha256(path: str) -> str:
    """Compute SHA-256 of a file in chunks."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


class CastExecutor:
    """
    Executes a CastPlan against the Crucible API.

    Supports resumability via a lock file: already-created entities and
    already-applied links are skipped on re-runs. File uploads and ingestion
    requests are tracked individually so partial failures can be resumed.
    """

    def __init__(self, plan: CastPlan):
        self.plan = plan
        self._lock = self._load_lock()

    # ------------------------------------------------------------------
    # Lock file helpers
    # ------------------------------------------------------------------

    def _load_lock(self) -> Dict:
        if self.plan.lock_path.exists():
            try:
                with open(self.plan.lock_path) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Lock file is empty or invalid - starting fresh")
        return {"ids": {}, "links": []}

    def _save_lock(self):
        with open(self.plan.lock_path, 'w') as f:
            json.dump(self._lock, f, indent=2)

    @contextmanager
    def _file_lock(self):
        """Exclusive file lock to prevent simultaneous cast runs on the same recipe."""
        lock_file = self.plan.lock_path.with_suffix('.lck')
        with open(lock_file, 'w') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    f"Another cast process is already running on {self.plan.lock_path.with_suffix('')}. "
                    f"If this is stale, delete {lock_file} and retry."
                )
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        lock_file.unlink(missing_ok=True)

    def _server_id(self, local_id: str) -> Optional[str]:
        entry = self._lock["ids"].get(local_id)
        if entry is None:
            return None
        return entry["server_id"] if isinstance(entry, dict) else entry

    def _mark_created(self, local_id: str, server_id: str, entity_hash: str):
        self._lock["ids"][local_id] = {"server_id": server_id, "hash": entity_hash,
                                       "files": {}, "ingestion_id": None}
        self._save_lock()

    def _uploaded_files(self, local_id: str) -> Dict[str, str]:
        """Return {absolute_path: sha256} for files already uploaded for this entity.
        Paths in the lock are stored relative to the .crux directory for portability."""
        entry = self._lock["ids"].get(local_id)
        if isinstance(entry, dict):
            return {
                str((self.plan.base_dir / rel).resolve()): sha256
                for rel, sha256 in (entry.get("files") or {}).items()
            }
        return {}

    def _mark_file_uploaded(self, local_id: str, path: str, sha256: str):
        rel = os.path.relpath(path, self.plan.base_dir)
        self._lock["ids"][local_id].setdefault("files", {})[rel] = sha256
        self._save_lock()

    def _ingestion_id(self, local_id: str) -> Optional[int]:
        entry = self._lock["ids"].get(local_id)
        if isinstance(entry, dict):
            return entry.get("ingestion_id")
        return None

    def _mark_ingested(self, local_id: str, ingestion_id: int):
        self._lock["ids"][local_id]["ingestion_id"] = ingestion_id
        self._save_lock()

    def reset(self):
        """Clear the entire lock - all entities will be recreated on next apply."""
        self._lock = {"ids": {}, "links": []}
        self._save_lock()
        logger.info("Lock cleared - all entities will be recreated")

    def reset_files(self):
        """Clear file upload and ingestion tracking for all datasets.
        Server IDs are preserved so existing records are reused."""
        for entry in self._lock["ids"].values():
            if isinstance(entry, dict):
                entry["files"] = {}
                entry["ingestion_id"] = None
        self._save_lock()
        logger.info("File tracking cleared - files will be re-uploaded to existing records")

    def _mark_linked(self, link: Link):
        key = f"{link.kind}:{link.source}:{link.target}"
        if key not in self._lock["links"]:
            self._lock["links"].append(key)
            self._save_lock()

    def _is_linked(self, link: Link) -> bool:
        return f"{link.kind}:{link.source}:{link.target}" in self._lock["links"]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self, client, dry_run: bool = False) -> Dict[str, str]:
        """
        Create all entities and apply all links.

        Args:
            client: CrucibleClient instance.
            dry_run: If True, log what would happen without making API calls.

        Returns:
            Dict mapping local_id -> server_id for all entities.
            In dry_run mode, values are None for entities not yet created.
        """
        if dry_run:
            self._run(client, dry_run=True)
            return {
                lid: self._server_id(lid)
                for lid in list(self.plan.datasets) + list(self.plan.samples)
            }

        with self._file_lock():
            self._run(client, dry_run=False)
        return {lid: self._server_id(lid) for lid in self._lock["ids"]}

    def _run(self, client, dry_run: bool):
        # Pre-populate ID map with existing server resources (mfid refs)
        for local_id, server_id in self.plan.prefilled.items():
            self._lock["ids"].setdefault(local_id, {"server_id": server_id, "hash": None})

        self._create_entities(client, dry_run)
        self._apply_links(client, dry_run)

    # ------------------------------------------------------------------
    # Entity creation
    # ------------------------------------------------------------------

    def _create_entities(self, client, dry_run: bool):
        for local_id, ds in self.plan.datasets.items():
            self._process_dataset(local_id, ds, client, dry_run)

        for local_id, smp in self.plan.samples.items():
            if not self._should_skip_sample(local_id, smp, dry_run):
                self._create_sample(local_id, smp, client)

    def _should_skip_sample(self, local_id: str, smp, dry_run: bool) -> bool:
        entry = self._lock["ids"].get(local_id)
        if entry is not None:
            if entry.get("hash") != _hash_entity(smp):
                logger.warning(
                    f"Sample '{smp.name}' [{local_id}] has changed since it was "
                    f"created (server_id: {entry['server_id']}). Skipping - update manually if needed."
                )
            else:
                logger.info(f"Skip sample '{smp.name}' (already created: {entry['server_id']})")
            return True
        if dry_run:
            logger.info(f"[dry-run] Would create sample: {smp.name}")
            return True
        return False

    def _process_dataset(self, local_id: str, ds, client, dry_run: bool):
        """Handle a dataset: fresh creation or resuming pending uploads/ingestion."""
        entry = self._lock["ids"].get(local_id)

        if entry is not None:
            # Record already exists - check for definition changes
            if entry.get("hash") != _hash_entity(ds):
                logger.warning(
                    f"Dataset '{ds.name}' [{local_id}] has changed since it was "
                    f"created (server_id: {entry['server_id']}). Skipping - update manually if needed."
                )
                return
            if dry_run:
                logger.info(f"Skip dataset '{ds.name}' (already created: {entry['server_id']})")
                return
            # Resume: upload any pending files and request ingestion if not done.
            # For parser-based datasets, re-run the parser to get the full file list
            # (it may produce additional files beyond ds.files). For direct datasets,
            # ds.files is already fully resolved at load time.
            logger.info(f"Resuming dataset '{ds.name}' ({entry['server_id']})")
            if ds.parser is not None:
                _, files, _, _, thumbnail = self._resolve_all_assets(ds, client)
            else:
                files, thumbnail = ds.files or [], None
            self._upload_files(local_id, entry["server_id"], files, thumbnail, client)
            self._ingest_if_needed(local_id, entry["server_id"], ds, files, client)

        elif dry_run:
            logger.info(f"[dry-run] Would create dataset: {ds.name}")

        else:
            self._create_dataset(local_id, ds, client)

    def _cast_provenance(self) -> dict:
        """Provenance metadata injected into every dataset created by cast."""
        crux_path = self.plan.lock_path.with_suffix('').resolve()
        return {
            "cast_source": str(crux_path),
            "hostname": socket.getfqdn(),
        }

    def _resolve_all_assets(self, ds, client):
        """
        Resolve all assets needed for fresh dataset creation.
        Returns (dataset_obj, files, metadata, keywords, thumbnail).
        """
        if ds.parser is not None:
            from crucible.parsers import get_parser
            parser_cls = get_parser(ds.parser)
            parser = parser_cls(
                files_to_upload=ds.files or None,
                project_id=ds.project_id,
                metadata=ds.metadata or None,
                keywords=ds.keywords or None,
                measurement=ds.measurement,
                dataset_name=ds.name,
                session_name=ds.session,
                public=ds.public,
                instrument_name=ds.instrument,
                data_format=ds.data_format,
                timestamp=ds.timestamp,
            )
            parser._client = client
            provenance = self._cast_provenance()
            metadata = {**provenance, **parser.scientific_metadata}
            return (parser.to_dataset(), parser.files_to_upload,
                    metadata, parser.keywords, parser.thumbnail)
        else:
            from crucible.models import Dataset
            dataset = Dataset(
                dataset_name=ds.name,
                project_id=ds.project_id,
                measurement=ds.measurement,
                session_name=ds.session,
                public=ds.public,
                instrument_name=ds.instrument,
                data_format=ds.data_format,
                timestamp=ds.timestamp,
            )
            provenance = self._cast_provenance()
            metadata = {**provenance, **(ds.metadata or {})}
            return dataset, ds.files or [], metadata, ds.keywords or None, None

    def _upload_files(self, local_id: str, dsid: str, files: List[str],
                      thumbnail, client):
        """Upload files not yet tracked in the lock."""
        already_uploaded = self._uploaded_files(local_id)
        for f in files:
            if f in already_uploaded:
                logger.info(f"Skip upload '{os.path.basename(f)}' (already uploaded)")
                continue
            client.datasets.upload_file(dsid, f)
            self._mark_file_uploaded(local_id, f, _file_sha256(f))
            logger.info(f"Uploaded '{os.path.basename(f)}' to {dsid}")

        if thumbnail is not None:
            client.datasets.add_thumbnail(dsid, thumbnail)

    def _ingest_if_needed(self, local_id: str, dsid: str, ds, files: List[str], client):
        """Request ingestion if files are present and ingestion not yet requested."""
        if not files or self._ingestion_id(local_id) is not None:
            return
        ingestor = ds.ingestor or 'ApiUploadIngestor'
        cloud_path = f"api-uploads/{os.path.basename(files[0])}"
        req = client.datasets.request_ingestion(dsid, cloud_path, ingestor)
        self._mark_ingested(local_id, req['id'])
        logger.info(f"Requested ingestion for '{ds.name}' ({dsid}) with {ingestor}")

    def _create_dataset(self, local_id: str, ds, client):
        dataset, files, metadata, keywords, thumbnail = self._resolve_all_assets(ds, client)

        # Create the record first, mark immediately so a re-run after a failed
        # file upload does not create a duplicate record.
        result = client.datasets.create(
            dataset,
            files_to_upload=None,
            scientific_metadata=metadata,
            keywords=keywords,
        )
        dsid = result['dsid']
        self._mark_created(local_id, dsid, _hash_entity(ds))
        logger.info(f"Created dataset '{ds.name}': {dsid}")

        self._upload_files(local_id, dsid, files, thumbnail, client)
        self._ingest_if_needed(local_id, dsid, ds, files, client)

    def _create_sample(self, local_id: str, smp, client):
        result = client.samples.create(
            sample_name=smp.name,
            project_id=smp.project_id,
            sample_type=smp.type,
            description=smp.description,
            timestamp=smp.timestamp,
        )
        sid = result['unique_id']
        self._mark_created(local_id, sid, _hash_entity(smp))
        logger.info(f"Created sample '{smp.name}': {sid}")

    # ------------------------------------------------------------------
    # Link application
    # ------------------------------------------------------------------

    def _apply_links(self, client, dry_run: bool):
        for link in self.plan.links:
            if self._is_linked(link):
                continue

            if dry_run:
                logger.info(f"[dry-run] Would link {link.kind}: {link.source} -> {link.target}")
                continue

            src_id = self._server_id(link.source)
            tgt_id = self._server_id(link.target)

            if src_id is None or tgt_id is None:
                logger.warning(
                    f"Cannot apply link {link.kind} '{link.source}' -> '{link.target}': "
                    f"missing server ID (creation failed?)"
                )
                continue

            self._apply_link(link, src_id, tgt_id, client)
            self._mark_linked(link)

    def _apply_link(self, link: Link, src_id: str, tgt_id: str, client):
        if link.kind == 'dataset_child':
            client.datasets.link_parent_child(src_id, tgt_id)
            logger.info(f"Linked dataset parent {src_id} -> child {tgt_id}")
        elif link.kind == 'dataset_sample':
            client.datasets.add_sample(src_id, tgt_id)
            logger.info(f"Linked dataset {src_id} <-> sample {tgt_id}")
        elif link.kind == 'sample_child':
            client.samples.link(src_id, tgt_id)
            logger.info(f"Linked sample parent {src_id} -> child {tgt_id}")
        else:
            raise ValueError(f"Unknown link kind: {link.kind}")
