"""Heuristic candidate resource subnet generation."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from resource_mapping.constants import CANDIDATE_NODE_TEMPLATE, NODE_TYPES


class CandidateGenerator:
    """Generate coarse candidates before GNN scoring."""

    def __init__(self, resources: list[dict[str, Any]], edges: list[dict[str, Any]], seed: int = 42) -> None:
        self.resources = resources
        self.edges = edges
        self.rng = random.Random(seed)
        self.by_id = {r["id"]: r for r in resources}
        self.by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.adj: dict[str, set[str]] = defaultdict(set)
        for resource in resources:
            if bool(resource.get("features", {}).get("available", 1.0)):
                self.by_type[resource["type"]].append(resource)
        for edge in edges:
            self.adj[edge["source"]].add(edge["target"])
            self.adj[edge["target"]].add(edge["source"])

    def generate(self, task: dict[str, Any], max_candidates: int = 20) -> list[dict[str, Any]]:
        """Generate at most max_candidates candidate subnets for a task."""

        task_id = task["task_id"]
        mode = task.get("dominant_mode", task.get("requirements", {}).get("dominant_mode", "mixed"))
        seeds = self._seed_nodes(mode)
        if not seeds:
            seeds = [r["id"] for r in self.resources if bool(r.get("features", {}).get("available", 1.0))]

        candidates: list[dict[str, Any]] = []
        seen: set[tuple[tuple[str, tuple[str, ...]], ...]] = set()
        attempts = max_candidates * 20
        for _ in range(attempts):
            if len(candidates) >= max_candidates:
                break
            seed_id = self.rng.choice(seeds)
            nodes = self._assemble_from_seed(seed_id)
            key = tuple(sorted((k, tuple(sorted(v))) for k, v in nodes.items()))
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"candidate_id": f"{task_id}_cand_{len(candidates):03d}", "task_id": task_id, "nodes": nodes})
        return candidates

    def _seed_nodes(self, mode: str) -> list[str]:
        if mode == "compute_intensive":
            types = ["gpu", "fpga"]
        elif mode == "data_intensive":
            types = ["storage"]
        elif mode == "communication_intensive":
            types = ["nic", "switch"]
        else:
            types = ["gpu", "cpu", "storage", "nic"]
        return [r["id"] for t in types for r in self.by_type.get(t, [])]

    def _assemble_from_seed(self, seed_id: str) -> dict[str, list[str]]:
        nodes = {k: list(v) for k, v in CANDIDATE_NODE_TEMPLATE.items()}
        neighborhood = {seed_id} | set(self.adj.get(seed_id, set()))
        for n1 in list(neighborhood):
            neighborhood |= set(self.adj.get(n1, set()))

        available_by_type: dict[str, list[str]] = defaultdict(list)
        for node_id in neighborhood:
            resource = self.by_id.get(node_id)
            if resource and bool(resource.get("features", {}).get("available", 1.0)):
                available_by_type[resource["type"]].append(node_id)
        for node_type in NODE_TYPES:
            if not available_by_type[node_type]:
                available_by_type[node_type] = [r["id"] for r in self.by_type.get(node_type, [])]

        accel_type = "gpu" if available_by_type["gpu"] and self.rng.random() > 0.25 else "fpga"
        accel_count = self.rng.randint(1, min(4, max(1, len(available_by_type[accel_type]))))
        nodes[accel_type] = self.rng.sample(available_by_type[accel_type], k=accel_count) if available_by_type[accel_type] else []
        for node_type, count in [("cpu", self.rng.randint(1, 2)), ("memory", 1), ("storage", 1), ("nic", 1)]:
            pool = available_by_type[node_type]
            nodes[node_type] = self.rng.sample(pool, k=min(count, len(pool))) if pool else []
        if available_by_type["switch"] and self.rng.random() > 0.2:
            nodes["switch"] = [self.rng.choice(available_by_type["switch"])]
        return nodes
