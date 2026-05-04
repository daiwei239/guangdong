from typing import Dict, Tuple

import torch
from torch import Tensor, nn

from app.algorithms.gnn_encoder import ResourceGraphEncoder
from app.algorithms.task_encoder import TaskEncoder


class TaskResourceMatcher(nn.Module):
    """任务-资源匹配模型，保留给后续训练与辅助评分。"""

    def __init__(
        self,
        input_dims: Dict[str, int],
        task_dim: int,
        hidden_dim: int = 64,
        out_dim: int = 64,
    ) -> None:
        super().__init__()
        self.resource_encoder = ResourceGraphEncoder(input_dims=input_dims, hidden_dim=hidden_dim, out_dim=out_dim)
        self.task_encoder = TaskEncoder(task_dim=task_dim, hidden_dim=hidden_dim)
        self.scorer = nn.Sequential(
            nn.Linear(out_dim + hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, data, task_vec: Tensor) -> Tuple[Tensor, Tensor, Dict[str, Tensor]]:
        z_subgraph, node_embeddings = self.resource_encoder(data)
        z_task = self.task_encoder(task_vec)
        score = self.scorer(torch.cat([z_subgraph, z_task], dim=-1))
        return score, z_subgraph, node_embeddings
