from typing import Dict, Sequence, Tuple

import networkx as nx
import torch

from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


def add_reverse_edges(
    edge_index_dict: Dict[Tuple[str, str, str], torch.Tensor],
    edge_attr_dict: Dict[Tuple[str, str, str], torch.Tensor],
) -> Tuple[Dict[Tuple[str, str, str], torch.Tensor], Dict[Tuple[str, str, str], torch.Tensor]]:
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
    def build_graph(self, resources: Sequence[ResourceNodeRead], edges: Sequence[ResourceEdgeRead]) -> nx.Graph:
        graph = nx.Graph()
        for resource in resources:
            graph.add_node(resource.id, **model_dump_compat(resource))
        for edge in edges:
            graph.add_edge(edge.source, edge.target, **model_dump_compat(edge))
        return graph
