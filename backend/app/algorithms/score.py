from collections import Counter
from typing import Dict, Sequence

import networkx as nx

from app.schemas.match_schema import CandidateSubgraphSchema, VerificationResultSchema
from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.utils.id_generator import generate_id
from app.utils.normalizer import clamp


class ScoreCalculator:
    """规则评分器：计算容量、性能、拓扑、QoS 与综合成本。"""

    def __init__(
        self,
        alpha: float = 0.35,
        beta: float = 0.35,
        gamma: float = 0.20,
        lambda_: float = 0.10,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.lambda_ = lambda_

    def score_candidate(
        self,
        task: TaskProfileRead,
        resources_by_id: Dict[str, ResourceNodeRead],
        graph: nx.Graph,
        node_ids: Sequence[str],
        rank: int,
    ) -> CandidateSubgraphSchema:
        resource_nodes = [resources_by_id[node_id] for node_id in node_ids]
        subgraph = graph.subgraph(node_ids)

        capacity_score = self.compute_capacity_score(task, resource_nodes)
        performance_score = self.compute_performance_score(task, resource_nodes)
        topology_score = self.compute_topology_score(task, subgraph)
        qos_score = self.compute_qos_score(task, resource_nodes, subgraph)
        communication_cost, energy_cost, load_cost, cost = self.compute_cost(task, resource_nodes, subgraph)
        final_score = self.compute_final_score(capacity_score, performance_score, topology_score, cost)

        edge_ids = []
        for source, target in subgraph.edges():
            edge_ids.append(graph.edges[source, target]["id"])

        return CandidateSubgraphSchema(
            subgraph_id=generate_id("subgraph"),
            rank=rank,
            nodes=list(node_ids),
            edges=edge_ids,
            score=round(final_score, 2),
            capacity_score=round(capacity_score, 2),
            performance_score=round(performance_score, 2),
            topology_score=round(topology_score, 2),
            qos_score=round(qos_score, 2),
            communication_cost=round(communication_cost, 2),
            energy_cost=round(energy_cost, 2),
            load_cost=round(load_cost, 2),
            final_score=round(final_score, 2),
            is_top1=False,
        )

    def compute_capacity_score(self, task: TaskProfileRead, resource_nodes: Sequence[ResourceNodeRead]) -> float:
        total_gpu_memory = sum(float(node.static_attrs.get("memory_total", 0)) for node in resource_nodes if node.type == "GPU")
        total_cpu_cores = sum(float(node.static_attrs.get("cores", 0)) for node in resource_nodes if node.type == "CPU")
        total_memory = sum(float(node.static_attrs.get("capacity_gb", 0)) for node in resource_nodes if node.type == "MEMORY")
        storage_throughput = sum(float(node.static_attrs.get("throughput_gbps", 0)) for node in resource_nodes if node.type == "STORAGE")
        return clamp(
            (
                min(total_gpu_memory / max(task.constraints.get("min_gpu_memory_gb", 1), 1), 2.0) * 25
                + min(total_cpu_cores / max(task.compute_req.get("cpu_cores", 1), 1), 2.0) * 25
                + min(total_memory / max(task.memory_req.get("capacity_gb", 1), 1), 2.0) * 25
                + min(storage_throughput / max(task.constraints.get("min_storage_throughput_gbps", 1), 1), 2.0) * 25
            )
        )

    def compute_performance_score(self, task: TaskProfileRead, resource_nodes: Sequence[ResourceNodeRead]) -> float:
        gpu_fp16 = sum(float(node.static_attrs.get("fp16_tflops", 0)) for node in resource_nodes if node.type == "GPU")
        nic_bandwidth = sum(float(node.static_attrs.get("bandwidth_gbps", 0)) for node in resource_nodes if node.type == "NIC")
        memory_bandwidth = sum(float(node.static_attrs.get("bandwidth_gbps", 0)) for node in resource_nodes if node.type == "MEMORY")
        return clamp(
            (
                gpu_fp16 / max(task.compute_req.get("fp16_tflops", 1), 1) * 40
                + nic_bandwidth / max(task.network_req.get("bandwidth_gbps", 1), 1) * 30
                + memory_bandwidth / 400.0 * 30
            )
        )

    def compute_topology_score(self, task: TaskProfileRead, subgraph: nx.Graph) -> float:
        if subgraph.number_of_edges() > 0:
            avg_latency = sum(float(data.get("latency_ms", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
            avg_bandwidth = sum(float(data.get("bandwidth_gbps", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
        else:
            avg_latency = 10.0
            avg_bandwidth = 0.0
        topo_context_bonus = self._compute_topology_context_bonus(subgraph)
        return clamp(
            (65.0 if nx.is_connected(subgraph) else 30.0)
            + min(avg_bandwidth / 4.0, 25.0)
            - min(avg_latency * 4.0, 25.0)
            + topo_context_bonus
        )

    def compute_qos_score(
        self,
        task: TaskProfileRead,
        resource_nodes: Sequence[ResourceNodeRead],
        subgraph: nx.Graph,
    ) -> float:
        if subgraph.number_of_edges() > 0:
            avg_latency = sum(float(data.get("latency_ms", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
        else:
            avg_latency = 10.0
        total_queue = sum(float(node.dynamic_state.get("queue_length", 0)) for node in resource_nodes)
        same_rack_bonus = self._same_rack_ratio(subgraph) * 12.0 if task.constraints.get("prefer_same_rack") else 0.0
        return clamp(
            100.0
            - min(avg_latency / max(task.constraints.get("max_network_latency_ms", 1), 1) * 35.0, 35.0)
            - min(total_queue * 1.2, 35.0)
            + min(task.priority * 4.0, 20.0)
            + same_rack_bonus
        )

    def compute_cost(
        self,
        task: TaskProfileRead,
        resource_nodes: Sequence[ResourceNodeRead],
        subgraph: nx.Graph,
    ) -> tuple[float, float, float, float]:
        if subgraph.number_of_edges() > 0:
            avg_latency = sum(float(data.get("latency_ms", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
            avg_bandwidth = sum(float(data.get("bandwidth_gbps", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
        else:
            avg_latency = 10.0
            avg_bandwidth = 0.0
        topo_penalty = self._compute_topology_penalty(subgraph)
        communication_cost = clamp(max(0.0, avg_latency * 10.0 - avg_bandwidth * 0.04) + topo_penalty)
        energy_cost = clamp(sum(float(node.dynamic_state.get("power_watt", 0)) for node in resource_nodes) / max(task.energy_limit, 1) * 100.0)
        load_cost = clamp(sum(float(node.dynamic_state.get("utilization", 0)) for node in resource_nodes) / max(len(resource_nodes), 1))
        cost = clamp(0.4 * communication_cost + 0.3 * energy_cost + 0.3 * load_cost)
        return communication_cost, energy_cost, load_cost, cost

    def compute_final_score(
        self,
        capacity_score: float,
        performance_score: float,
        topology_score: float,
        cost: float,
    ) -> float:
        return clamp(
            self.alpha * capacity_score
            + self.beta * performance_score
            + self.gamma * topology_score
            - self.lambda_ * cost
        )

    def validate_top1(
        self,
        task: TaskProfileRead,
        candidate: CandidateSubgraphSchema,
    ) -> VerificationResultSchema:
        capacity_ok = candidate.capacity_score >= 60
        performance_ok = candidate.performance_score >= 55
        topology_ok = candidate.topology_score >= 60
        qos_ok = candidate.qos_score >= 55

        recommendation = "当前最优资源子网满足任务容量、性能、拓扑与 QoS 约束，建议提交调度器进行任务部署。"
        if not all([capacity_ok, performance_ok, topology_ok, qos_ok]):
            recommendation = "当前候选资源子网仍存在容量、性能、拓扑或 QoS 短板，建议继续搜索或调整任务约束后再提交调度。"

        return VerificationResultSchema(
            capacity_ok=capacity_ok,
            performance_ok=performance_ok,
            topology_ok=topology_ok,
            qos_ok=qos_ok,
            recommendation=recommendation,
        )

    def _compute_topology_context_bonus(self, subgraph: nx.Graph) -> float:
        if subgraph.number_of_nodes() == 0:
            return 0.0
        same_server_ratio = self._shared_context_ratio(subgraph, "server_id")
        same_rack_ratio = self._shared_context_ratio(subgraph, "rack_id")
        same_cluster_ratio = self._shared_context_ratio(subgraph, "cluster_id")
        avg_network_tier = self._average_topology_metric(subgraph, "network_tier", default=3.0)
        avg_hop_level = self._average_topology_metric(subgraph, "hop_level", default=4.0)

        bonus = same_server_ratio * 12.0 + same_rack_ratio * 10.0 + same_cluster_ratio * 6.0
        bonus += max(0.0, 8.0 - avg_network_tier * 3.0)
        bonus += max(0.0, 8.0 - avg_hop_level * 1.8)
        return bonus

    def _compute_topology_penalty(self, subgraph: nx.Graph) -> float:
        avg_network_tier = self._average_topology_metric(subgraph, "network_tier", default=3.0)
        avg_hop_level = self._average_topology_metric(subgraph, "hop_level", default=4.0)
        same_rack_ratio = self._same_rack_ratio(subgraph)
        return max(0.0, avg_network_tier * 6.0 + avg_hop_level * 4.0 - same_rack_ratio * 8.0)

    def _same_rack_ratio(self, subgraph: nx.Graph) -> float:
        return self._shared_context_ratio(subgraph, "rack_id")

    def _shared_context_ratio(self, subgraph: nx.Graph, key: str) -> float:
        values = []
        for _, data in subgraph.nodes(data=True):
            topo_context = data.get("topo_context", {}) or {}
            value = topo_context.get(key)
            if value:
                values.append(value)
        if not values:
            return 0.0
        counts = Counter(values)
        return counts.most_common(1)[0][1] / max(subgraph.number_of_nodes(), 1)

    def _average_topology_metric(self, subgraph: nx.Graph, key: str, default: float) -> float:
        values = []
        for _, data in subgraph.nodes(data=True):
            topo_context = data.get("topo_context", {}) or {}
            values.append(float(topo_context.get(key, default)))
        if not values:
            return default
        return sum(values) / len(values)
