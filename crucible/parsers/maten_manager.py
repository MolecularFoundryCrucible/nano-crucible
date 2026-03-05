#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MatEnsemble manager parser for the top-level simulation setup dataset.

Parses the root directory of a MatEnsemble simulation campaign, which holds
the shared input files (LAMMPS input script, initial structure, force field,
parameter config, driver scripts) that all individual runs share.

Ground-truth metadata is read from ``input_paramters.json`` written by the
workflow; nothing about the material system is hardcoded.
"""

import json
import logging
import os
import random
import re
import string
import tempfile
from pathlib import Path

from .base import BaseParser

logger = logging.getLogger(__name__)


class MatEnsembleManagerParser(BaseParser):
    """Parser for the MatEnsemble root/manager dataset."""

    _measurement     = "MatEnsemble-manager"
    _data_format     = "MatEns"
    _instrument_name = None

    # ------------------------------------------------------------------ parse

    def parse(self):
        """
        Parse the MatEnsemble root simulation directory.

        Accepts either the root directory or the driver Python script
        (e.g. ``onlineMD_Eq.py``) as the primary input.  When given a
        Python file, the ``initial_parameters_file`` argument is extracted
        from it to locate ``input_paramters.json``; otherwise the JSON is
        searched for by name in the directory.

        All non-hidden regular files directly in the directory are uploaded.
        A thumbnail is rendered from the initial LAMMPS structure file.
        """
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Resolve root directory and locate params file
        first = Path(self.files_to_upload[0])
        if first.suffix == ".py":
            # Entry point is the driver script — parse it for the params path
            root_dir    = first.parent
            params_file = self._find_params_from_script(first, root_dir)
        else:
            root_dir    = first if first.is_dir() else first.parent
            params_file = self._find_params_file(root_dir)

        logger.debug(f"Parsing MatEnsemble manager dataset: {root_dir}")

        # 1. Read input_paramters.json
        params = self._read_params(params_file)

        # 2. Collect all non-hidden files in the root directory for upload
        self.files_to_upload = self._select_files_to_upload(root_dir)

        # 3. Load JSON metadata directly, then add computed fields not in the file
        species = params.get("species") or []
        if params_file:
            self.add_metadata(str(params_file))
        self.add_metadata({
            "root":                   str(root_dir.resolve()),
            "simulation_duration_fs": (params.get("total_number_of_timesteps", 0)
                                       * params.get("verlet_delta_t", 0)),
        })

        # 4. Keywords derived from species
        keywords = ["molecular dynamics", "matensemble", "LAMMPS", "manager"]
        keywords += [s.lower() for s in species]
        self.add_keywords(keywords)

        # 5. Render thumbnail from the initial structure file
        datafile = self._resolve_datafile(root_dir, params)
        if datafile:
            self.thumbnail = self._render_thumbnail(datafile, species, self.mfid)
            if self.thumbnail:
                logger.info(f"Thumbnail generated: {self.thumbnail}")

    # --------------------------------------------------------- static helpers

    @staticmethod
    def _find_params_from_script(script_path: Path, root_dir: Path) -> Path | None:
        """
        Parse a MatEnsemble driver script to extract the ``initial_parameters_file``
        argument and resolve it relative to *root_dir*.

        Falls back to ``_find_params_file`` if the argument cannot be found.
        """
        try:
            content = script_path.read_text()
            match = re.search(
                r"initial_parameters_file\s*=\s*['\"]([^'\"]+)['\"]", content
            )
            if match:
                params_path = root_dir / match.group(1)
                if params_path.exists():
                    logger.debug(f"Found params file from script: {params_path}")
                    return params_path
                logger.warning(
                    f"Script references '{match.group(1)}' but it was not found in {root_dir}"
                )
        except Exception as exc:
            logger.warning(f"Could not parse script {script_path}: {exc}")

        # Fall back to searching by name
        return MatEnsembleManagerParser._find_params_file(root_dir)

    @staticmethod
    def _find_params_file(root_dir: Path) -> Path | None:
        """
        Locate ``input_paramters.json`` (or ``input_parameters.json``) in *root_dir*.

        Returns ``None`` with a warning if neither variant is found.
        """
        for name in ("input_paramters.json", "input_parameters.json"):
            candidate = root_dir / name
            if candidate.exists():
                return candidate
        logger.warning(f"No input parameters JSON found in {root_dir}")
        return None

    @staticmethod
    def _read_params(params_file: Path | None) -> dict:
        """Read and return the parameters JSON, or an empty dict if unavailable."""
        if params_file is None:
            return {}
        try:
            with open(params_file) as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning(f"Could not read {params_file}: {exc}")
            return {}

    @staticmethod
    def _select_files_to_upload(root_dir: Path) -> list[str]:
        """
        Collect all non-hidden regular files directly in *root_dir*.

        Subdirectories (e.g. workflow output folders) are skipped entirely.
        """
        files = [
            str(f) for f in sorted(root_dir.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]
        return files

    @staticmethod
    def _resolve_datafile(root_dir: Path, params: dict) -> Path | None:
        """
        Find the initial LAMMPS structure file.

        Tries the path recorded in *params* first; falls back to scanning
        *root_dir* for a ``.lmp`` file if the recorded path doesn't exist locally.
        """
        recorded = (params.get("lammps_datafile") or "").strip()
        if recorded:
            candidate = Path(recorded)
            if candidate.exists():
                return candidate
            # Recorded path may be an absolute NERSC path — try just the filename
            local = root_dir / candidate.name
            if local.exists():
                return local

        # Last resort: first .lmp file in the directory
        lmp_files = sorted(root_dir.glob("*.lmp"))
        if lmp_files:
            return lmp_files[0]

        logger.warning(f"No LAMMPS data file found in {root_dir}")
        return None

    @staticmethod
    def _render_thumbnail(datafile: Path, species: list, mfid: str) -> str | None:
        """
        Read the initial LAMMPS structure and render a PNG thumbnail.

        *species* provides the LAMMPS-type → chemical-symbol mapping
        (type 1 → species[0], type 2 → species[1], …).
        """
        try:
            from ase.data import atomic_numbers
            from ase.io import read, write

            logging.getLogger("matplotlib").setLevel(logging.WARNING)
            logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

            Z_of_type = {i + 1: atomic_numbers[s] for i, s in enumerate(species)}
            atoms = read(str(datafile), format="lammps-data", Z_of_type=Z_of_type)

            thumbnail_dir = os.path.join(tempfile.gettempdir(), "crucible_thumbnails")
            os.makedirs(thumbnail_dir, exist_ok=True)

            if mfid:
                filename = f"{mfid}.png"
            else:
                rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
                filename = f"thumbnail_{rand}.png"

            file_path = os.path.join(thumbnail_dir, filename)
            atoms.wrap()
            write(file_path, atoms, format="png",
                  show_unit_cell=2, scale=20, maxwidth=512)
            return file_path

        except ImportError:
            logger.warning("ASE not installed; skipping thumbnail generation")
        except Exception as exc:
            logger.warning(f"Could not render thumbnail from {datafile}: {exc}")
        return None
