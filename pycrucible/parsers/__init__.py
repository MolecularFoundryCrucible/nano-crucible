#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsers for various data formats to upload to Crucible.

Available parsers:
    - LAMMPSParser: Parse LAMMPS molecular dynamics simulations
    - MDNoteParser: Parse markdown notes with linked images
"""

from .base import BaseParser
from .lammps import LAMMPSParser
from .mdnote import MDNoteParser

# Registry mapping dataset type names to parser classes
PARSER_REGISTRY = {
    'lammps': LAMMPSParser,
    'LAMMPS': LAMMPSParser,
    'md': LAMMPSParser,  # Alias
    'mdnote': MDNoteParser,
    'MDNote': MDNoteParser,
    'markdown': MDNoteParser,  # Alias
    'note': MDNoteParser,  # Alias
}

def get_parser(dataset_type):
    """
    Get the appropriate parser class for a given dataset type.

    Args:
        dataset_type (str): The type of dataset (e.g., 'lammps', 'xrd')

    Returns:
        class: The parser class for that dataset type

    Raises:
        ValueError: If dataset_type is not supported
    """
    parser_class = PARSER_REGISTRY.get(dataset_type)
    if parser_class is None:
        available = ', '.join(sorted(set(PARSER_REGISTRY.keys())))
        raise ValueError(
            f"Unknown dataset type '{dataset_type}'. "
            f"Available types: {available}"
        )
    return parser_class

__all__ = ['BaseParser', 'LAMMPSParser', 'MDNoteParser', 'PARSER_REGISTRY', 'get_parser']
