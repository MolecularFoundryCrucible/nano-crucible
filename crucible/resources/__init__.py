#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resource classes for Crucible API operations.

Provides organized access to different resource types (datasets, samples, etc.)
while maintaining backward compatibility with the original flat API.
"""

from .datasets import DatasetOperations
from .samples import SampleOperations
from .projects import ProjectOperations
from .users import UserOperations
from .instruments import InstrumentOperations

__all__ = ['DatasetOperations', 'SampleOperations', 'ProjectOperations', 'UserOperations', 'InstrumentOperations']
