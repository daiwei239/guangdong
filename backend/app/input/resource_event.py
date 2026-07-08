from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.resource_schema import (
    RawTopologyEdge,
    validate_cluster_type_attributes,
    validate_accelerator_attributes,
    validate_maintenance_state_metrics,
    validate_node_role_attributes,
    validate_node_status_metrics,
)


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


class SourceNodePatch(BaseModel):
    node_id: str
    resource_id: Optional[str] = None
    resource_type: str = "resource"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    topology: Dict[str, Any] = Field(default_factory=dict)

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


class ResourceSourceBatch(BaseModel):
    source_name: str = "unknown"
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None
    nodes: List[SourceNodePatch] = Field(default_factory=list)
    edges: List[RawTopologyEdge] = Field(default_factory=list)
