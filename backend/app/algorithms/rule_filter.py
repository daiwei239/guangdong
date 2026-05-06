from typing import List, Sequence

from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


TASK_TYPE_PRIORITY = {
    "计算密集型": ["GPU", "FPGA", "CPU", "MEMORY"],
    "数据密集型": ["STORAGE", "MEMORY", "NIC", "CPU"],
    "通信密集型": ["NIC", "SWITCH", "GPU", "MEMORY"],
    "混合型": ["CPU", "GPU", "MEMORY", "STORAGE", "NIC", "SWITCH"],
}


class RuleFilter:
    """规则筛选器：负责资源粗筛与候选种子打分。"""

    def filter_resources(self, task: TaskProfileRead, resources: Sequence[ResourceNodeRead]) -> List[ResourceNodeRead]:
        preferred_types = TASK_TYPE_PRIORITY.get(task.task_type, [])
        eligible = []
        for resource in resources:
            if not resource.dynamic_state.get("available", False):
                continue
            if resource.type in preferred_types:
                eligible.append(resource)

        if len(eligible) < 10:
            eligible.extend([resource for resource in resources if resource.dynamic_state.get("available", False) and resource not in eligible])
        return eligible

    def score_seed_fit(self, task: TaskProfileRead, resource: ResourceNodeRead) -> float:
        score = 40.0
        if resource.type in TASK_TYPE_PRIORITY.get(task.task_type, []):
            score += 25.0
        utilization = float(resource.dynamic_state.get("utilization", 100))
        score += max(0.0, 20.0 - utilization * 0.2)
        if resource.type == "GPU":
            score += min(float(resource.static_attrs.get("memory_total", 0)), 80) * 0.15
        if resource.type == "NIC":
            score += float(resource.static_attrs.get("bandwidth_gbps", 0)) * 0.05
        if resource.type == "STORAGE":
            score += float(resource.static_attrs.get("throughput_gbps", 0)) * 0.12
        score += self._topology_bonus(task, resource)
        return score

    def _topology_bonus(self, task: TaskProfileRead, resource: ResourceNodeRead) -> float:
        """拓扑上下文加分：优先更低网络层级、更少跳数的资源。"""
        topo_context = resource.topo_context or {}
        network_tier = float(topo_context.get("network_tier", 3))
        hop_level = float(topo_context.get("hop_level", 4))

        score = max(0.0, 8.0 - max(network_tier - 1.0, 0.0) * 4.0)
        score += max(0.0, 6.0 - max(hop_level - 1.0, 0.0) * 1.5)

        if task.constraints.get("prefer_low_latency"):
            score += max(0.0, 8.0 - network_tier * 2.0 - hop_level * 0.8)
        if task.constraints.get("prefer_same_rack"):
            score += 2.0 if topo_context.get("rack_id") else 0.0
        return score
