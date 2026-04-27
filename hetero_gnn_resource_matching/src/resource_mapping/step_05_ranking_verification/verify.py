"""Rule-based candidate verification after GNN scoring."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class ResourceVerifier:
    """Validate hard constraints for a task-candidate pair."""

    def __init__(self, resources: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        self.resources = {r["id"]: r for r in resources}
        self.edges = edges
        self.adj: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            self.adj[edge["source"]].add(edge["target"])
            self.adj[edge["target"]].add(edge["source"])

    def verify(self, task: dict[str, Any], candidate_subnet: dict[str, Any]) -> dict[str, Any]:
        """Verify capacity, performance, topology and QoS constraints."""

        req = task.get("requirements", task)
        nodes = candidate_subnet["nodes"]
        violations: list[str] = []

        capacity_ok = self._capacity(req, nodes, violations)
        performance_ok = self._performance(req, nodes, violations)
        topology_ok = self._topology(req, nodes, violations)
        qos_ok = self._qos(req, nodes, violations)
        verification_score = max(0.0, 1.0 - 0.12 * len(violations))
        return {
            "capacity_satisfied": capacity_ok,
            "performance_satisfied": performance_ok,
            "topology_satisfied": topology_ok,
            "qos_satisfied": qos_ok,
            "violations": violations,
            "verification_score": verification_score,
        }

    def _features(self, ids: list[str]) -> list[dict[str, Any]]:
        return [self.resources[node_id].get("features", {}) for node_id in ids if node_id in self.resources]

    def _capacity(self, req: dict[str, Any], nodes: dict[str, list[str]], violations: list[str]) -> bool:
        gpu = self._features(nodes.get("gpu", []))
        fpga = self._features(nodes.get("fpga", []))
        cpu = self._features(nodes.get("cpu", []))
        mem = self._features(nodes.get("memory", []))
        compute = sum(f.get("fp32_tflops", 0.0) for f in gpu) + sum(f.get("dsp_blocks", 0.0) / 500.0 for f in fpga)
        tensor = sum(f.get("tensor_tflops", 0.0) for f in gpu)
        vram = sum(f.get("vram_gb", 0.0) for f in gpu)
        cores = sum(f.get("cores", 0.0) for f in cpu)
        memory = sum(f.get("capacity_gb", 0.0) for f in mem) + sum(f.get("memory_gb", 0.0) for f in cpu)
        checks = [
            (compute >= req.get("min_compute_tflops", 0.0), "compute_tflops"),
            (tensor >= req.get("min_tensor_tflops", 0.0), "tensor_tflops"),
            (vram >= req.get("min_gpu_memory_gb", 0.0), "gpu_memory"),
            (cores >= req.get("min_cpu_cores", 0.0), "cpu_cores"),
            (memory >= req.get("min_memory_gb", 0.0), "memory_gb"),
        ]
        for ok, name in checks:
            if not ok:
                violations.append(f"capacity:{name}")
        return all(ok for ok, _ in checks)

    def _performance(self, req: dict[str, Any], nodes: dict[str, list[str]], violations: list[str]) -> bool:
        storage = self._features(nodes.get("storage", []))
        nics = self._features(nodes.get("nic", []))
        storage_bw = max([min(f.get("read_bw_gbps", 0.0), f.get("write_bw_gbps", 0.0)) for f in storage] or [0.0])
        network_bw = sum(f.get("bandwidth_gbps", 0.0) for f in nics)
        latency = min([f.get("latency_us", 1e9) for f in nics] or [1e9])
        checks = [
            (storage_bw >= req.get("min_storage_bw_gbps", 0.0), "storage_bw"),
            (network_bw >= req.get("min_network_bw_gbps", 0.0), "network_bw"),
            (latency <= req.get("max_latency_us", 1e9), "latency"),
        ]
        for ok, name in checks:
            if not ok:
                violations.append(f"performance:{name}")
        return all(ok for ok, _ in checks)

    def _topology(self, req: dict[str, Any], nodes: dict[str, list[str]], violations: list[str]) -> bool:
        selected = [node_id for ids in nodes.values() for node_id in ids]
        ok = True
        if req.get("prefer_same_node", 0.0):
            node_ids = {self.resources[n].get("node_id") for n in selected if n in self.resources and self.resources[n].get("type") in {"cpu", "gpu", "nic", "memory"}}
            if len(node_ids - {None}) > 1:
                violations.append("topology:not_same_node")
                ok = False
        if req.get("need_rdma", 0.0):
            if not any(f.get("rdma_support", 0.0) for f in self._features(nodes.get("nic", []))):
                violations.append("topology:rdma")
                ok = False
        if selected and not self._connected(selected):
            violations.append("topology:not_connected")
            ok = False
        return ok

    def _connected(self, selected: list[str]) -> bool:
        selected_set = set(selected)
        start = selected[0]
        seen = {start}
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in self.adj.get(current, set()):
                if nxt in selected_set and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return selected_set.issubset(seen)

    def _qos(self, req: dict[str, Any], nodes: dict[str, list[str]], violations: list[str]) -> bool:
        deadline = req.get("deadline_ms", 1e12)
        compute = sum(f.get("fp32_tflops", 0.0) for f in self._features(nodes.get("gpu", []))) + 1.0
        load = sum(f.get("utilization", 0.0) for ids in nodes.values() for f in self._features(ids))
        execution_time = 1000.0 * (1.0 + load / 10.0) / compute
        if execution_time > deadline:
            violations.append("qos:deadline")
            return False
        return True
