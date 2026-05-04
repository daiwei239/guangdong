from typing import Dict, Iterable, List, Optional, Sequence, Set

import networkx as nx

from app.schemas.resource_schema import FrontendResourceEdge, FrontendResourceNode, ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


class GraphBuilder:
    """负责 NetworkX 资源图构建与前端大屏结构转换。"""

    def build_graph(self, resources: Sequence[ResourceNodeRead], edges: Sequence[ResourceEdgeRead]) -> nx.Graph:
        graph = nx.Graph()
        for resource in resources:
            graph.add_node(resource.id, **model_dump_compat(resource))
        for edge in edges:
            graph.add_edge(edge.source, edge.target, **model_dump_compat(edge))
        return graph

    def to_frontend_snapshot(
        self,
        resources: Sequence[ResourceNodeRead],
        edges: Sequence[ResourceEdgeRead],
        candidate_node_ids: Optional[Set[str]] = None,
        top1_node_ids: Optional[Set[str]] = None,
        candidate_edge_ids: Optional[Set[str]] = None,
        top1_edge_ids: Optional[Set[str]] = None,
    ) -> Dict[str, List[Dict]]:
        candidate_node_ids = candidate_node_ids or set()
        top1_node_ids = top1_node_ids or set()
        candidate_edge_ids = candidate_edge_ids or set()
        top1_edge_ids = top1_edge_ids or set()

        nodes = []
        for resource in resources:
            nodes.append(
                FrontendResourceNode(
                    id=resource.id,
                    label=resource.name,
                    type=resource.type,
                    cluster_id=resource.cluster_id,
                    x=float(abs(hash(resource.id)) % 700),
                    y=float(abs(hash(resource.host_id)) % 500),
                    status="online" if resource.dynamic_state.get("available") else "busy",
                    utilization=float(resource.dynamic_state.get("utilization", 0.0)),
                    available=bool(resource.dynamic_state.get("available", False)),
                    is_candidate=resource.id in candidate_node_ids,
                    is_top1=resource.id in top1_node_ids,
                ).model_dump()
            )

        frontend_edges = []
        for edge in edges:
            frontend_edges.append(
                FrontendResourceEdge(
                    id=edge.id,
                    source=edge.source,
                    target=edge.target,
                    relation_type=edge.relation_type,
                    bandwidth_gbps=edge.bandwidth_gbps,
                    latency_ms=edge.latency_ms,
                    is_candidate_edge=edge.id in candidate_edge_ids,
                    is_top1_edge=edge.id in top1_edge_ids,
                ).model_dump()
            )
        return {"nodes": nodes, "edges": frontend_edges}
