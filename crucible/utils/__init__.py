#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crucible utility package.

Submodules
----------
io          : File I/O, hashing, time, and image helpers
deprecation : API lifecycle decorators (_deprecated, _removed)
"""

from .io import run_shell, checkhash, get_tz_isoformat, check_small_files, is_base64, data2thumbnail, parse_timestamp, hash_file, storage_display_name
from .deprecation import _deprecated, _removed

__all__ = [
    # io
    'run_shell',
    'checkhash',
    'get_tz_isoformat',
    'parse_timestamp',
    'check_small_files',
    'is_base64',
    'data2thumbnail',
    'hash_file',
    'storage_display_name',
    # deprecation
    '_deprecated',
    '_removed',
]
