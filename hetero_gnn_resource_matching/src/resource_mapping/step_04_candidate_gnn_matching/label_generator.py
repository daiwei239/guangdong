"""Pseudo-label generation from expert verification rules."""

from __future__ import annotations

from typing import Any

from resource_mapping.step_05_ranking_verification.verify import ResourceVerifier


class LabelGenerator:
    """Generate binary labels and dense expert scores for candidates."""

    def __init__(self, resources: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        self.verifier = ResourceVerifier(resources, edges)

    def generate(self, tasks: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Label the best verified candidate per task as positive."""

        task_by_id = {task["task_id"]: task for task in tasks}
        by_task: dict[str, list[dict[str, Any]]] = {}
        for cand in candidates:
            by_task.setdefault(cand["task_id"], []).append(cand)

        labels: list[dict[str, Any]] = []
        for task_id, task_candidates in by_task.items():
            scored = []
            for cand in task_candidates:
                verification = self.verifier.verify(task_by_id[task_id], cand)
                scored.append((cand, verification["verification_score"], not verification["violations"]))
            verified = [item for item in scored if item[2]]
            best_id = max(verified or scored, key=lambda item: item[1])[0]["candidate_id"]
            for cand, score, _ in scored:
                labels.append({"task_id": task_id, "candidate_id": cand["candidate_id"], "y": 1 if cand["candidate_id"] == best_id else 0, "expert_score": score})
        return labels
