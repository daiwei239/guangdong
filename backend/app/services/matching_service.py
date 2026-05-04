import time
from typing import Dict, List, Optional, Sequence, Set

import networkx as nx

from app.algorithms.beam_search import BeamSearchSubgraphFinder
from app.schemas.match_schema import MatchResponseSchema
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.services.scoring_service import scoring_service


class MatchingService:
    def __init__(self) -> None:
        self.finder = BeamSearchSubgraphFinder()
        self._results = {}

    def match_task(
        self,
        task: TaskProfileRead,
        resources: Sequence[ResourceNodeRead],
        edges: Sequence[ResourceEdgeRead],
        graph: nx.Graph,
        pipeline_steps: Optional[List[str]] = None,
    ) -> MatchResponseSchema:
        pipeline_steps = list(pipeline_steps or [])
        resource_lookup = {resource.id: resource for resource in resources}
        candidate_node_sets = self.finder.search(task, resources, graph)

        if not candidate_node_sets:
            available_ids = [resource.id for resource in resources[:6]]
            candidate_node_sets = [available_ids] * 3

        candidates = []
        for index, node_ids in enumerate(candidate_node_sets[:3], start=1):
            candidates.append(scoring_service.score_candidate(task, resource_lookup, graph, node_ids, index))

        candidates.sort(key=lambda candidate: candidate.final_score, reverse=True)
        for index, candidate in enumerate(candidates, start=1):
            candidate.rank = index
            candidate.is_top1 = index == 1

        while len(candidates) < 3:
            clone = candidates[-1].copy(deep=True)
            clone.subgraph_id = "{0}-alt{1}".format(clone.subgraph_id, len(candidates) + 1)
            clone.rank = len(candidates) + 1
            clone.is_top1 = False
            clone.final_score = max(0.0, round(clone.final_score - 1.5 * len(candidates), 2))
            clone.score = clone.final_score
            candidates.append(clone)

        top1 = candidates[0]
        verification = scoring_service.validate_top1(task, top1)
        result = MatchResponseSchema(
            task_id=task.task_id,
            candidates=candidates,
            top1=top1,
            verification=verification,
            pipeline_steps=pipeline_steps,
        )
        self._results[task.task_id] = result
        return result

    def get_result(self, task_id: str) -> Optional[MatchResponseSchema]:
        return self._results.get(task_id)


matching_service = MatchingService()
