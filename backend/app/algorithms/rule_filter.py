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
    """规则筛选器：负责资源粗筛与候选种子打分。

    这是 GNN 评分之前的第一层规则过滤。它会先移除明显不可用或不满足
    基础约束的资源，并根据任务主导模式优先选择相关资源类型。后续的
    BeamSearch 模块会从这些种子节点继续扩展，生成候选资源子图。
    """

    def filter_resources(self, task: TaskProfileRead, resources: Sequence[ResourceNodeRead]) -> List[ResourceNodeRead]:
        preferred_types = TASK_TYPE_PRIORITY.get(task.task_type, [])
        eligible = []
        for resource in resources:
            if not resource.dynamic_state.get("available", False):
                continue
            if not self._passes_basic_constraints(task, resource):
                continue
            if resource.type in preferred_types:
                eligible.append(resource)

        if len(eligible) < 10:
            fallback = [
                resource
                for resource in resources
                if resource.dynamic_state.get("available", False)
                and self._passes_basic_constraints(task, resource)
                and resource not in eligible
            ]
            eligible.extend(fallback)
        return eligible

    def score_seed_fit(self, task: TaskProfileRead, resource: ResourceNodeRead) -> float:
        score = 40.0
        if resource.type in TASK_TYPE_PRIORITY.get(task.task_type, []):
            score += 25.0
        utilization = float(resource.dynamic_state.get("utilization", 100))
        score += max(0.0, 20.0 - utilization * 0.2)

        if resource.type == "CPU":
            score += min(float(resource.static_attrs.get("cores", 0)), 128.0) * 0.08
        if resource.type == "GPU":
            score += min(float(resource.static_attrs.get("memory_total", 0)), 80.0) * 0.15
            score += min(float(resource.static_attrs.get("fp16_tflops", 0)), 400.0) * 0.03
        if resource.type == "MEMORY":
            score += min(float(resource.static_attrs.get("capacity_gb", 0)), 2048.0) * 0.01
        if resource.type == "NIC":
            score += float(resource.static_attrs.get("bandwidth_gbps", 0)) * 0.05
        if resource.type == "STORAGE":
            score += float(resource.static_attrs.get("throughput_gbps", 0)) * 0.12
        score += self._topology_bonus(task, resource)
        return score

    def _passes_basic_constraints(self, task: TaskProfileRead, resource: ResourceNodeRead) -> bool:
        """在图搜索和子图搜索之前执行低成本的本地硬约束过滤。"""

        max_utilization = float(task.constraints.get("max_resource_utilization", 95.0))
        utilization = float(resource.dynamic_state.get("utilization", 0.0))
        if utilization > max_utilization:
            return False

        if resource.type == "GPU":
            min_gpu_memory = float(task.constraints.get("min_gpu_memory_gb", 0.0))
            if min_gpu_memory > 0 and float(resource.static_attrs.get("memory_total", 0.0)) < min_gpu_memory:
                return False

        if resource.type == "MEMORY":
            min_memory = float(task.memory_req.get("capacity_gb", 0.0))
            if min_memory > 0 and float(resource.static_attrs.get("capacity_gb", 0.0)) < min_memory:
                return False

        if resource.type == "STORAGE":
            min_storage_throughput = float(task.constraints.get("min_storage_throughput_gbps", 0.0))
            if min_storage_throughput > 0 and float(resource.static_attrs.get("throughput_gbps", 0.0)) < min_storage_throughput:
                return False

        if resource.type == "NIC":
            min_bandwidth = float(task.network_req.get("bandwidth_gbps", 0.0))
            if min_bandwidth > 0 and float(resource.static_attrs.get("bandwidth_gbps", 0.0)) < min_bandwidth:
                return False

        return True

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
