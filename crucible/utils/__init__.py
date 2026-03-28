#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crucible utility package.

Submodules
----------
io          : File I/O, hashing, time, and image helpers
deprecation : API lifecycle decorators (_deprecated, _removed)
"""

from .io import run_shell, checkhash, get_tz_isoformat, check_small_files, data2thumbnail, parse_timestamp
from .deprecation import _deprecated, _removed

__all__ = [
    # io
    'run_shell',
    'checkhash',
    'get_tz_isoformat',
    'parse_timestamp',
    'check_small_files',
    'data2thumbnail',
    # deprecation
    '_deprecated',
    '_removed',
]
