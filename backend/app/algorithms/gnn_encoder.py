from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import torch
from torch import Tensor, nn

from app.algorithms.feature_builder import EDGE_ATTR_DIM, RESOURCE_TYPES
from app.algorithms.feature_encoder import ResourceFeatureEncoder, encoder_module_key

try:
    from torch_geometric.nn import GATConv, HeteroConv
except ImportError:  # pragma: no cover - PyG 不可用时走兜底路径
    GATConv = None
    HeteroConv = None


TASK_TYPE_POOLING_WEIGHTS: Dict[str, Dict[str, float]] = {
    "计算密集型": {"GPU": 0.30, "FPGA": 0.25, "CPU": 0.20, "MEMORY": 0.15, "NIC": 0.05, "STORAGE": 0.03, "SWITCH": 0.02},
    "通信密集型": {"NIC": 0.30, "SWITCH": 0.25, "GPU": 0.20, "MEMORY": 0.15, "CPU": 0.05, "FPGA": 0.03, "STORAGE": 0.02},
    "数据密集型": {"STORAGE": 0.30, "MEMORY": 0.25, "NIC": 0.20, "CPU": 0.10, "GPU": 0.10, "FPGA": 0.03, "SWITCH": 0.02},
    "混合型": {"CPU": 0.15, "GPU": 0.20, "FPGA": 0.10, "MEMORY": 0.20, "STORAGE": 0.15, "NIC": 0.15, "SWITCH": 0.05},
}
DEFAULT_RELATIONS = [
    "CONNECTED_TO",
    "SAME_HOST",
    "SAME_RACK",
    "SHARES_MEMORY",
    "COMPETES_BANDWIDTH",
    "LOW_LATENCY_LINK",
    "SCHEDULING_DEPENDENCY",
]


def projection_module_key(resource_type: str) -> str:
    return encoder_module_key(resource_type)


class ResourceGraphEncoder(nn.Module):
    """异构关系感知资源图编码器。

    编码流程：
        按类型分组的原始特征 -> 类型专属 MLP -> HeteroConv 消息传递
        -> 每个节点的 embedding -> 任务感知的按类型池化。

    如果当前环境没有安装 PyG，本模块仍然会返回一个基于线性投影的兜底
    embedding，这样后端和测试在没有 GPU/GNN 依赖时也可以正常运行。
    """

    def __init__(
        self,
        input_dims: Dict[str, int],
        hidden_dim: int = 64,
        out_dim: int = 64,
        edge_attr_dim: int = EDGE_ATTR_DIM,
        num_layers: int = 2,
        heads: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_dims = dict(input_dims)
        self.hidden_dim = hidden_dim
        self.out_dim = out_dim
        self.edge_attr_dim = edge_attr_dim
        self.num_layers = num_layers
        self.heads = heads
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.ReLU()
        self.feature_encoder = ResourceFeatureEncoder(input_dims, hidden_dim)
        self.out_proj = nn.ModuleDict(
            {projection_module_key(resource_type): nn.Linear(hidden_dim, out_dim) for resource_type in self.input_dims}
        )
        self.fallback_proj = nn.ModuleDict(
            {projection_module_key(resource_type): nn.Linear(hidden_dim, out_dim) for resource_type in self.input_dims}
        )
        self.hetero_layers: Optional[nn.ModuleList] = None
        self.configured_edge_types: List[Tuple[str, str, str]] = []
        self.last_edge_types: List[Tuple[str, str, str]] = []

    def forward(self, data, task_type: Optional[str] = None) -> Tuple[Tensor, Dict[str, Tensor]]:
        x_dict = data.x_dict
        edge_index_dict = self._safe_collect_edge_index_dict(data)
        edge_attr_dict = self.get_edge_attr_dict(data, edge_index_dict, self.edge_attr_dim)
        self.last_edge_types = list(edge_index_dict.keys())

        encoded_x_dict = self.feature_encoder(x_dict)

        if HeteroConv is None or GATConv is None or not edge_index_dict:
            projected_x_dict = self._fallback_project(encoded_x_dict)
            z_subgraph = self.pool_subgraph(projected_x_dict, task_type=task_type)
            return z_subgraph, projected_x_dict

        self._ensure_hetero_layers(edge_index_dict.keys())
        x_state = encoded_x_dict
        for hetero_conv in self.hetero_layers or []:
            updated = hetero_conv(x_state, edge_index_dict, edge_attr_dict=edge_attr_dict)
            x_state = self._merge_with_residual(x_state, updated)

        projected_x_dict = self._project_out(x_state)
        z_subgraph = self.pool_subgraph(projected_x_dict, task_type=task_type)
        return z_subgraph, projected_x_dict

    def get_edge_attr_dict(
        self,
        data,
        edge_index_dict: Mapping[Tuple[str, str, str], Tensor],
        edge_attr_dim: int,
    ) -> Dict[Tuple[str, str, str], Tensor]:
        try:
            raw_edge_attr_dict = data.edge_attr_dict
        except (AttributeError, KeyError):
            raw_edge_attr_dict = {}

        edge_attr_dict: Dict[Tuple[str, str, str], Tensor] = {}
        for edge_type, edge_index in edge_index_dict.items():
            attr = raw_edge_attr_dict.get(edge_type)
            num_edges = edge_index.shape[1] if edge_index.dim() > 1 else 0
            if attr is None:
                edge_attr_dict[edge_type] = torch.zeros((num_edges, edge_attr_dim), dtype=torch.float32, device=edge_index.device)
                continue
            if attr.shape[0] != num_edges:
                edge_attr_dict[edge_type] = torch.zeros((num_edges, edge_attr_dim), dtype=attr.dtype, device=attr.device)
                continue
            if attr.dim() != 2:
                edge_attr_dict[edge_type] = torch.zeros((num_edges, edge_attr_dim), dtype=torch.float32, device=edge_index.device)
                continue
            if attr.shape[1] != edge_attr_dim:
                padded = torch.zeros((num_edges, edge_attr_dim), dtype=attr.dtype, device=attr.device)
                width = min(edge_attr_dim, attr.shape[1])
                padded[:, :width] = attr[:, :width]
                edge_attr_dict[edge_type] = padded
            else:
                edge_attr_dict[edge_type] = attr
        return edge_attr_dict

    def pool_subgraph(self, x_dict: Mapping[str, Tensor], task_type: Optional[str] = None) -> Tensor:
        """将节点 embedding 池化成一个资源子网表示 z_R^k。"""

        type_means: Dict[str, Tensor] = {}
        for resource_type, tensor in x_dict.items():
            if tensor.numel() > 0:
                type_means[resource_type] = tensor.mean(dim=0, keepdim=True)

        if not type_means:
            return torch.zeros((1, self.out_dim), dtype=torch.float32)

        if task_type is None or task_type not in TASK_TYPE_POOLING_WEIGHTS:
            return torch.stack(list(type_means.values()), dim=0).mean(dim=0)

        weights = TASK_TYPE_POOLING_WEIGHTS[task_type]
        present_weights = {resource_type: weights.get(resource_type, 0.0) for resource_type in type_means}
        total_weight = sum(present_weights.values())
        if total_weight <= 0:
            return torch.stack(list(type_means.values()), dim=0).mean(dim=0)

        first_tensor = next(iter(type_means.values()))
        pooled = torch.zeros((1, self.out_dim), dtype=first_tensor.dtype, device=first_tensor.device)
        for resource_type, tensor in type_means.items():
            pooled = pooled + tensor * (present_weights[resource_type] / total_weight)
        return pooled

    def _safe_collect_edge_index_dict(self, data) -> Dict[Tuple[str, str, str], Tensor]:
        try:
            raw = data.edge_index_dict
        except (AttributeError, KeyError):
            return {}
        return dict(raw)

    def _ensure_hetero_layers(self, edge_types: Sequence[Tuple[str, str, str]]) -> None:
        normalized = sorted(set(edge_types))
        if self.hetero_layers is not None and normalized == sorted(self.configured_edge_types):
            return
        self.configured_edge_types = list(normalized)
        self.hetero_layers = nn.ModuleList([self._build_hetero_layer(normalized) for _ in range(self.num_layers)])

    def _build_hetero_layer(self, edge_types: Sequence[Tuple[str, str, str]]) -> nn.Module:
        convs = {}
        for edge_type in edge_types:
            convs[edge_type] = GATConv(
                (-1, -1),
                self.hidden_dim,
                heads=self.heads,
                concat=False,
                edge_dim=self.edge_attr_dim,
                add_self_loops=False,
            )
        return HeteroConv(convs, aggr="sum")

    def _merge_with_residual(self, previous: Mapping[str, Tensor], updated: Mapping[str, Tensor]) -> Dict[str, Tensor]:
        merged: Dict[str, Tensor] = {}
        for resource_type in self.input_dims:
            new_tensor = updated.get(resource_type)
            previous_tensor = previous.get(resource_type)
            if new_tensor is None:
                base = previous_tensor
            else:
                if previous_tensor is not None and previous_tensor.shape == new_tensor.shape:
                    base = previous_tensor + self.dropout(self.activation(new_tensor))
                else:
                    base = self.dropout(self.activation(new_tensor))
            if base is None:
                base = torch.zeros((0, self.hidden_dim), dtype=torch.float32)
            merged[resource_type] = base
        return merged

    def _project_out(self, x_dict: Mapping[str, Tensor]) -> Dict[str, Tensor]:
        projected: Dict[str, Tensor] = {}
        for resource_type in self.input_dims:
            tensor = x_dict.get(resource_type)
            if tensor is None or tensor.numel() == 0:
                device = tensor.device if tensor is not None else None
                projected[resource_type] = torch.zeros((0, self.out_dim), dtype=torch.float32, device=device)
                continue
            projected[resource_type] = self.out_proj[projection_module_key(resource_type)](tensor)
        return projected

    def _fallback_project(self, x_dict: Mapping[str, Tensor]) -> Dict[str, Tensor]:
        projected: Dict[str, Tensor] = {}
        for resource_type in self.input_dims:
            tensor = x_dict.get(resource_type)
            if tensor is None or tensor.numel() == 0:
                device = tensor.device if tensor is not None else None
                projected[resource_type] = torch.zeros((0, self.out_dim), dtype=torch.float32, device=device)
                continue
            projected[resource_type] = self.activation(self.fallback_proj[projection_module_key(resource_type)](tensor))
        return projected
