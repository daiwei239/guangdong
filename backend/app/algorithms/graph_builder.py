from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx
import torch

from app.schemas.resource_schema import FrontendResourceEdge, FrontendResourceNode, ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


def add_reverse_edges(
    edge_index_dict: Dict[Tuple[str, str, str], torch.Tensor],
    edge_attr_dict: Dict[Tuple[str, str, str], torch.Tensor],
) -> Tuple[Dict[Tuple[str, str, str], torch.Tensor], Dict[Tuple[str, str, str], torch.Tensor]]:
    """为每条异构关系边自动补充 REV_ 反向边。"""
    merged_edge_index_dict = dict(edge_index_dict)
    merged_edge_attr_dict = dict(edge_attr_dict)

    for edge_type, edge_index in list(edge_index_dict.items()):
        source_type, relation_type, target_type = edge_type
        reverse_relation = relation_type if relation_type.startswith("REV_") else "REV_{0}".format(relation_type)
        reverse_edge_type = (target_type, reverse_relation, source_type)
        if reverse_edge_type in merged_edge_index_dict:
            continue
        merged_edge_index_dict[reverse_edge_type] = edge_index.flip(0).contiguous()
        edge_attr = edge_attr_dict.get(edge_type)
        if edge_attr is not None:
            merged_edge_attr_dict[reverse_edge_type] = edge_attr.clone()
    return merged_edge_index_dict, merged_edge_attr_dict


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
