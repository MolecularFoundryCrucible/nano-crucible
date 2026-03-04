#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsers for various data formats to upload to Crucible.

Available parsers:
    - LAMMPSParser: Parse LAMMPS molecular dynamics simulations
    - MatEnsembleLmpParser: Parse MatEnsemble MD-ML datasets (LAMMPS + bispectrum)
"""

from .base import BaseParser
from .lammps import LAMMPSParser
from .matensemble import MatEnsembleLmpParser
from .emdvelox import EMDVeloxParser

# Registry mapping dataset type names to parser classes
# All keys should be lowercase
PARSER_REGISTRY = {
    'base': BaseParser,
    'lammps': LAMMPSParser,
    'matensemble': MatEnsembleLmpParser,
    'emdvelox': EMDVeloxParser
}

def get_parser(dataset_type):
    """
    Get the appropriate parser class for a given dataset type.

    Args:
        dataset_type (str): The type of dataset (e.g., 'lammps', 'LAMMPS', 'xrd')
                           Case-insensitive.

    Returns:
        class: The parser class for that dataset type

    Raises:
        ValueError: If dataset_type is not supported
    """
    # Normalize to lowercase for case-insensitive lookup
    dataset_type_lower = dataset_type.lower()
    parser_class = PARSER_REGISTRY.get(dataset_type_lower)
    if parser_class is None:
        available = ', '.join(sorted(PARSER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown dataset type '{dataset_type}'. "
            f"Available types: {available}"
        )
    return parser_class

__all__ = ['BaseParser', 'LAMMPSParser', 'MatEnsembleLmpParser', 'EMDVeloxParser', 'PARSER_REGISTRY', 'get_parser']
