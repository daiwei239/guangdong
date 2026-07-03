from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_SCHEMA_VERSION = "1.0"
RESOURCE_DESCRIPTION_MODULE = "Module-2.1-ResourceDescription"


class RawResourceRecord(BaseModel):
    id: str
    type: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    attributes: Dict[str, Any] = Field(default_factory=dict)


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
