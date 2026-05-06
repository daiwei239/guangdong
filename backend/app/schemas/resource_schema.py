from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


class ResourceNodeBase(BaseModel):
    id: str
    name: str
    type: str
    cluster_id: str
    host_id: str
    topo_context: Dict
    static_attrs: Dict
    dynamic_state: Dict
    semantic_tags: List[str]
    created_at: datetime
    updated_at: datetime


class ResourceNodeRead(ResourceNodeBase):
    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True


class ResourceEdgeRead(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str
    bandwidth_gbps: float
    latency_ms: float
    weight: float

    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True


class FrontendResourceNode(BaseModel):
    id: str
    label: str
    type: str
    cluster_id: str
    x: float
    y: float
    status: str
    utilization: float
    available: bool
    is_candidate: bool = False
    is_top1: bool = False


class FrontendResourceEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str
    bandwidth_gbps: float
    latency_ms: float
    is_candidate_edge: bool = False
    is_top1_edge: bool = False


class ResourceSnapshot(BaseModel):
    total_nodes: int
    total_edges: int
    by_type: Dict[str, int]
    resources: List[ResourceNodeRead]
