"""Task-conditioned heterogeneous resource matching model."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HGTConv

from resource_mapping.step_01_resource_description.constants import NODE_TYPES


class ResourceHGTEncoder(nn.Module):
    """Encode a heterogeneous resource graph with HGTConv."""

    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], hidden_dim: int = 128, num_layers: int = 2, num_heads: int = 4, dropout: float = 0.2) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.node_types = list(metadata[0])
        self.safe_node_types = [self._key(node_type) for node_type in self.node_types]
        self.to_safe = dict(zip(self.node_types, self.safe_node_types))
        self.to_public = dict(zip(self.safe_node_types, self.node_types))
        self.safe_metadata = (
            self.safe_node_types,
            [(self.to_safe[src], rel, self.to_safe[dst]) for src, rel, dst in metadata[1]],
        )
        self.proj = nn.ModuleDict({self._key(node_type): nn.LazyLinear(hidden_dim) for node_type in self.node_types})
        self.convs = nn.ModuleList([HGTConv(hidden_dim, hidden_dim, self.safe_metadata, heads=num_heads) for _ in range(num_layers)])
        self.norms = nn.ModuleList([nn.ModuleDict({self._key(node_type): nn.LayerNorm(hidden_dim) for node_type in self.node_types}) for _ in range(num_layers)])
        self.dropout = nn.Dropout(dropout)

    @staticmethod
    def _key(node_type: str) -> str:
        """Return a ModuleDict-safe key for a PyG node type."""

        return f"node_{node_type}"

    def forward(self, x_dict: dict[str, torch.Tensor], edge_index_dict: dict[tuple[str, str, str], torch.Tensor]) -> dict[str, torch.Tensor]:
        """Return node embeddings per type."""

        h = {self.to_safe[node_type]: torch.relu(self.proj[self._key(node_type)](x)) for node_type, x in x_dict.items()}
        safe_edge_index_dict = {(self.to_safe[src], rel, self.to_safe[dst]): edge_index for (src, rel, dst), edge_index in edge_index_dict.items()}
        for layer_idx, conv in enumerate(self.convs):
            h_new = conv(h, safe_edge_index_dict)
            h = {
                node_type: self.dropout(torch.relu(self.norms[layer_idx][node_type](h_new.get(node_type, h[node_type]) if h_new.get(node_type) is not None else h[node_type])))
                for node_type in h
            }
        return {self.to_public[node_type]: emb for node_type, emb in h.items()}


class TaskEncoder(nn.Module):
    """Encode task requirement vectors with an MLP."""

    def __init__(self, task_dim: int, hidden_dim: int = 128, dropout: float = 0.2) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(task_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden_dim, hidden_dim))

    def forward(self, task_vector: torch.Tensor) -> torch.Tensor:
        """Encode task vectors."""

        return self.net(task_vector)


class CandidatePooler(nn.Module):
    """Pool candidate subnet node embeddings into one vector per candidate."""

    def __init__(self, hidden_dim: int = 128) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim

    def forward(self, node_emb_dict: dict[str, torch.Tensor], candidate_nodes: list[dict[str, list[int]]]) -> torch.Tensor:
        """Mean-pool by type, then mean-pool across types."""

        device = next(iter(node_emb_dict.values())).device
        outputs = []
        for candidate in candidate_nodes:
            type_embs = []
            for node_type in NODE_TYPES:
                indices = candidate.get(node_type, [])
                if indices and node_type in node_emb_dict:
                    idx = torch.tensor(indices, dtype=torch.long, device=device)
                    type_embs.append(node_emb_dict[node_type].index_select(0, idx).mean(dim=0))
                else:
                    type_embs.append(torch.zeros(self.hidden_dim, device=device))
            outputs.append(torch.stack(type_embs, dim=0).mean(dim=0))
        return torch.stack(outputs, dim=0)


class TaskConditionedResourceMatcher(nn.Module):
    """Full task-candidate resource matching model."""

    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], task_dim: int, hidden_dim: int = 128, num_layers: int = 2, num_heads: int = 4, dropout: float = 0.2) -> None:
        super().__init__()
        self.resource_encoder = ResourceHGTEncoder(metadata, hidden_dim, num_layers, num_heads, dropout)
        self.task_encoder = TaskEncoder(task_dim, hidden_dim, dropout)
        self.pooler = CandidatePooler(hidden_dim)
        self.scorer = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, data: HeteroData, task_vectors: torch.Tensor, candidate_nodes_list: list[dict[str, list[int]]]) -> tuple[torch.Tensor, torch.Tensor]:
        """Score task-candidate pairs."""

        node_emb_dict = self.resource_encoder(data.x_dict, data.edge_index_dict)
        task_emb = self.task_encoder(task_vectors)
        subgraph_emb = self.pooler(node_emb_dict, candidate_nodes_list)
        fusion = torch.cat([subgraph_emb, task_emb, subgraph_emb * task_emb, torch.abs(subgraph_emb - task_emb)], dim=-1)
        logits = self.scorer(fusion)
        return logits, torch.sigmoid(logits)
