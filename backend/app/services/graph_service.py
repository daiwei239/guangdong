from typing import Sequence

import networkx as nx

from app.algorithms.graph_builder import GraphBuilder
from app.core.neo4j_client import Neo4jGraphClient
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


class GraphService:
    def __init__(self) -> None:
        self.builder = GraphBuilder()
        self.neo4j_client = Neo4jGraphClient()
        self._graph = nx.Graph()

    def build_networkx_graph(self, resources: Sequence[ResourceNodeRead], edges: Sequence[ResourceEdgeRead]) -> nx.Graph:
        self._graph = self.builder.build_graph(resources, edges)
        return self._graph

    def sync_to_neo4j(self, resources: Sequence[ResourceNodeRead], edges: Sequence[ResourceEdgeRead]) -> None:
        self.neo4j_client.load_graph_from_resources(
            [model_dump_compat(resource) for resource in resources],
            [model_dump_compat(edge) for edge in edges],
        )

    def get_graph(self) -> nx.Graph:
        return self._graph


graph_service = GraphService()
