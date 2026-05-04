from typing import Dict, List, Sequence, Tuple

import networkx as nx

from app.schemas.match_schema import CandidateSubgraphSchema, VerificationResultSchema
from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.utils.id_generator import generate_id
from app.utils.normalizer import clamp


class ScoreCalculator:
    """规则评分器，将多种指标映射到 0-100 并计算最终分。"""

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

        total_gpu_memory = sum(float(node.static_attrs.get("memory_total", 0)) for node in resource_nodes if node.type == "GPU")
        total_cpu_cores = sum(float(node.static_attrs.get("cores", 0)) for node in resource_nodes if node.type == "CPU")
        total_memory = sum(float(node.static_attrs.get("capacity_gb", 0)) for node in resource_nodes if node.type == "MEMORY")
        storage_throughput = sum(float(node.static_attrs.get("throughput_gbps", 0)) for node in resource_nodes if node.type == "STORAGE")
        nic_bandwidth = sum(float(node.static_attrs.get("bandwidth_gbps", 0)) for node in resource_nodes if node.type == "NIC")

        capacity_score = clamp(
            (
                min(total_gpu_memory / max(task.constraints.get("min_gpu_memory_gb", 1), 1), 2.0) * 25
                + min(total_cpu_cores / max(task.compute_req.get("cpu_cores", 1), 1), 2.0) * 25
                + min(total_memory / max(task.memory_req.get("capacity_gb", 1), 1), 2.0) * 25
                + min(storage_throughput / max(task.constraints.get("min_storage_throughput_gbps", 1), 1), 2.0) * 25
            )
        )

        performance_score = clamp(
            (
                sum(float(node.static_attrs.get("fp16_tflops", 0)) for node in resource_nodes if node.type == "GPU") / max(task.compute_req.get("fp16_tflops", 1), 1) * 40
                + nic_bandwidth / max(task.network_req.get("bandwidth_gbps", 1), 1) * 30
                + sum(float(node.static_attrs.get("bandwidth_gbps", 0)) for node in resource_nodes if node.type == "MEMORY") / 400.0 * 30
            )
        )

        if subgraph.number_of_edges() > 0:
            avg_latency = sum(float(data.get("latency_ms", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
            avg_bandwidth = sum(float(data.get("bandwidth_gbps", 0)) for _, _, data in subgraph.edges(data=True)) / subgraph.number_of_edges()
        else:
            avg_latency = 10.0
            avg_bandwidth = 0.0

        topology_score = clamp(
            (100.0 if nx.is_connected(subgraph) else 40.0)
            + min(avg_bandwidth / 4.0, 25.0)
            - min(avg_latency * 4.0, 25.0)
        )

        qos_score = clamp(
            100.0
            - min(avg_latency / max(task.constraints.get("max_network_latency_ms", 1), 1) * 35.0, 35.0)
            - min(sum(float(node.dynamic_state.get("queue_length", 0)) for node in resource_nodes) * 1.2, 35.0)
            + min(task.priority * 4.0, 20.0)
        )

        communication_cost = clamp(max(0.0, avg_latency * 10.0 - avg_bandwidth * 0.04))
        energy_cost = clamp(sum(float(node.dynamic_state.get("power_watt", 0)) for node in resource_nodes) / max(task.energy_limit, 1) * 100.0)
        load_cost = clamp(sum(float(node.dynamic_state.get("utilization", 0)) for node in resource_nodes) / max(len(resource_nodes), 1))

        final_score = clamp(
            0.25 * capacity_score
            + 0.25 * performance_score
            + 0.20 * topology_score
            + 0.20 * qos_score
            - 0.04 * communication_cost
            - 0.03 * energy_cost
            - 0.03 * load_cost
        )

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
            recommendation = "当前最优资源子网存在部分约束风险，建议调整任务需求或重新生成资源快照后再提交。"

        return VerificationResultSchema(
            capacity_ok=capacity_ok,
            performance_ok=performance_ok,
            topology_ok=topology_ok,
            qos_ok=qos_ok,
            recommendation=recommendation,
        )
