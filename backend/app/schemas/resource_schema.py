from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_SCHEMA_VERSION = "1.0"
RESOURCE_DESCRIPTION_MODULE = "Module-2.1-ResourceDescription"


class ClusterType(str, Enum):
    HPC = "HPC"
    AI = "AI"
    HYBRID = "Hybrid"
    EDGE = "Edge"


class NodeRole(str, Enum):
    CONTROL = "control"
    COMPUTE = "compute"
    STORAGE = "storage"
    LOGIN = "login"
    MIXED = "mixed"


class NodeStatus(str, Enum):
    READY = "Ready"
    BUSY = "Busy"
    DRAINING = "Draining"
    OFFLINE = "Offline"
    FAULT = "Fault"


class AcceleratorType(str, Enum):
    NPU = "NPU"
    GPU = "GPU"
    NONE = "None"


class MaintenanceState(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    MAINTENANCE = "maintenance"


def validate_cluster_type_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    cluster_type = attributes.get("cluster_type")
    if cluster_type is None:
        return attributes

    try:
        ClusterType(cluster_type)
    except ValueError as exc:
        allowed = ", ".join(cluster.value for cluster in ClusterType)
        raise ValueError(f"cluster_type must be one of: {allowed}") from exc

    return attributes


def validate_node_role_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    node_role = attributes.get("node_role")
    if node_role is None:
        return attributes

    try:
        NodeRole(node_role)
    except ValueError as exc:
        allowed = ", ".join(role.value for role in NodeRole)
        raise ValueError(f"node_role must be one of: {allowed}") from exc

    return attributes


def validate_node_status_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    node_status = metrics.get("node_status")
    if node_status is None:
        return metrics

    try:
        NodeStatus(node_status)
    except ValueError as exc:
        allowed = ", ".join(status.value for status in NodeStatus)
        raise ValueError(f"node_status must be one of: {allowed}") from exc

    return metrics


def validate_maintenance_state_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    reliability_state = metrics.get("reliability_state")
    if not isinstance(reliability_state, dict):
        return metrics

    maintenance_state = reliability_state.get("maintenance_state")
    if maintenance_state is None:
        return metrics

    try:
        MaintenanceState(maintenance_state)
    except ValueError as exc:
        allowed = ", ".join(state.value for state in MaintenanceState)
        raise ValueError(f"maintenance_state must be one of: {allowed}") from exc

    return metrics


def validate_accelerator_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    accelerator = attributes.get("accelerator")
    if not isinstance(accelerator, dict):
        return attributes

    accelerator_type = accelerator.get("accelerator_type")
    if accelerator_type is None:
        return attributes

    try:
        AcceleratorType(accelerator_type)
    except ValueError as exc:
        allowed = ", ".join(accelerator_type.value for accelerator_type in AcceleratorType)
        raise ValueError(f"accelerator_type must be one of: {allowed}") from exc

    return attributes


class RawResourceRecord(BaseModel):
    id: str
    type: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_cluster_type(cls, attributes: Dict[str, Any]) -> Dict[str, Any]:
        attributes = validate_cluster_type_attributes(attributes)
        attributes = validate_node_role_attributes(attributes)
        return validate_accelerator_attributes(attributes)

    @field_validator("metrics")
    @classmethod
    def validate_node_status(cls, metrics: Dict[str, Any]) -> Dict[str, Any]:
        metrics = validate_node_status_metrics(metrics)
        return validate_maintenance_state_metrics(metrics)


class RawTopologyEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    relation_type: str
    bandwidth_gbps: Optional[float] = None
    latency_ms: Optional[float] = None
    weight: Optional[float] = None


class ResourceStateInput(BaseModel):
    source: str = "unknown"
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None
    resources: List[RawResourceRecord] = Field(default_factory=list)
    edges: List[RawTopologyEdge] = Field(default_factory=list)


class SensedResourceState(BaseModel):
    source: str
    timestamp: str
    trace_id: str
    resources: List[RawResourceRecord]
    edges: List[RawTopologyEdge]


class ProcessedResourceRecord(BaseModel):
    id: str
    type: str
    attributes: Dict[str, Any]
    metrics: Dict[str, Any]
    normalized_metrics: Dict[str, float]


class ProcessedResourceState(BaseModel):
    source: str
    timestamp: str
    processed_at: str
    trace_id: str
    resources: List[ProcessedResourceRecord]
    edges: List[RawTopologyEdge]


class MessageEnvelope(BaseModel):
    schema_version: str = DEFAULT_SCHEMA_VERSION
    message_id: str
    message_type: str
    source_module: str
    target_module: List[str]
    timestamp: str
    trace_id: str
    payload: Dict[str, Any]


class FlexibleResourceModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CpuProfile(FlexibleResourceModel):
    cpu_arch: str
    cpu_model: str
    cpu_total_cores: int
    cpu_frequency_ghz: Optional[float] = None
    numa_topology: Optional[Dict[str, Any]] = None


class AcceleratorProfile(FlexibleResourceModel):
    accelerator_type: str
    accelerator_vendor: Optional[str] = None
    accelerator_model: Optional[str] = None
    accelerator_total_count: Optional[int] = None
    accelerator_slice_total: Optional[int] = None
    accelerator_memory_total_gb: Optional[float] = None
    device_ids: Optional[List[str]] = None


class MemoryProfile(FlexibleResourceModel):
    memory_total_gb: float
    memory_bandwidth_gbps: Optional[float] = None


class StorageProfile(FlexibleResourceModel):
    local_storage_total_gb: Optional[float] = None
    shared_storage_access: bool


class NetworkCapability(FlexibleResourceModel):
    network_bandwidth_gbps: float
    interconnect_type: Optional[str] = None


class SoftwareProfile(FlexibleResourceModel):
    os_version: str
    driver_version: Optional[str] = None
    runtime_stack: List[str]
    ai_frameworks: Optional[List[str]] = None
    hpc_libraries: Optional[List[str]] = None
    operator_library: Optional[List[str]] = None


class ResourceProfileNode(FlexibleResourceModel):
    node_id: str
    node_role: str
    cpu: CpuProfile
    accelerator: AcceleratorProfile
    memory: MemoryProfile
    storage: StorageProfile
    network_capability: NetworkCapability
    software: SoftwareProfile


class ResourceProfilePayload(FlexibleResourceModel):
    cluster_id: str
    profile_id: str
    profile_version: str
    cluster_type: str
    region: Optional[str] = None
    generated_time: Optional[str] = None
    nodes: List[ResourceProfileNode]


class CpuState(FlexibleResourceModel):
    cpu_available_cores: int
    cpu_utilization: float


class AcceleratorState(FlexibleResourceModel):
    accelerator_available_count: Optional[int] = None
    accelerator_slice_available: Optional[int] = None
    accelerator_utilization: Optional[float] = None
    accelerator_temperature: Optional[float] = None


class MemoryState(FlexibleResourceModel):
    memory_available_gb: float


class StorageState(FlexibleResourceModel):
    local_storage_available_gb: Optional[float] = None
    storage_read_bw_gbps: Optional[float] = None
    storage_write_bw_gbps: Optional[float] = None


class NetworkState(FlexibleResourceModel):
    network_latency_ms: Optional[float] = None
    packet_loss_rate: Optional[float] = None
    interconnect_type: Optional[str] = None


class ReservedResources(FlexibleResourceModel):
    cpu_cores: Optional[float] = None
    npu_slices: Optional[float] = None
    memory_gb: Optional[float] = None


class QueueState(FlexibleResourceModel):
    queue_length: int
    expected_wait_time_s: Optional[float] = None
    reserved_resources: Optional[ReservedResources] = None


class DynamicState(FlexibleResourceModel):
    running_task_count: int
    load_1min: Optional[float] = None
    resource_fragmentation_score: Optional[float] = None
    availability_score: float


class EnergyState(FlexibleResourceModel):
    power_current_w: Optional[float] = None
    energy_efficiency_score: Optional[float] = None


class ReliabilityState(FlexibleResourceModel):
    failure_rate_recent: Optional[float] = None
    maintenance_state: Optional[str] = None


class ResourceStateNode(FlexibleResourceModel):
    node_id: str
    node_status: str
    cpu: CpuState
    accelerator: AcceleratorState = Field(default_factory=AcceleratorState)
    memory: MemoryState
    storage: StorageState = Field(default_factory=StorageState)
    network: NetworkState = Field(default_factory=NetworkState)
    queue_state: QueueState
    dynamic_state: DynamicState
    energy_state: EnergyState = Field(default_factory=EnergyState)
    reliability_state: ReliabilityState = Field(default_factory=ReliabilityState)


class ResourceStatePayload(FlexibleResourceModel):
    cluster_id: str
    snapshot_id: str
    snapshot_time: str
    profile_version: str
    nodes: List[ResourceStateNode]


class LinkCost(FlexibleResourceModel):
    latency_ms: float
    bandwidth_gbps: float
    interconnect_type: str
    cost_score: Optional[float] = None


class ResourceTopologyNode(FlexibleResourceModel):
    node_id: str
    rack_id: Optional[str] = None
    topology_neighbors: List[str] = Field(default_factory=list)
    link_cost_to_nodes: Dict[str, LinkCost] = Field(default_factory=dict)


class ResourceTopologyPayload(FlexibleResourceModel):
    cluster_id: str
    topology_id: str
    topology_version: str
    profile_version: str
    generated_time: Optional[str] = None
    nodes: List[ResourceTopologyNode]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
