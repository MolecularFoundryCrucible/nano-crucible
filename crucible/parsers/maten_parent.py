#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 27 09:04:08 2026

@author: roncofaber
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MatEnsemble LAMMPS Parser for Molecular Dynamics + Machine Learning datasets.

Parses datasets from MatEnsemble project containing:
- LAMMPS simulation logs
- Bispectrum coefficient files
- Atomic snapshots (pickle format)
- OVITO dump files
- VTK visualization files
"""

import os
import re
import logging
import pickle
from pathlib import Path
from .base import BaseParser
import socket

logger = logging.getLogger(__name__)


class MatEnsembleParentParser(BaseParser):
    """Parser for parent MatEnsemble datasets."""

    _measurement = "MatEnsemble parent"
    _data_format = "MatEns"
    _instrument_name = "MatEnsemble"

    def parse(self):
        """
        Parse MatEnsemble LAMMPS dataset folder.

        Extracts metadata from folder name, log file, and snapshot files.
        Uploads only summary files (log + last snapshot) rather than entire dataset.
        """
        # Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Get dataset directory from first file
        first_file = Path(self.files_to_upload[0])
        if first_file.is_dir():
            dataset_dir = first_file
        else:
            dataset_dir = first_file.parent

        logger.debug(f"Parsing MatEnsemble dataset: {dataset_dir}")

        # 1. Extract metadata from folder name
        folder_name = dataset_dir.name
        temp, lattice = self._parse_folder_name(folder_name)

        # 2. Find and parse log file
        log_file = self._find_log_file(dataset_dir)
        sim_params = self._parse_log_file(log_file)

        # 3. Count files and find timesteps
        file_stats = self._count_files(dataset_dir)

        # 4. Read last snapshot to get system info
        last_timestep = file_stats['last_timestep']
        snapshot_info = self._read_snapshot(dataset_dir, last_timestep)

        # 5. Build file list for upload (log + last snapshot files)
        files_to_upload = self._select_files_to_upload(dataset_dir, last_timestep)
        self.files_to_upload = [str(f) for f in files_to_upload]

        # 6. Generate thumbnail from last snapshot
        if snapshot_info.get('ase_atoms'):
            self.thumbnail = self._render_thumbnail(snapshot_info['ase_atoms'], self.mfid)
            logger.info(f"Thumbnail generated: {self.thumbnail}")

        # Add extracted metadata
        metadata = {
            'root': str(dataset_dir.resolve()),
            'temperature_K': temp,
            'lattice_parameter': lattice,
            'natoms': snapshot_info['natoms'],
            'ntimesteps': file_stats['ntimesteps'],
            'last_timestep': last_timestep,
            'simulation_type': 'recrystallization', #TODO need to do this better
            'material': 'MoS2',
            'dataset_folder': folder_name,
            **sim_params,
            **file_stats
        }
        self.add_metadata(metadata)

        # Add keywords
        keywords = [
            'molecular dynamics',
            'matensemble',
            'MoS2',
            'recrystallization',
            'LAMMPS'
        ]
        self.add_keywords(keywords)

    @staticmethod
    def _parse_folder_name(folder_name):
        """
        Extract temperature and lattice parameter from folder name.

        Args:
            folder_name (str): Folder name like "1011.5723_K_1.03116lattice"

        Returns:
            tuple: (temperature, lattice_parameter)
        """
        # Pattern: {temp}_K_{lattice}lattice
        match = re.match(r'([\d.]+)_K_([\d.]+)lattice', folder_name)
        if match:
            temp = float(match.group(1))
            lattice = float(match.group(2))
            return temp, lattice
        else:
            logger.warning(f"Could not parse folder name: {folder_name}")
            return None, None

    @staticmethod
    def _find_log_file(dataset_dir):
        """Find log.lammps file in dataset directory."""
        log_file = dataset_dir / 'log.lammps'
        if log_file.exists():
            return log_file
        else:
            raise FileNotFoundError(f"log.lammps not found in {dataset_dir}")

    @staticmethod
    def _parse_log_file(log_file):
        """
        Parse LAMMPS log file to extract simulation parameters.

        Args:
            log_file (Path): Path to log.lammps

        Returns:
            dict: Simulation parameters
        """
        params = {}

        with open(log_file, 'r') as f:
            content = f.read()

        # Extract LAMMPS version
        version_match = re.search(r'LAMMPS \((.*?)\)', content)
        if version_match:
            params['lammps_version'] = version_match.group(1)

        # Extract dimension
        dim_match = re.search(r'dimension\s+(\d+)', content)
        if dim_match:
            params['dimension'] = int(dim_match.group(1))

        # Extract boundary conditions
        boundary_match = re.search(r'boundary\s+(\w+)\s+(\w+)\s+(\w+)', content)
        if boundary_match:
            params['boundary'] = f"{boundary_match.group(1)} {boundary_match.group(2)} {boundary_match.group(3)}"

        # Extract pair style
        pair_match = re.search(r'pair_style\s+(\w+)', content)
        if pair_match:
            params['pair_style'] = pair_match.group(1)

        return params

    @staticmethod
    def _count_files(dataset_dir):
        """
        Count files and identify timesteps using pattern detection.

        Automatically discovers file types matching patterns:
        - {prefix}_{timestep}.{ext}
        - {prefix}_{timestep}
        - Ovito_dump.{timestep}.{ext}

        Args:
            dataset_dir (Path): Dataset directory

        Returns:
            dict: File statistics including discovered file types
        """
        all_files = list(dataset_dir.iterdir())

        # Dictionary to store files by type
        file_types = {}
        timesteps = set()

        # Pattern 1: prefix_{timestep}.ext or prefix_{timestep}
        pattern1 = re.compile(r'^([a-zA-Z_]+)_(\d+)(?:\.(.+))?$')
        # Pattern 2: Ovito_dump.{timestep}.ext
        pattern2 = re.compile(r'^(Ovito_dump)\.(\d+)\.(.+)$')

        for f in all_files:
            if not f.is_file():
                continue

            # Try pattern 1
            match = pattern1.match(f.name)
            if match:
                prefix = match.group(1)
                timestep = int(match.group(2))
                ext = match.group(3) or ''

                # Create file type key
                file_type = prefix
                if file_type not in file_types:
                    file_types[file_type] = []
                file_types[file_type].append(f)
                timesteps.add(timestep)
                continue

            # Try pattern 2 (Ovito_dump)
            match = pattern2.match(f.name)
            if match:
                prefix = match.group(1)
                timestep = int(match.group(2))

                file_type = 'Ovito_dump'
                if file_type not in file_types:
                    file_types[file_type] = []
                file_types[file_type].append(f)
                timesteps.add(timestep)
                continue

        timesteps = sorted(list(timesteps))

        # Build file counts dictionary
        nfiles = {file_type: len(files) for file_type, files in file_types.items()}

        # Build statistics dict
        stats = {
            'total_files': len(all_files),
            'ntimesteps': len(timesteps),
            'first_timestep': timesteps[0] if timesteps else None,
            'last_timestep': timesteps[-1] if timesteps else None,
            'timesteps': timesteps,
            'file_types': list(file_types.keys()),  # List of discovered file types
            'nfiles': nfiles,  # Dictionary of file counts by type
        }

        return stats

    @staticmethod
    def _read_snapshot(dataset_dir, timestep):
        """
        Read a pickle snapshot file and convert to ASE atoms.

        Args:
            dataset_dir (Path): Dataset directory
            timestep (int): Timestep to read

        Returns:
            dict: Snapshot information including ASE atoms
        """
        snapshot_file = dataset_dir / f'lmp_snapshot_{timestep}.pkl'

        if not snapshot_file.exists():
            logger.warning(f"Snapshot file not found: {snapshot_file}")
            return {'natoms': None, 'ase_atoms': None}

        # Load pickle data
        with open(snapshot_file, 'rb') as f:
            data = pickle.load(f)

        # Extract info
        natoms = len(data['coords'])
        coords = data['coords']
        types = data['types']
        box_info = data['box_info']

        # Convert to ASE Atoms object
        try:
            from ase import Atoms

            # Parse box info
            # box_info format: (lo, hi, xy, xz, yz, periodicity, triclinic)
            lo = box_info[0]  # [xlo, ylo, zlo]
            hi = box_info[1]  # [xhi, yhi, zhi]

            # Create cell
            cell = [
                [hi[0] - lo[0], 0, 0],
                [0, hi[1] - lo[1], 0],
                [0, 0, hi[2] - lo[2]]
            ]

            # Map types to chemical symbols (assuming MoS2)
            # Type 1 = S, Type 2 = Mo (common convention)
            symbols = ['S' if t == 1 else 'Mo' for t in types]

            # Create ASE Atoms
            ase_atoms = Atoms(
                symbols=symbols,
                positions=coords,
                cell=cell,
                pbc=[True, True, False]  # pp pp ff boundary
            )

            return {
                'natoms': natoms,
                'timestep': timestep,
                'ase_atoms': ase_atoms,
                'box_info': box_info
            }

        except ImportError:
            logger.warning("ASE not installed, cannot convert snapshot to Atoms")
            return {
                'natoms': natoms,
                'timestep': timestep,
                'ase_atoms': None,
                'box_info': box_info
            }
        except Exception as e:
            logger.error(f"Error converting snapshot to ASE Atoms: {e}")
            return {
                'natoms': natoms,
                'timestep': timestep,
                'ase_atoms': None,
                'box_info': box_info
            }

    @staticmethod
    def _select_files_to_upload(dataset_dir, last_timestep):
        """
        Select representative files to upload (not entire dataset).

        Automatically discovers all file types and includes last timestep version.

        Args:
            dataset_dir (Path): Dataset directory
            last_timestep (int): Last timestep number

        Returns:
            list: List of file paths to upload
        """
        files = []

        # 1. Always include log file
        log_file = dataset_dir / 'log.lammps'
        if log_file.exists():
            files.append(log_file)

        # 2. Auto-discover and include files for last timestep
        all_files = list(dataset_dir.iterdir())

        # Pattern 1: prefix_{timestep}.ext or prefix_{timestep}
        pattern1 = re.compile(r'^([a-zA-Z_]+)_(\d+)(?:\.(.+))?$')
        # Pattern 2: Ovito_dump.{timestep}.ext
        pattern2 = re.compile(r'^(Ovito_dump)\.(\d+)\.(.+)$')

        # Track which file types we've found for the last timestep
        found_types = set()

        for f in all_files:
            if not f.is_file():
                continue

            # Try pattern 1
            match = pattern1.match(f.name)
            if match:
                prefix = match.group(1)
                timestep = int(match.group(2))
                ext = match.group(3)

                if timestep == last_timestep and prefix not in found_types:
                    files.append(f)
                    found_types.add(prefix)
                continue

            # Try pattern 2 (Ovito_dump)
            match = pattern2.match(f.name)
            if match:
                timestep = int(match.group(2))

                if timestep == last_timestep and 'Ovito_dump' not in found_types:
                    files.append(f)
                    found_types.add('Ovito_dump')
                continue

        # 3. Include first snapshot for comparison (optional)
        first_snapshot_candidates = [
            dataset_dir / 'lmp_snapshot_0.pkl',
            dataset_dir / f'lmp_snapshot_0'
        ]
        for candidate in first_snapshot_candidates:
            if candidate.exists():
                files.append(candidate)
                break

        return files

    @staticmethod
    def _render_thumbnail(ase_atoms, mfid: str):
        """
        Generate thumbnail visualization from ASE Atoms.

        Args:
            ase_atoms: ASE Atoms object

        Returns:
            str: Path to thumbnail file
        """
        from ase.io import write
        import tempfile
        import logging

        # Suppress matplotlib's verbose output
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

        # Use system temp directory (platform-independent)
        temp_dir = tempfile.gettempdir()
        thumbnail_dir = os.path.join(temp_dir, 'crucible_thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)

        # Use timestep or create unique name
        file_path = os.path.join(thumbnail_dir, f'{mfid}.png')

        # Wrap atoms to unit cell
        ase_atoms.wrap()

        # Write thumbnail
        write(file_path, ase_atoms,
              format='png',
              show_unit_cell=2,
              scale=20,
              maxwidth=512,
              #rotation='90x,0y,90z'
              )

        return file_path
