from typing import Dict, Mapping, Optional

import torch
from torch import Tensor, nn


def encoder_module_key(resource_type: str) -> str:
    """为资源类型生成一个对 PyTorch 安全的 ModuleDict key。

    PyTorch 的 nn.Module 本身已经包含 ``.cpu()`` 等方法。如果后续有人把
    小写资源类型名（例如 ``"cpu"``）直接作为 ModuleDict 的 key，PyTorch 会
    报 ``KeyError: attribute 'cpu' already exists``。这里统一加前缀，可以
    同时兼容大写和小写资源类型名。
    """

    return f"resource__{resource_type}"


class ResourceFeatureEncoder(nn.Module):
    """类型感知的资源特征编码器。

    这个模块实现 Step 2 中的类型专属投影：

        h_v = MLP_{tau(v)}(x_v)

    不同资源类型的原始特征语义和输入维度不同，所以每一种资源类型都有一个
    独立的小型 MLP。所有输出都会被投影到同一个 ``hidden_dim``，这样后续
    异构 GNN 就可以统一处理节点 embedding 字典。
    """

    def __init__(self, input_dims: Dict[str, int], hidden_dim: int = 64) -> None:
        super().__init__()
        self.input_dims = dict(input_dims)
        self.hidden_dim = hidden_dim
        self.encoders = nn.ModuleDict()
        for resource_type, input_dim in self.input_dims.items():
            self.encoders[encoder_module_key(resource_type)] = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
            )

    def forward(self, x_dict: Mapping[str, Tensor]) -> Dict[str, Tensor]:
        encoded: Dict[str, Tensor] = {}
        device = self._infer_device(x_dict)

        for resource_type, input_dim in self.input_dims.items():
            tensor = x_dict.get(resource_type)
            if tensor is None:
                encoded[resource_type] = torch.zeros(
                    (0, self.hidden_dim),
                    dtype=torch.float32,
                    device=device,
                )
                continue

            if tensor.numel() == 0:
                encoded[resource_type] = torch.zeros(
                    (tensor.shape[0], self.hidden_dim),
                    dtype=tensor.dtype,
                    device=tensor.device,
                )
                continue

            if tensor.shape[-1] != input_dim:
                raise ValueError(
                    f"资源类型 {resource_type} 的输入维度应为 {input_dim}，"
                    f"但实际 tensor shape 为 {tuple(tensor.shape)}。"
                )

            encoded[resource_type] = self.encoders[encoder_module_key(resource_type)](tensor)
        return encoded

    @staticmethod
    def _infer_device(x_dict: Mapping[str, Tensor]) -> Optional[torch.device]:
        for tensor in x_dict.values():
            return tensor.device
        return None
