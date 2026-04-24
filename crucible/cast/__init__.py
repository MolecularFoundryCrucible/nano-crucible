#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crucible.cast - .crux file loader and executor.

Load a .crux file and apply it against the Crucible API:

    from crucible.cast import load, CastExecutor
    from crucible.config import get_client

    plan = load("experiment.crux")
    executor = CastExecutor(plan)
    ids = executor.apply(get_client())
"""

from .models import CastConfig, CastDataset, CastSample, CastPlan, Link
from .loader import load
from .executor import CastExecutor
from .builder import Cast, CastDatasetNode, CastSampleNode

__all__ = [
    "load",
    "CastExecutor",
    "Cast",
    "CastDatasetNode",
    "CastSampleNode",
    "CastConfig",
    "CastDataset",
    "CastSample",
    "CastPlan",
    "Link",
]
