from typing import Dict, List

from pydantic import BaseModel


class CandidateSubgraphSchema(BaseModel):
    subgraph_id: str
    rank: int
    nodes: List[str]
    edges: List[str]
    score: float
    capacity_score: float
    performance_score: float
    topology_score: float
    qos_score: float
    communication_cost: float
    energy_cost: float
    load_cost: float
    final_score: float
    is_top1: bool = False


class VerificationResultSchema(BaseModel):
    capacity_ok: bool
    performance_ok: bool
    topology_ok: bool
    qos_ok: bool
    recommendation: str


class MatchResponseSchema(BaseModel):
    task_id: str
    candidates: List[CandidateSubgraphSchema]
    top1: CandidateSubgraphSchema
    verification: VerificationResultSchema
    pipeline_steps: List[str]


class SimulationResponseSchema(BaseModel):
    resource_snapshot: Dict
    task_profile: Dict
    resource_graph: Dict
    candidates: List[Dict]
    top1: Dict
    verification: Dict
    pipeline_steps: List[str]
