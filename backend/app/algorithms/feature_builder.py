from collections import defaultdict
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import torch

from app.algorithms.graph_builder import add_reverse_edges
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.utils.normalizer import clamp

try:
    from torch_geometric.data import HeteroData
except ImportError:  # pragma: no cover - fallback path
    HeteroData = None


RESOURCE_TYPES = ["CPU", "GPU", "FPGA", "MEMORY", "STORAGE", "NIC", "SWITCH"]
RESOURCE_INPUT_DIMS: Dict[str, int] = {
    "CPU": 8,
    "GPU": 12,
    "FPGA": 10,
    "MEMORY": 7,
    "STORAGE": 8,
    "NIC": 8,
    "SWITCH": 7,
}
EDGE_ATTR_DIM = 5
TASK_TYPES = ["计算密集型", "数据密集型", "通信密集型", "混合型"]
TASK_INPUT_DIM = 14
DEFAULT_EDGE_ATTR = torch.tensor([0.5, 0.5, 0.5, 0.8, 0.5], dtype=torch.float32)


class SimpleHeteroData:
    """PyG 不可用时的最小 HeteroData 兼容结构。"""

    def __init__(self) -> None:
        self.x_dict: Dict[str, torch.Tensor] = {}
        self.edge_index_dict: Dict[Tuple[str, str, str], torch.Tensor] = {}
        self.edge_attr_dict: Dict[Tuple[str, str, str], torch.Tensor] = {}

    def metadata(self) -> Tuple[List[str], List[Tuple[str, str, str]]]:
        return list(self.x_dict.keys()), list(self.edge_index_dict.keys())


def _normalize(value: float, scale: float, default: float = 0.0) -> float:
    if value is None:
        value = default
    return clamp(float(value) / scale, 0.0, 1.0)


def _score_from_latency(latency_ms: float) -> float:
    return 1.0 - _normalize(latency_ms, 10.0, default=5.0)


def _score_from_congestion(congestion: float) -> float:
    return 1.0 - _normalize(congestion, 1.0, default=0.5)


def _bool_flag(value: object) -> float:
    return 1.0 if bool(value) else 0.0


def _extract_numeric_suffix(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value)
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return default
    return float(digits)


class ResourceFeatureBuilder:
    """将不同资源类型的原始属性构造成归一化特征向量。"""

    def build_feature_vector(self, resource: ResourceNodeRead) -> List[float]:
        builders = {
            "CPU": self._build_cpu_features,
            "GPU": self._build_gpu_features,
            "FPGA": self._build_fpga_features,
            "MEMORY": self._build_memory_features,
            "STORAGE": self._build_storage_features,
            "NIC": self._build_nic_features,
            "SWITCH": self._build_switch_features,
        }
        features = builders[resource.type](resource)
        return [float(clamp(value, 0.0, 1.0)) for value in features]

    def _build_cpu_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        return [
            _normalize(static.get("cores", 0), 128.0),
            _normalize(static.get("frequency", 0), 5.0),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _normalize(dynamic.get("queue_length", 0), 32.0),
            _normalize(dynamic.get("power_watt", 0), 500.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_gpu_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        fp16 = static.get("fp16_tflops", 0)
        fp32 = static.get("fp32_tflops", fp16 * 0.5)
        interconnect = static.get("interconnect", "PCIe")
        interconnect_score = {"PCIe": 0.4, "NVLink": 0.85, "InfinityFabric": 0.9}.get(interconnect, 0.5)
        return [
            _normalize(static.get("memory_total", 0), 120.0),
            _normalize(dynamic.get("memory_free", 0), 120.0),
            _normalize(fp16, 400.0),
            _normalize(fp32, 200.0),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _normalize(dynamic.get("temperature", 0), 100.0),
            _normalize(dynamic.get("power_watt", 0), 700.0),
            interconnect_score,
            _normalize(dynamic.get("queue_length", 0), 32.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_fpga_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        return [
            _normalize(static.get("logic_units", 0), 4000000.0),
            _normalize(static.get("dsp_blocks", 0), 20000.0),
            _normalize(static.get("bram", 0), 20000.0),
            _normalize(static.get("reconfig_time_ms", 0), 1000.0),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _normalize(dynamic.get("power_watt", 0), 500.0),
            _normalize(dynamic.get("temperature", 0), 100.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_memory_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        capacity = static.get("capacity_gb", 0)
        free_capacity = dynamic.get("memory_free", capacity)
        return [
            _normalize(capacity, 2048.0),
            _normalize(free_capacity, 2048.0),
            _normalize(static.get("bandwidth_gbps", 0), 800.0),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_storage_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        capacity = static.get("capacity_tb", 0)
        free_capacity = dynamic.get("memory_free", capacity)
        return [
            _normalize(capacity, 64.0),
            _normalize(free_capacity, 64.0),
            _normalize(static.get("throughput_gbps", 0), 100.0),
            _normalize(static.get("iops", 0), 5000000.0),
            _normalize(static.get("latency_ms", 0), 10.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_nic_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        return [
            _normalize(static.get("bandwidth_gbps", 0), 400.0),
            _normalize(static.get("latency_ms", 0), 10.0),
            _bool_flag(static.get("rdma_enabled", False)),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _normalize(dynamic.get("packet_loss", 0), 1.0),
            _bool_flag(dynamic.get("available", False)),
            *self._build_topo_features(resource),
        ]

    def _build_switch_features(self, resource: ResourceNodeRead) -> List[float]:
        static = resource.static_attrs
        dynamic = resource.dynamic_state
        return [
            _normalize(static.get("ports", 0), 128.0),
            _normalize(static.get("bandwidth_gbps", 0), 800.0),
            _normalize(static.get("latency_ms", 0), 10.0),
            _normalize(dynamic.get("utilization", 0), 100.0),
            _normalize(dynamic.get("congestion", 0), 1.0),
            *self._build_topo_features(resource),
        ]

    def _build_topo_features(self, resource: ResourceNodeRead) -> List[float]:
        topo = getattr(resource, "topo_context", {}) or {}
        rack_value = topo.get("rack_id") or topo.get("rack_index") or resource.host_id
        tier_value = topo.get("network_tier")
        if tier_value is None:
            hop_level = topo.get("hop_level")
            tier_value = hop_level if hop_level is not None else 1.0
        rack_norm = _normalize(_extract_numeric_suffix(rack_value, default=1.0), 16.0, default=1.0)
        tier_norm = _normalize(float(tier_value), 4.0, default=1.0)
        return [rack_norm, tier_norm]

    def build_edge_attr(self, edge: ResourceEdgeRead) -> List[float]:
        payload = edge.model_dump() if hasattr(edge, "model_dump") else edge.dict()
        bandwidth_norm = _normalize(payload.get("bandwidth_gbps"), 400.0, default=200.0)
        latency_norm = _score_from_latency(payload.get("latency_ms"))
        congestion_norm = _score_from_congestion(payload.get("congestion"))
        reliability_norm = _normalize(payload.get("reliability"), 1.0, default=0.8)
        weight = clamp(float(payload.get("weight", 0.5)), 0.0, 1.0)
        return [
            float(bandwidth_norm or DEFAULT_EDGE_ATTR[0]),
            float(latency_norm if payload.get("latency_ms") is not None else DEFAULT_EDGE_ATTR[1]),
            float(congestion_norm if payload.get("congestion") is not None else DEFAULT_EDGE_ATTR[2]),
            float(reliability_norm or DEFAULT_EDGE_ATTR[3]),
            weight,
        ]


def build_raw_feature_tensors(resources: Sequence[ResourceNodeRead]) -> Dict[str, torch.Tensor]:
    builder = ResourceFeatureBuilder()
    grouped: Dict[str, List[List[float]]] = {resource_type: [] for resource_type in RESOURCE_TYPES}
    for resource in resources:
        grouped[resource.type].append(builder.build_feature_vector(resource))

    x_dict: Dict[str, torch.Tensor] = {}
    for resource_type in RESOURCE_TYPES:
        rows = grouped[resource_type]
        if rows:
            x_dict[resource_type] = torch.tensor(rows, dtype=torch.float32)
        else:
            x_dict[resource_type] = torch.zeros((0, RESOURCE_INPUT_DIMS[resource_type]), dtype=torch.float32)
    return x_dict


def build_task_feature_tensor(task: TaskProfileRead) -> torch.Tensor:
    one_hot = [1.0 if task.task_type == task_type else 0.0 for task_type in TASK_TYPES]
    task_vec = [
        _normalize(task.compute_req.get("cpu_cores", 0), 128.0),
        _normalize(task.compute_req.get("gpu_count", 0), 16.0),
        _normalize(task.compute_req.get("fp16_tflops", 0), 400.0),
        _normalize(task.memory_req.get("capacity_gb", 0), 2048.0),
        _normalize(task.storage_req.get("capacity_tb", 0), 64.0),
        _normalize(task.storage_req.get("throughput_gbps", 0), 100.0),
        _normalize(task.network_req.get("bandwidth_gbps", 0), 400.0),
        _normalize(task.network_req.get("latency_ms", 0), 10.0),
        _normalize(task.energy_limit, 5000.0),
        _normalize(task.qos_deadline_sec, 600.0),
    ] + one_hot
    return torch.tensor(task_vec, dtype=torch.float32).unsqueeze(0)


def build_edge_index_and_attr_dict(
    resources: Sequence[ResourceNodeRead],
    edges: Sequence[ResourceEdgeRead],
) -> Tuple[Dict[Tuple[str, str, str], torch.Tensor], Dict[Tuple[str, str, str], torch.Tensor]]:
    builder = ResourceFeatureBuilder()
    node_index_by_type: Dict[str, Dict[str, int]] = {resource_type: {} for resource_type in RESOURCE_TYPES}
    for resource_type in RESOURCE_TYPES:
        type_nodes = [resource for resource in resources if resource.type == resource_type]
        node_index_by_type[resource_type] = {node.id: index for index, node in enumerate(type_nodes)}

    resource_by_id = {resource.id: resource for resource in resources}
    grouped_edges: Dict[Tuple[str, str, str], List[List[int]]] = defaultdict(list)
    grouped_attrs: Dict[Tuple[str, str, str], List[List[float]]] = defaultdict(list)

    for edge in edges:
        source_resource = resource_by_id.get(edge.source)
        target_resource = resource_by_id.get(edge.target)
        if source_resource is None or target_resource is None:
            continue
        relation = edge.relation_type.upper()
        source_type = source_resource.type
        target_type = target_resource.type
        source_index = node_index_by_type[source_type].get(edge.source)
        target_index = node_index_by_type[target_type].get(edge.target)
        if source_index is None or target_index is None:
            continue
        edge_type = (source_type, relation, target_type)
        grouped_edges[edge_type].append([source_index, target_index])
        grouped_attrs[edge_type].append(builder.build_edge_attr(edge))

    edge_index_dict: Dict[Tuple[str, str, str], torch.Tensor] = {}
    edge_attr_dict: Dict[Tuple[str, str, str], torch.Tensor] = {}
    for edge_type, index_pairs in grouped_edges.items():
        edge_index_dict[edge_type] = torch.tensor(index_pairs, dtype=torch.long).t().contiguous()
        edge_attr_dict[edge_type] = torch.tensor(grouped_attrs[edge_type], dtype=torch.float32)

    return add_reverse_edges(edge_index_dict, edge_attr_dict)


def build_mock_heterodata_from_resources(
    resources: Sequence[ResourceNodeRead],
    edges: Sequence[ResourceEdgeRead],
):
    data = HeteroData() if HeteroData is not None else SimpleHeteroData()
    x_dict = build_raw_feature_tensors(resources)
    edge_index_dict, edge_attr_dict = build_edge_index_and_attr_dict(resources, edges)

    if HeteroData is not None and isinstance(data, HeteroData):
        for resource_type, tensor in x_dict.items():
            data[resource_type].x = tensor
        for edge_type, edge_index in edge_index_dict.items():
            data[edge_type].edge_index = edge_index
            data[edge_type].edge_attr = edge_attr_dict[edge_type]
    else:
        data.x_dict = x_dict
        data.edge_index_dict = edge_index_dict
        data.edge_attr_dict = edge_attr_dict
    return data
