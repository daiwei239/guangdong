from typing import Dict, List, Sequence, Set, Tuple

import networkx as nx

from app.algorithms.rule_filter import RuleFilter
from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


class BeamSearchSubgraphFinder:
    """使用简化 Beam Search 搜索候选资源子网。"""

    def __init__(self, beam_width: int = 5, target_candidates: int = 3) -> None:
        self.beam_width = beam_width
        self.target_candidates = target_candidates
        self.rule_filter = RuleFilter()

    def search(
        self,
        task: TaskProfileRead,
        resources: Sequence[ResourceNodeRead],
        graph: nx.Graph,
    ) -> List[List[str]]:
        eligible = self.rule_filter.filter_resources(task, resources)
        scored_seeds = sorted(
            eligible,
            key=lambda resource: self.rule_filter.score_seed_fit(task, resource),
            reverse=True,
        )
        seeds = scored_seeds[: max(self.beam_width, self.target_candidates)]
        candidates = []
        visited_signatures = set()

        for seed in seeds:
            beam = [(self.rule_filter.score_seed_fit(task, seed), [seed.id])]
            rounds = 0
            while beam and rounds < 4:
                next_beam = []
                for score, node_ids in beam:
                    neighborhood = self._expand_neighbors(graph, node_ids)
                    for neighbor in neighborhood:
                        if neighbor in node_ids:
                            continue
                        new_node_ids = node_ids + [neighbor]
                        new_score = score + self._node_expansion_score(graph, neighbor, new_node_ids)
                        next_beam.append((new_score, new_node_ids))
                next_beam.sort(key=lambda item: item[0], reverse=True)
                beam = next_beam[: self.beam_width]
                rounds += 1

            final_sets = beam or [(self.rule_filter.score_seed_fit(task, seed), [seed.id])]
            for _, node_ids in final_sets:
                enriched = self._ensure_min_size(graph, node_ids, minimum_size=6, maximum_size=10)
                signature = tuple(sorted(enriched))
                if signature in visited_signatures:
                    continue
                visited_signatures.add(signature)
                if nx.is_connected(graph.subgraph(enriched)):
                    candidates.append(enriched)
                if len(candidates) >= self.target_candidates:
                    return candidates

        return candidates[: self.target_candidates]

    def _expand_neighbors(self, graph: nx.Graph, node_ids: List[str]) -> List[str]:
        neighbors = set()
        for node_id in node_ids:
            neighbors.update(graph.neighbors(node_id))
        return list(neighbors)

    def _node_expansion_score(self, graph: nx.Graph, neighbor: str, node_ids: List[str]) -> float:
        edge_bonus = 0.0
        for node_id in node_ids:
            if graph.has_edge(node_id, neighbor):
                attrs = graph.edges[node_id, neighbor]
                edge_bonus += float(attrs.get("weight", 1.0)) * 8.0
                edge_bonus += float(attrs.get("bandwidth_gbps", 0.0)) * 0.03
                edge_bonus -= float(attrs.get("latency_ms", 0.0)) * 0.4
        return edge_bonus

    def _ensure_min_size(self, graph: nx.Graph, node_ids: List[str], minimum_size: int, maximum_size: int) -> List[str]:
        selected = list(node_ids)
        frontier = self._expand_neighbors(graph, selected)
        while len(selected) < minimum_size and frontier:
            frontier = [node_id for node_id in frontier if node_id not in selected]
            if not frontier:
                break
            frontier.sort(key=lambda node_id: graph.degree(node_id), reverse=True)
            selected.append(frontier[0])
            frontier = self._expand_neighbors(graph, selected)
        return selected[:maximum_size]
