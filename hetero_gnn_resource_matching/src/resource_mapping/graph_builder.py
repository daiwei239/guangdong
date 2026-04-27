"""Build PyG HeteroData resource graphs from JSON resources and edges."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import torch
from torch_geometric.data import HeteroData

from resource_mapping.constants import EDGE_TYPES, FEATURE_FIELDS, NODE_TYPES


class ResourceGraphBuilder:
    """Convert raw resources and edges into PyG HeteroData."""

    def __init__(self) -> None:
        self.node_id_maps: dict[str, dict[str, int]] = {}
        self.index_to_id: dict[str, list[str]] = {}
        self.resource_by_id: dict[str, dict[str, Any]] = {}

    def build(self, resources: list[dict[str, Any]], edges: list[dict[str, Any]]) -> HeteroData:
        """Build a heterogeneous resource graph."""

        data = HeteroData()
        by_type: dict[str, list[dict[str, Any]]] = {node_type: [] for node_type in NODE_TYPES}
        self.resource_by_id = {r["id"]: r for r in resources}
        for resource in resources:
            by_type[resource["type"]].append(resource)

        for node_type in NODE_TYPES:
            nodes = sorted(by_type[node_type], key=lambda item: item["id"])
            self.index_to_id[node_type] = [n["id"] for n in nodes]
            self.node_id_maps[node_type] = {node_id: idx for idx, node_id in enumerate(self.index_to_id[node_type])}
            fields = FEATURE_FIELDS[node_type]
            rows = []
            for node in nodes:
                features = node.get("features", {})
                rows.append([float(features.get(field, 0.0)) for field in fields])
            if not rows:
                rows = [[0.0 for _ in fields]]
                self.index_to_id[node_type] = []
                self.node_id_maps[node_type] = {}
            data[node_type].x = torch.tensor(rows, dtype=torch.float)
            data[node_type].node_ids = self.index_to_id[node_type]

        edge_buckets: dict[tuple[str, str, str], list[tuple[int, int]]] = defaultdict(list)
        for edge in edges:
            src_type = edge["source_type"]
            dst_type = edge["target_type"]
            rel = edge["relation"]
            etype = (src_type, rel, dst_type)
            src_idx = self.node_id_maps.get(src_type, {}).get(edge["source"])
            dst_idx = self.node_id_maps.get(dst_type, {}).get(edge["target"])
            if src_idx is not None and dst_idx is not None:
                edge_buckets[etype].append((src_idx, dst_idx))

        for etype in EDGE_TYPES:
            pairs = edge_buckets.get(etype, [])
            if pairs:
                edge_index = torch.tensor(pairs, dtype=torch.long).t().contiguous()
            else:
                edge_index = torch.empty((2, 0), dtype=torch.long)
            data[etype].edge_index = edge_index

        return data

    def ids_to_indices(self, candidate_nodes: dict[str, list[str]]) -> dict[str, list[int]]:
        """Convert candidate node ids to per-type indices."""

        out: dict[str, list[int]] = {}
        for node_type, ids in candidate_nodes.items():
            mapping = self.node_id_maps.get(node_type, {})
            out[node_type] = [mapping[node_id] for node_id in ids if node_id in mapping]
        return out
