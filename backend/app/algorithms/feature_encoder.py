from typing import Dict, Mapping

import torch
from torch import Tensor, nn


class ResourceFeatureEncoder(nn.Module):
    """类型感知的资源特征编码器。"""

    def __init__(self, input_dims: Dict[str, int], hidden_dim: int = 64) -> None:
        super().__init__()
        self.input_dims = dict(input_dims)
        self.hidden_dim = hidden_dim
        self.encoders = nn.ModuleDict()
        for resource_type, input_dim in self.input_dims.items():
            self.encoders[resource_type] = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
            )

    def forward(self, x_dict: Mapping[str, Tensor]) -> Dict[str, Tensor]:
        encoded: Dict[str, Tensor] = {}
        device = None
        for tensor in x_dict.values():
            device = tensor.device
            break
        for resource_type, input_dim in self.input_dims.items():
            tensor = x_dict.get(resource_type)
            if tensor is None:
                encoded[resource_type] = torch.zeros((0, self.hidden_dim), dtype=torch.float32, device=device)
                continue
            if tensor.numel() == 0:
                encoded[resource_type] = torch.zeros((tensor.shape[0], self.hidden_dim), dtype=tensor.dtype, device=tensor.device)
                continue
            encoded[resource_type] = self.encoders[resource_type](tensor)
        return encoded
