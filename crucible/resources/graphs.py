#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graph resource operations for Crucible API.

Provides access to entity graph traversal endpoints.
"""

import logging
from typing import Optional
from .base import BaseResource

logger = logging.getLogger(__name__)


class GraphOperations(BaseResource):
    """Entity graph traversal operations.

    Access via: client.graphs.get(), or as a convenience via
    client.samples.graph() / client.datasets.graph().
    """

    def get(self, entity_id: str, recursive: bool = False, as_networkx: bool = False):
        """Return the graph of entities connected to entity_id.

        By default returns only first-degree neighbours (direct parents,
        children, and cross-linked entities). Pass recursive=True for the
        full connected component.

        Args:
            entity_id (str): Unique ID of any sample or dataset.
            recursive (bool): If True, traverse the full connected component.
            as_networkx (bool): If True, return a networkx DiGraph instead
                of the raw node-link dict. Requires networkx to be installed.

        Returns:
            dict | networkx.DiGraph: Node-link graph data.
        """
        params = {"recursive": recursive} if recursive else {}
        data = self._request("get", f"/entity_graph_cte/{entity_id}", params=params)
        if as_networkx:
            import networkx as nx
            from networkx.readwrite import json_graph
            return json_graph.node_link_graph(data, directed=True)
        return data

    def project(self, project_id: str, as_networkx: bool = False):
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
