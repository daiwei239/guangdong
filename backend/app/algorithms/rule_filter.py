from typing import Any, Dict, List, Sequence, Tuple

import networkx as nx

from app.schemas.resource_schema import ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


TASK_TYPE_PRIORITY = {
    "计算密集型": ["GPU", "FPGA", "CPU", "MEMORY"],
    "数据密集型": ["STORAGE", "MEMORY", "NIC", "CPU"],
    "通信密集型": ["NIC", "SWITCH", "GPU", "MEMORY"],
    "混合型": ["CPU", "GPU", "MEMORY", "STORAGE", "NIC", "SWITCH"],
}


class RuleFilter:
    """规则筛选器：负责资源粗筛、候选种子打分、候选子图硬规则验证。

    这里分成两层规则：
    1. filter_resources：在 Beam Search 之前做低成本资源粗筛；
    2. select_with_rule_fallback：在候选子图已经生成和打分之后，
       从高分到低分逐个做硬规则验证，不通过就回退尝试下一个候选。
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

    def validate_candidate_subgraph(
        self,
        task: TaskProfileRead,
        resources: Sequence[ResourceNodeRead],
        graph: nx.Graph,
    ) -> Tuple[bool, List[str]]:
        """对一个候选子图做硬规则验证。

        返回：
        - True, []：候选子图满足规则，可以作为最终 Top1；
        - False, reasons：候选子图不满足规则，reasons 用于记录失败原因。
        """
        reasons: List[str] = []

        if not resources:
            return False, ["候选子图为空"]

        resource_types = {resource.type for resource in resources}

        # 规则 1：候选子图中的所有资源都必须处于 available 状态。
        unavailable = [
            resource.id
            for resource in resources
            if not resource.dynamic_state.get("available", False)
        ]
        if unavailable:
            reasons.append(f"候选子图包含不可用资源: {unavailable}")

        # 规则 2：候选资源利用率不能超过任务允许的最大利用率。
        max_utilization = float(task.constraints.get("max_resource_utilization", 95.0))
        overloaded = [
            resource.id
            for resource in resources
            if float(resource.dynamic_state.get("utilization", 0.0)) > max_utilization
        ]
        if overloaded:
            reasons.append(f"资源利用率超过限制: {overloaded}")

        # 规则 3：根据任务类型检查必须出现的资源类型组合。
        has_compute = bool(resource_types & {"CPU", "GPU", "FPGA"})
        has_memory = "MEMORY" in resource_types
        has_storage = "STORAGE" in resource_types
        has_network = bool(resource_types & {"NIC", "SWITCH"})

        if task.task_type == "计算密集型":
            if not has_compute:
                reasons.append("计算密集型任务缺少 CPU/GPU/FPGA")
            if not has_memory:
                reasons.append("计算密集型任务缺少 MEMORY")
            if not has_network:
                reasons.append("计算密集型任务缺少 NIC/SWITCH")

        elif task.task_type == "数据密集型":
            if not has_storage:
                reasons.append("数据密集型任务缺少 STORAGE")
            if not has_memory:
                reasons.append("数据密集型任务缺少 MEMORY")
            if not has_network:
                reasons.append("数据密集型任务缺少 NIC/SWITCH")

        elif task.task_type == "通信密集型":
            if not has_network:
                reasons.append("通信密集型任务缺少 NIC/SWITCH")
            if not (has_compute or has_memory):
                reasons.append("通信密集型任务缺少计算或内存资源")

        else:
            if not has_compute:
                reasons.append("混合型任务缺少 CPU/GPU/FPGA")
            if not has_memory:
                reasons.append("混合型任务缺少 MEMORY")
            if not (has_network or has_storage):
                reasons.append("混合型任务缺少网络或存储资源")

        # 规则 4：检查候选子图聚合后的资源容量是否满足任务需求。
        total_cpu_cores = sum(
            float(resource.static_attrs.get("cores", 0.0))
            for resource in resources
            if resource.type == "CPU"
        )
        total_gpu_memory = sum(
            float(resource.static_attrs.get("memory_total", 0.0))
            for resource in resources
            if resource.type == "GPU"
        )
        total_memory = sum(
            float(resource.static_attrs.get("capacity_gb", 0.0))
            for resource in resources
            if resource.type == "MEMORY"
        )
        total_storage_throughput = sum(
            float(resource.static_attrs.get("throughput_gbps", 0.0))
            for resource in resources
            if resource.type == "STORAGE"
        )
        total_network_bandwidth = sum(
            float(resource.static_attrs.get("bandwidth_gbps", 0.0))
            for resource in resources
            if resource.type in {"NIC", "SWITCH"}
        )

        required_cpu_cores = float(task.compute_req.get("cpu_cores", 0.0))
        required_gpu_memory = float(task.constraints.get("min_gpu_memory_gb", 0.0))
        required_memory = float(task.memory_req.get("capacity_gb", 0.0))
        required_storage_throughput = float(task.constraints.get("min_storage_throughput_gbps", 0.0))
        required_network_bandwidth = float(task.network_req.get("bandwidth_gbps", 0.0))

        if total_cpu_cores < required_cpu_cores:
            reasons.append(f"CPU cores 不满足任务需求: {total_cpu_cores} < {required_cpu_cores}")

        if total_gpu_memory < required_gpu_memory:
            reasons.append(f"GPU memory 不满足任务需求: {total_gpu_memory} < {required_gpu_memory}")

        if total_memory < required_memory:
            reasons.append(f"Memory capacity 不满足任务需求: {total_memory} < {required_memory}")

        if total_storage_throughput < required_storage_throughput:
            reasons.append(
                f"Storage throughput 不满足任务需求: "
                f"{total_storage_throughput} < {required_storage_throughput}"
            )

        if total_network_bandwidth < required_network_bandwidth:
            reasons.append(
                f"Network bandwidth 不满足任务需求: "
                f"{total_network_bandwidth} < {required_network_bandwidth}"
            )

        # 规则 5：候选节点必须在拓扑图中连通，否则不能组成可执行资源子图。
        node_ids = [resource.id for resource in resources]
        missing_nodes = [node_id for node_id in node_ids if not graph.has_node(node_id)]
        if missing_nodes:
            reasons.append(f"候选子图包含图中不存在的节点: {missing_nodes}")
        else:
            subgraph = graph.subgraph(node_ids)
            if len(node_ids) > 1 and not nx.is_connected(subgraph):
                reasons.append("候选子图不连通")

            # 规则 6：如果任务给了最大网络延迟限制，则检查候选子图平均边延迟。
            max_latency = float(task.constraints.get("max_network_latency_ms", float("inf")))
            if subgraph.number_of_edges() > 0 and max_latency < float("inf"):
                avg_latency = sum(
                    float(data.get("latency_ms", 0.0))
                    for _, _, data in subgraph.edges(data=True)
                ) / subgraph.number_of_edges()

                if avg_latency > max_latency:
                    reasons.append(f"平均网络延迟超过任务限制: {avg_latency} > {max_latency}")

        return len(reasons) == 0, reasons

    def select_with_rule_fallback(
        self,
        task: TaskProfileRead,
        candidates: Sequence[Any],
        resources_by_id: Dict[str, ResourceNodeRead],
        graph: nx.Graph,
    ) -> Tuple[Any, List[Dict[str, Any]]]:
        """按候选排序结果执行“规则验证 + 回退重试”。

        输入的 candidates 应该已经按照 final_score 从高到低排好序。
        逻辑是：
        1. 先验证最高分候选；
        2. 如果失败，记录失败原因，然后尝试下一个候选；
        3. 返回第一个通过规则验证的候选；
        4. 如果全部失败，返回 None，并保留完整失败日志。
        """
        fallback_logs: List[Dict[str, Any]] = []

        for index, candidate in enumerate(candidates, start=1):
            selected_resources = [
                resources_by_id[node_id]
                for node_id in candidate.nodes
                if node_id in resources_by_id
            ]

            is_valid, reasons = self.validate_candidate_subgraph(
                task=task,
                resources=selected_resources,
                graph=graph,
            )

            fallback_logs.append(
                {
                    "try_index": index,
                    "subgraph_id": candidate.subgraph_id,
                    "score": candidate.final_score,
                    "is_valid": is_valid,
                    "reasons": reasons,
                }
            )

            if is_valid:
                return candidate, fallback_logs

        return None, fallback_logs

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
