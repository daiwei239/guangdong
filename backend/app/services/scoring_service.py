from typing import Dict, Sequence

import networkx as nx

from app.algorithms.score import ScoreCalculator
from app.schemas.match_schema import CandidateSubgraphSchema, VerificationResultSchema
from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


class ScoringService:
    def __init__(self) -> None:
        self.calculator = ScoreCalculator()

    def score_candidate(
        self,
        task: TaskProfileRead,
        resources_by_id: Dict[str, ResourceNodeRead],
        graph: nx.Graph,
        node_ids: Sequence[str],
        rank: int,
    ) -> CandidateSubgraphSchema:
        return self.calculator.score_candidate(task, resources_by_id, graph, node_ids, rank)

    def validate_top1(self, task: TaskProfileRead, candidate: CandidateSubgraphSchema) -> VerificationResultSchema:
        return self.calculator.validate_top1(task, candidate)


scoring_service = ScoringService()
