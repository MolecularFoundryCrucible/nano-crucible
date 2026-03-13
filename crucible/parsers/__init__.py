#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsers for various data formats to upload to Crucible.

Built-in parsers:
    - BaseParser:   Generic upload, no parsing
    - LAMMPSParser: Parse LAMMPS molecular dynamics simulations

Additional parsers can be made available by installing third-party packages
that register them under the ``crucible.parsers`` entry-point group::

    [project.entry-points."crucible.parsers"]
    myparser = "mypackage.mymodule:MyParserClass"
"""

from .base import BaseParser
from .lammps import LAMMPSParser

# Built-in parser registry (lowercase keys)
PARSER_REGISTRY = {
    'base':   BaseParser,
    'lammps': LAMMPSParser,
}

def get_all_parsers():
    """
    Return a dict of all available parsers: built-in + entry-point installed.

    Returns:
        dict: Mapping of parser name (str) → parser class, combining built-ins
              and any parsers registered via the ``crucible.parsers`` entry-point
              group by installed third-party packages.
    """
    all_parsers = dict(PARSER_REGISTRY)
    try:
        from importlib.metadata import entry_points
        for ep in entry_points(group="crucible.parsers"):
            if ep.name.lower() not in all_parsers:
                try:
                    all_parsers[ep.name.lower()] = ep.load()
                except Exception:
                    pass
    except Exception:
        pass
    return all_parsers


def get_parser(dataset_type):
    """
    Get the appropriate parser class for a given dataset type.

    Checks the built-in registry first, then discovers parsers registered
    by third-party packages via the ``crucible.parsers`` entry-point group.
    Installing a package that declares::

        [project.entry-points."crucible.parsers"]
        myparser = "mypackage.mymodule:MyParserClass"

    makes ``get_parser('myparser')`` available automatically.

    Args:
        dataset_type (str): The type of dataset (e.g., 'lammps', 'xrd').
                            Case-insensitive.

    Returns:
        class: The parser class for that dataset type.

    Raises:
        ValueError: If dataset_type is not found in the built-in registry
                    or any installed entry points.
    """
    dataset_type_lower = dataset_type.lower()
    all_parsers = get_all_parsers()

    if dataset_type_lower in all_parsers:
        return all_parsers[dataset_type_lower]

    available = ', '.join(sorted(all_parsers.keys()))
    raise ValueError(
        f"Unknown dataset type '{dataset_type}'. "
        f"Available types: {available}. "
        f"Additional parsers can be installed via third-party packages."
    )


__all__ = ['BaseParser', 'LAMMPSParser', 'PARSER_REGISTRY', 'get_parser', 'get_all_parsers']
