#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graph resource operations for Crucible API.

Provides access to entity graph traversal endpoints.
"""

import logging
from typing import Any, Optional
from .base import BaseResource
from ..utils.deprecation import _deprecated_parameter

logger = logging.getLogger(__name__)


class GraphOperations(BaseResource):
    """Entity graph traversal operations.

    Access via: client.graphs.get(), or as a convenience via
    client.samples.graph() / client.datasets.graph().
    """

    @_deprecated_parameter('entity_id', 'resource_mfid')
    def get(self, resource_mfid: str, recursive: bool = False,
            as_networkx: bool = False) -> Any:
        """Return the graph of entities connected to a dataset or sample MFID.

        By default returns only first-degree neighbours (direct parents,
        children, and cross-linked entities). Pass recursive=True for the
        full connected component.

        Args:
            resource_mfid (str): Dataset or sample MFID.
            recursive (bool): If True, traverse the full connected component.
            as_networkx (bool): If True, return a networkx DiGraph instead
                of the raw node-link dict. Requires networkx to be installed.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        params = {"recursive": recursive} if recursive else {}
        data = self._request(
            "get", f"/entity_graph_cte/{resource_mfid}", params=params)
        if as_networkx:
            import networkx as nx
            from networkx.readwrite import json_graph
            return json_graph.node_link_graph(data, directed=True)
        return data

    def project(self, project_id: str, as_networkx: bool = False) -> Any:
        """Return the full graph of all entities in a project.

        Args:
            project_id (str): Project identifier.
            as_networkx (bool): If True, return a networkx DiGraph instead
                of the raw node-link dict. Requires networkx to be installed.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        data = self._request("get", f"/project_graph/{project_id}")
        if as_networkx:
            import networkx as nx
            from networkx.readwrite import json_graph
            return json_graph.node_link_graph(data, directed=True)
        return data
