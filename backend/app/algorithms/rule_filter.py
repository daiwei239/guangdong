from typing import Dict, List, Sequence

from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


TASK_TYPE_PRIORITY = {
    "计算密集型": ["GPU", "FPGA", "CPU", "MEMORY"],
    "数据密集型": ["STORAGE", "MEMORY", "NIC", "CPU"],
    "通信密集型": ["NIC", "SWITCH", "GPU", "MEMORY"],
    "混合型": ["CPU", "GPU", "MEMORY", "STORAGE", "NIC", "SWITCH"],
}


class RuleFilter:
    """根据任务约束和资源类型偏好做粗筛。"""

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
        return score
