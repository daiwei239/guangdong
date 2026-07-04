from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.resource_schema import RawTopologyEdge


SOURCE_TYPES = {
    "management_config",
    "agent_collect",
    "realtime_monitor",
    "device_plugin",
    "topology_probe",
    "scheduler_queue",
    "asset_ops",
    "analytics_history",
}


class ResourceEvent(BaseModel):
    source_type: str
    source_name: str = "unknown"
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None
    node_id: str
    resource_id: Optional[str] = None
    resource_type: str = "resource"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    topology: Dict[str, Any] = Field(default_factory=dict)
    edges: List[RawTopologyEdge] = Field(default_factory=list)


class SourceNodePatch(BaseModel):
    node_id: str
    resource_id: Optional[str] = None
    resource_type: str = "resource"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    topology: Dict[str, Any] = Field(default_factory=dict)


class ResourceSourceBatch(BaseModel):
    source_name: str = "unknown"
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None
    nodes: List[SourceNodePatch] = Field(default_factory=list)
    edges: List[RawTopologyEdge] = Field(default_factory=list)
