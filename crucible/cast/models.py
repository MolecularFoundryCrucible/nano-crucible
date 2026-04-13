#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic models for the .crux file format.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional
from pydantic import BaseModel, ConfigDict


class CastConfig(BaseModel):
    """Global defaults declared in a 'config' document."""
    version: str = "1"
    project_id: Optional[str] = None

    model_config = ConfigDict(extra='ignore')


class CastDataset(BaseModel):
    """A dataset entity parsed from a .crux file."""
    id: Optional[str] = None
    name: str
    files: List[str] = []
    measurement: Optional[str] = None
    instrument: Optional[str] = None
    data_format: Optional[str] = None
    session: Optional[str] = None
    public: bool = False
    keywords: List[str] = []
    metadata: Dict[str, Any] = {}
    timestamp: Optional[str] = None
    project_id: Optional[str] = None
    parser: Optional[str] = None    # client-side parser (e.g. 'lammps'); None = direct upload
    ingestor: Optional[str] = None  # server-side ingestor class (e.g. 'DigitalMicrographIngestor')

    model_config = ConfigDict(extra='ignore')


class CastSample(BaseModel):
    """A sample entity parsed from a .crux file."""
    id: Optional[str] = None
    name: str
    type: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[str] = None
    project_id: Optional[str] = None

    model_config = ConfigDict(extra='ignore')


class Link(NamedTuple):
    """A relationship between two entities, identified by their local IDs."""
    kind: str    # 'dataset_child' | 'sample_child' | 'dataset_sample'
    source: str  # local_id of the source entity
    target: str  # local_id of the target entity


@dataclass
class CastPlan:
    """Resolved, validated plan ready for execution."""
    config: CastConfig
    datasets: Dict[str, CastDataset]
    samples: Dict[str, CastSample]
    links: List[Link]
    lock_path: Path
    base_dir: Path
    prefilled: Dict[str, str] = field(default_factory=dict)

    def __repr__(self):
        return (
            f"CastPlan("
            f"{len(self.datasets)} dataset(s), "
            f"{len(self.samples)} sample(s), "
            f"{len(self.links)} link(s))"
        )
