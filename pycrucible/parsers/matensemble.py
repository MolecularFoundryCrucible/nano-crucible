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

logger = logging.getLogger(__name__)


class MatEnsembleLmpParser(BaseParser):
    """Parser for MatEnsemble LAMMPS MD-ML datasets."""

    _measurement = "MD-ML"
    _data_format = "LAMMPS-BiSpec"
    _instrument_name = None

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
            self.thumbnail = self._render_thumbnail(snapshot_info['ase_atoms'])

        # Add extracted metadata
        metadata = {
            'temperature_K': temp,
            'lattice_parameter': lattice,
            'natoms': snapshot_info['natoms'],
            'ntimesteps': file_stats['ntimesteps'],
            'last_timestep': last_timestep,
            'simulation_type': 'recrystallization',
            'material': 'MoS2',
            'bispectrum_components': 55,
            'dataset_folder': folder_name,
            **sim_params,
            **file_stats
        }
        self.add_metadata(metadata)

        # Add keywords
        keywords = [
            'molecular-dynamics',
            'machine-learning',
            'bispectrum',
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

        # Extract units
        units_match = re.search(r'units\s+(\w+)', content)
        if units_match:
            params['units'] = units_match.group(1)

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

        # Extract box info
        box_match = re.search(r'triclinic box = \((.*?)\) to \((.*?)\)', content)
        if box_match:
            params['box_lo'] = box_match.group(1)
            params['box_hi'] = box_match.group(2)

        return params

    @staticmethod
    def _count_files(dataset_dir):
        """
        Count files and identify timesteps.

        Args:
            dataset_dir (Path): Dataset directory

        Returns:
            dict: File statistics
        """
        all_files = list(dataset_dir.iterdir())

        # Count by type
        bispec_files = [f for f in all_files if f.name.startswith('bispec_')]
        snapshot_files = [f for f in all_files if f.name.startswith('lmp_snapshot_')]
        ovito_files = [f for f in all_files if f.name.startswith('Ovito_dump.')]
        vtk_files = [f for f in all_files if f.name.endswith('.vtk')]

        # Extract timesteps from snapshot files
        timesteps = []
        for f in snapshot_files:
            match = re.search(r'lmp_snapshot_(\d+)\.pkl', f.name)
            if match:
                timesteps.append(int(match.group(1)))

        timesteps = sorted(timesteps)

        return {
            'total_files': len(all_files),
            'nbispec_files': len(bispec_files),
            'nsnapshot_files': len(snapshot_files),
            'novito_files': len(ovito_files),
            'nvtk_files': len(vtk_files),
            'ntimesteps': len(timesteps),
            'first_timestep': timesteps[0] if timesteps else None,
            'last_timestep': timesteps[-1] if timesteps else None,
            'timesteps': timesteps
        }

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
            import numpy as np
            from ase import Atoms
            from ase.geometry import Cell

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

        # 2. Include last snapshot files
        snapshot_file = dataset_dir / f'lmp_snapshot_{last_timestep}.pkl'
        if snapshot_file.exists():
            files.append(snapshot_file)

        bispec_file = dataset_dir / f'bispec_{last_timestep}.dat'
        if bispec_file.exists():
            files.append(bispec_file)

        ovito_file = dataset_dir / f'Ovito_dump.{last_timestep}.lmp'
        if ovito_file.exists():
            files.append(ovito_file)

        # 3. Include first snapshot for comparison (optional)
        snapshot_0 = dataset_dir / 'lmp_snapshot_0.pkl'
        if snapshot_0.exists():
            files.append(snapshot_0)

        return files

    @staticmethod
    def _render_thumbnail(ase_atoms):
        """
        Generate thumbnail visualization from ASE Atoms.

        Args:
            ase_atoms: ASE Atoms object

        Returns:
            str: Path to thumbnail file
        """
        from ase.io import write
        from pycrucible.config import get_cache_dir
        import logging

        # Suppress matplotlib's verbose output
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

        # Get cache directory
        cache_dir = get_cache_dir()
        thumbnail_dir = os.path.join(cache_dir, 'thumbnails_upload')
        os.makedirs(thumbnail_dir, exist_ok=True)

        # Use timestep or create unique name
        file_path = os.path.join(thumbnail_dir, 'matensemble_thumbnail.png')

        # Wrap atoms to unit cell
        ase_atoms.wrap()

        # Write thumbnail
        write(file_path, ase_atoms,
              format='png',
              show_unit_cell=2,
              scale=20,
              maxwidth=512,
              rotation='10x,10y,0z')

        return file_path
