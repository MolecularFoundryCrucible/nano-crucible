#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MatEnsemble run parser for individual MD simulation directories.

Parses a single run directory produced by the MatEnsemble workflow.
Ground-truth metadata (species, temperatures, file pointers) is read
from the per-timestep ``metadata_<N>.json`` files written by the workflow,
so nothing about the material system or folder naming is hardcoded here.
"""

import json
import logging
import os
import pickle
import re
from pathlib import Path

from .base import BaseParser

logger = logging.getLogger(__name__)


class MatEnsembleRunParser(BaseParser):
    """Parser for a single MatEnsemble run directory (one point in parameter space)."""

    _measurement     = "MatEnsemble-run"
    _data_format     = "MatEns"
    _instrument_name = None

    # ------------------------------------------------------------------ parse

    def parse(self):
        """
        Parse a MatEnsemble run directory.

        Reads ``metadata_0.json`` for setup information and
        ``metadata_<last_timestep>.json`` for final-state information.
        Species, temperatures, and output-file pointers are all taken
        from those JSON files — nothing is inferred from the folder name
        or hardcoded for a specific material.
        """
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Resolve directory from the first entry (can be a dir or a file in it)
        first = Path(self.files_to_upload[0])
        dataset_dir = first if first.is_dir() else first.parent
        logger.debug(f"Parsing MatEnsemble dataset: {dataset_dir}")

        # 1. Count all files / discover timesteps
        file_stats = self._count_files(dataset_dir)
        first_ts   = file_stats["first_timestep"]
        last_ts    = file_stats["last_timestep"]

        # 2. Read metadata JSONs (first and last timestep)
        meta_first = self._read_metadata_json(dataset_dir, first_ts)
        meta_last  = self._read_metadata_json(dataset_dir, last_ts)

        # 3. Extract species — drives thumbnail rendering and atom-type mapping
        species = meta_first.get("species") or []

        # 4. Parse LAMMPS log for version / pair-style / dimension
        log_file   = self._find_log_file(dataset_dir)
        sim_params = self._parse_log_file(log_file)

        # Boundary conditions come from the input script (canonical source);
        # fall back to the log if the input file can't be resolved locally.
        lammps_input = self._resolve_path(
            meta_first.get("lammps_input"), dataset_dir
        )
        if lammps_input:
            boundary = self._parse_boundary(lammps_input)
        else:
            boundary = sim_params.get("boundary")

        # 5. Read last snapshot → ASE Atoms for thumbnail
        snapshot_info = self._read_snapshot(
            dataset_dir, last_ts, species, boundary=boundary
        )

        # 6. Select representative files for upload
        self.files_to_upload = self._select_files_to_upload(
            dataset_dir, first_ts, last_ts, meta_last
        )

        # 7. Generate thumbnail
        if snapshot_info.get("ase_atoms"):
            self.thumbnail = self._render_thumbnail(snapshot_info["ase_atoms"], self.mfid)
            logger.info(f"Thumbnail generated: {self.thumbnail}")

        # 8. Load JSON metadata directly (first timestep for setup info,
        #    last timestep to overwrite current_* with the final state)
        for ts in (first_ts, last_ts):
            path = dataset_dir / f"metadata_{ts}.json"
            if path.exists():
                self.add_metadata(str(path))

        # Add computed fields not present in the metadata JSONs
        self.add_metadata({
            "root":           str(dataset_dir.resolve()),
            "dataset_folder": dataset_dir.name,
            "natoms":         snapshot_info.get("natoms"),
            "ntimesteps":     file_stats["ntimesteps"],
            "first_timestep": first_ts,
            "last_timestep":  last_ts,
            "file_types":     file_stats["file_types"],
            "nfiles":         file_stats["nfiles"],
            **sim_params,
        })

        # 9. Keywords — derived from metadata, not hardcoded
        keywords = ["molecular dynamics", "matensemble", "LAMMPS"]
        keywords += [s.lower() for s in species]
        self.add_keywords(keywords)

    # --------------------------------------------------------- static helpers

    @staticmethod
    def _read_metadata_json(dataset_dir: Path, timestep: int) -> dict:
        """
        Read ``metadata_<timestep>.json`` from *dataset_dir*.

        Returns an empty dict if the file is missing or unparseable.
        """
        path = dataset_dir / f"metadata_{timestep}.json"
        if not path.exists():
            logger.warning(f"Metadata file not found: {path}")
            return {}
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning(f"Could not read {path}: {exc}")
            return {}

    @staticmethod
    def _resolve_path(recorded: str | None, base_dir: Path) -> Path | None:
        """
        Resolve a file path that may be an absolute path from another machine.

        Tries the path as-is first, then falls back to looking up just the
        filename in *base_dir*.  Returns ``None`` if neither exists.
        """
        if not recorded:
            return None
        candidate = Path(recorded.strip())
        if candidate.exists():
            return candidate
        local = base_dir / candidate.name
        if local.exists():
            return local
        return None

    @staticmethod
    def _parse_boundary(input_file: Path) -> str | None:
        """
        Read the ``boundary`` command from a LAMMPS input script.

        Returns a string like ``"p p f"`` or ``None`` if not found.
        """
        with open(input_file) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                m = re.match(r'boundary\s+(\w+)\s+(\w+)\s+(\w+)', line)
                if m:
                    return f"{m.group(1)} {m.group(2)} {m.group(3)}"
        logger.warning(f"No boundary command found in {input_file}")
        return None

    @staticmethod
    def _find_log_file(dataset_dir: Path) -> Path:
        """Return path to ``log.lammps``, raising if absent."""
        log_file = dataset_dir / "log.lammps"
        if not log_file.exists():
            raise FileNotFoundError(f"log.lammps not found in {dataset_dir}")
        return log_file

    @staticmethod
    def _parse_log_file(log_file: Path) -> dict:
        """Extract LAMMPS version, dimension, boundary, and pair style from the log."""
        params = {}
        with open(log_file) as fh:
            content = fh.read()

        for pattern, key, cast in [
            (r'LAMMPS \((.*?)\)',                   "lammps_version", str),
            (r'dimension\s+(\d+)',                   "dimension",      int),
            (r'pair_style\s+(\w+)',                  "pair_style",     str),
        ]:
            m = re.search(pattern, content)
            if m:
                params[key] = cast(m.group(1))

        m = re.search(r'boundary\s+(\w+)\s+(\w+)\s+(\w+)', content)
        if m:
            params["boundary"] = f"{m.group(1)} {m.group(2)} {m.group(3)}"

        return params

    @staticmethod
    def _count_files(dataset_dir: Path) -> dict:
        """
        Discover all timestep-indexed files in *dataset_dir*.

        Recognised patterns:
        - ``{prefix}_{timestep}[.{ext}]``
        - ``Ovito_dump.{timestep}.{ext}``
        """
        pattern_generic = re.compile(r'^([a-zA-Z_]+)_(\d+)(?:\.(.+))?$')
        pattern_ovito   = re.compile(r'^(Ovito_dump)\.(\d+)\.(.+)$')

        file_types: dict[str, list] = {}
        timesteps: set[int] = set()

        for f in dataset_dir.iterdir():
            if not f.is_file():
                continue
            m = pattern_generic.match(f.name) or pattern_ovito.match(f.name)
            if m:
                prefix   = m.group(1)
                timestep = int(m.group(2))
                file_types.setdefault(prefix, []).append(f)
                timesteps.add(timestep)

        timesteps_sorted = sorted(timesteps)
        return {
            "total_files":    sum(len(v) for v in file_types.values()),
            "ntimesteps":     len(timesteps_sorted),
            "first_timestep": timesteps_sorted[0]  if timesteps_sorted else None,
            "last_timestep":  timesteps_sorted[-1] if timesteps_sorted else None,
            "timesteps":      timesteps_sorted,
            "file_types":     list(file_types.keys()),
            "nfiles":         {k: len(v) for k, v in file_types.items()},
        }

    @staticmethod
    def _read_snapshot(dataset_dir: Path, timestep: int, species: list,
                       boundary: str | None = None) -> dict:
        """
        Load ``lmp_snapshot_<timestep>.pkl`` and return an ASE Atoms object.

        *species* is used for the LAMMPS-type → chemical-symbol mapping
        (type 1 → species[0], type 2 → species[1], …).

        *boundary* is the LAMMPS boundary string (e.g. ``"p p f"``); each token
        maps to periodic (``p``) or non-periodic (any other flag).
        Defaults to fully periodic if not provided.
        """
        snapshot_file = dataset_dir / f"lmp_snapshot_{timestep}.pkl"
        if not snapshot_file.exists():
            logger.warning(f"Snapshot not found: {snapshot_file}")
            return {"natoms": None, "ase_atoms": None}

        with open(snapshot_file, "rb") as fh:
            data = pickle.load(fh)

        natoms  = len(data["coords"])
        coords  = data["coords"]
        types   = data["types"]
        box_info = data["box_info"]

        try:
            from ase import Atoms

            # Build a 1-based type → symbol map from the species list
            type_map = {i + 1: s for i, s in enumerate(species)}
            symbols  = [type_map.get(t, "X") for t in types]

            lo, hi = box_info[0], box_info[1]
            cell = [
                [hi[0] - lo[0], 0, 0],
                [0, hi[1] - lo[1], 0],
                [0, 0, hi[2] - lo[2]],
            ]

            # Derive PBC from the LAMMPS boundary string ("p p f", "p p p", …)
            # 'p' = periodic; any other flag (f, s, m) = non-periodic
            if boundary:
                pbc = [tok == "p" for tok in boundary.split()]
            else:
                pbc = True  # default: fully periodic

            ase_atoms = Atoms(symbols=symbols, positions=coords,
                              cell=cell, pbc=pbc)
            return {"natoms": natoms, "timestep": timestep,
                    "ase_atoms": ase_atoms, "box_info": box_info}

        except ImportError:
            logger.warning("ASE not installed; skipping thumbnail generation")
            return {"natoms": natoms, "timestep": timestep,
                    "ase_atoms": None, "box_info": box_info}
        except Exception as exc:
            logger.error(f"Error building ASE Atoms: {exc}")
            return {"natoms": natoms, "timestep": timestep,
                    "ase_atoms": None, "box_info": box_info}

    @staticmethod
    def _select_files_to_upload(dataset_dir: Path, first_ts: int,
                                last_ts: int, meta_last: dict) -> list[str]:
        """
        Choose a representative set of files to upload.

        Uses the file pointers in *meta_last* (the last-timestep metadata JSON)
        so no regex pattern-matching against filenames is needed.

        Uploads:
        - ``log.lammps``
        - ``metadata_<last_ts>.json``
        - dump, rdf, adf files named in *meta_last*
        - last-timestep snapshot pickle
        - first-timestep snapshot pickle (for comparison)
        """
        candidates = [
            dataset_dir / "log.lammps",
            dataset_dir / f"metadata_{last_ts}.json",
            # Files named explicitly in the last metadata record
            *[dataset_dir / meta_last[key]
              for key in ("dump", "rdf", "adf")
              if meta_last.get(key)],
            # Pickle snapshots
            dataset_dir / f"lmp_snapshot_{last_ts}.pkl",
            dataset_dir / f"lmp_snapshot_{first_ts}.pkl",
        ]
        files = [str(p) for p in candidates if p.exists()]
        return files

    @staticmethod
    def _render_thumbnail(ase_atoms, mfid: str) -> str:
        """Render an ASE Atoms object to a PNG thumbnail and return its path."""
        import random
        import string
        import tempfile

        from ase.io import write

        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

        thumbnail_dir = os.path.join(tempfile.gettempdir(), "crucible_thumbnails")
        os.makedirs(thumbnail_dir, exist_ok=True)

        if mfid:
            filename = f"{mfid}.png"
        else:
            rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
            filename = f"thumbnail_{rand}.png"

        file_path = os.path.join(thumbnail_dir, filename)
        ase_atoms.wrap()
        write(file_path, ase_atoms, format="png",
              show_unit_cell=2, scale=20, maxwidth=512)
        return file_path
