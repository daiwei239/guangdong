import torch
from torch import Tensor, nn


class TaskEncoder(nn.Module):
    """任务需求编码器。"""

    def __init__(self, task_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(task_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, task_vec: Tensor) -> Tensor:
        if task_vec.dim() == 1:
            task_vec = task_vec.unsqueeze(0)
        return self.encoder(task_vec)
