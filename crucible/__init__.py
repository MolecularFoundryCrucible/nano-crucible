"""
nano-crucible: National Archive for NSRC Observations - Crucible

Python client library for the Crucible API - the Molecular Foundry data lakehouse.
"""

__version__ = "2.0.0"
__author__ = "mkywall"

from .client import CrucibleClient
from .models import BaseDataset
from . import config

__all__ = ['CrucibleClient', 'BaseDataset', 'config', '__version__', '__author__']
