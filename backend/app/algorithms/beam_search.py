from typing import List, Sequence, Set

import networkx as nx

from app.algorithms.rule_filter import RuleFilter
from app.schemas.task_schema import TaskProfileRead


class BeamSearchSubgraphFinder:
    """基于规则筛选与 Beam Search 的候选子网搜索器。

    搜索阶段会把任务查询转换成 Top-K 候选资源子图。它先从规则过滤后的
    种子资源开始，然后沿着物理连接或拓扑邻接关系扩展，最后保留连通且
    资源类型组合合理的子图，例如同时包含计算、内存、网络和存储资源。
    """

    def __init__(self, beam_width: int = 5, target_candidates: int = 3) -> None:
        self.beam_width = beam_width
        self.target_candidates = target_candidates
        self.rule_filter = RuleFilter()

    def search(
        self,
        task: TaskProfileRead,
        resources: Sequence,
        graph: nx.Graph,
    ) -> List[List[str]]:
        eligible = [resource for resource in self.rule_filter.filter_resources(task, resources) if graph.has_node(resource.id)]
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
                if nx.is_connected(graph.subgraph(enriched)) and self._is_valid_candidate_mix(task, graph, enriched):
                    candidates.append(enriched)
                if len(candidates) >= self.target_candidates:
                    return candidates

        return candidates[: self.target_candidates]

    def _expand_neighbors(self, graph: nx.Graph, node_ids: List[str]) -> List[str]:
        neighbors = set()
        for node_id in node_ids:
            if graph.has_node(node_id):
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
                edge_bonus += self._topology_affinity(graph, node_id, neighbor)
        edge_bonus += self._resource_type_bonus(graph, neighbor)
        return edge_bonus

    def _resource_type_bonus(self, graph: nx.Graph, node_id: str) -> float:
        resource_type = graph.nodes[node_id].get("type")
        if resource_type in {"CPU", "GPU", "FPGA", "MEMORY", "STORAGE", "NIC", "SWITCH"}:
            return 2.0
        return 0.0

    def _topology_affinity(self, graph: nx.Graph, source: str, target: str) -> float:
        """优先扩展与当前候选在拓扑上更接近的节点。"""
        source_topo = (graph.nodes[source] or {}).get("topo_context", {})
        target_topo = (graph.nodes[target] or {}).get("topo_context", {})
        if not source_topo or not target_topo:
            return 0.0

        score = 0.0
        if source_topo.get("server_id") == target_topo.get("server_id"):
            score += 8.0
        elif source_topo.get("rack_id") == target_topo.get("rack_id"):
            score += 5.0
        elif source_topo.get("cluster_id") == target_topo.get("cluster_id"):
            score += 2.5

        source_tier = float(source_topo.get("network_tier", 3))
        target_tier = float(target_topo.get("network_tier", 3))
        source_hop = float(source_topo.get("hop_level", 4))
        target_hop = float(target_topo.get("hop_level", 4))
        score += max(0.0, 3.0 - abs(source_tier - target_tier) * 1.5)
        score += max(0.0, 2.0 - abs(source_hop - target_hop) * 0.5)
        return score

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

    def _is_valid_candidate_mix(self, task: TaskProfileRead, graph: nx.Graph, node_ids: List[str]) -> bool:
        """检查候选子网不是只包含单一资源类型的碎片子图。"""
        resource_types = self._resource_types_in_nodes(graph, node_ids)
        has_compute = bool(resource_types & {"CPU", "GPU", "FPGA"})
        has_memory = "MEMORY" in resource_types
        has_network = bool(resource_types & {"NIC", "SWITCH"})
        has_storage = "STORAGE" in resource_types

        if task.task_type == "计算密集型":
            return has_compute and has_memory and has_network
        if task.task_type == "数据密集型":
            return has_storage and has_memory and has_network
        if task.task_type == "通信密集型":
            return has_network and (has_compute or has_memory)
        return has_compute and has_memory and (has_network or has_storage)

    def _resource_types_in_nodes(self, graph: nx.Graph, node_ids: List[str]) -> Set[str]:
        return {str(graph.nodes[node_id].get("type")) for node_id in node_ids if graph.has_node(node_id)}
