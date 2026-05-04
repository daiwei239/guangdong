from typing import Dict, Iterable, List, Optional

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - optional dependency at runtime
    GraphDatabase = None

from app.core.config import get_settings


class Neo4jGraphClient:
    """Neo4j 可选客户端，不可用时自动降级为 no-op。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.neo4j_enabled and GraphDatabase is not None)
        self._driver = None
        if self.enabled:
            try:
                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
            except Exception:
                self.enabled = False
                self._driver = None

    def clear_graph(self) -> None:
        if not self._driver:
            return
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def create_resource_node(self, node: Dict) -> None:
        if not self._driver:
            return
        query = """
        MERGE (n:ResourceNode {id: $id})
        SET n.name = $name,
            n.type = $type,
            n.cluster_id = $cluster_id,
            n.host_id = $host_id,
            n.static_attrs = $static_attrs,
            n.dynamic_state = $dynamic_state,
            n.semantic_tags = $semantic_tags
        """
        with self._driver.session() as session:
            session.run(query, **node)

    def create_resource_edge(self, edge: Dict) -> None:
        if not self._driver:
            return
        query = """
        MATCH (a:ResourceNode {id: $source})
        MATCH (b:ResourceNode {id: $target})
        MERGE (a)-[r:RESOURCE_LINK {id: $id}]->(b)
        SET r.relation_type = $relation_type,
            r.bandwidth_gbps = $bandwidth_gbps,
            r.latency_ms = $latency_ms,
            r.weight = $weight
        """
        with self._driver.session() as session:
            session.run(query, **edge)

    def load_graph_from_resources(self, nodes: Iterable[Dict], edges: Iterable[Dict]) -> None:
        if not self._driver:
            return
        self.clear_graph()
        for node in nodes:
            self.create_resource_node(node)
        for edge in edges:
            self.create_resource_edge(edge)

    def close(self) -> None:
        if self._driver:
            self._driver.close()
