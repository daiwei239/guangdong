"""PyTorch dataset for task-candidate matching samples."""

from __future__ import annotations

from typing import Any

import torch
from torch.utils.data import Dataset

from resource_mapping.step_02_resource_graph.graph_builder import ResourceGraphBuilder
from resource_mapping.step_03_task_expression.task_vectorizer import TaskVectorizer


class CandidateDataset(Dataset):
    """Flatten task candidates into supervised samples."""

    def __init__(
        self,
        tasks: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        labels: list[dict[str, Any]],
        graph_builder: ResourceGraphBuilder,
    ) -> None:
        self.task_by_id = {task["task_id"]: task for task in tasks}
        self.candidate_by_id = {cand["candidate_id"]: cand for cand in candidates}
        self.vectorizer = TaskVectorizer()
        self.samples = []
        for label in labels:
            cand = self.candidate_by_id[label["candidate_id"]]
            task = self.task_by_id[label["task_id"]]
            self.samples.append(
                {
                    "task_id": label["task_id"],
                    "candidate_id": label["candidate_id"],
                    "task_vector": torch.tensor(self.vectorizer.transform_one(task), dtype=torch.float),
                    "candidate_nodes": graph_builder.ids_to_indices(cand["nodes"]),
                    "label": torch.tensor(float(label["y"]), dtype=torch.float),
                }
            )

    def __len__(self) -> int:
        """Return sample count."""

        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        """Return one sample."""

        return self.samples[idx]


def collate_candidate_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Collate variable-size candidate node dictionaries."""

    return {
        "task_ids": [item["task_id"] for item in batch],
        "candidate_ids": [item["candidate_id"] for item in batch],
        "task_vectors": torch.stack([item["task_vector"] for item in batch], dim=0),
        "candidate_nodes": [item["candidate_nodes"] for item in batch],
        "labels": torch.stack([item["label"] for item in batch], dim=0).view(-1, 1),
    }
