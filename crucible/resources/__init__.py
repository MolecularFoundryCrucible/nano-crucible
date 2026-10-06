#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resource classes for Crucible API operations.

Provides organized access to different resource types (datasets, samples, etc.)
while maintaining backward compatibility with the original flat API.
"""

from .files import FileOperations
from .datasets import DatasetOperations  # no longer inherits FileOperations
from .ingestion import IngestionOperations
from .samples import SampleOperations
from .projects import ProjectOperations
from .users import UserOperations
from .instruments import InstrumentOperations
from .deletion import DeletionOperations
from .graphs import GraphOperations
from .account import AccountOperations
from .service_accounts import ServiceAccountOperations
from .access_groups import AccessGroupOperations
from .print import PrintOperations

__all__ = ['FileOperations', 'DatasetOperations', 'IngestionOperations',
           'SampleOperations', 'ProjectOperations',
           'UserOperations', 'InstrumentOperations', 'DeletionOperations', 'GraphOperations',
           'AccountOperations', 'ServiceAccountOperations', 'AccessGroupOperations',
           'PrintOperations']
