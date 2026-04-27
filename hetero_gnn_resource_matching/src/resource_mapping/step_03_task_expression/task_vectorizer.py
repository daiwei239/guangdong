"""Task requirement vectorization."""

from __future__ import annotations

from typing import Any

import numpy as np

from resource_mapping.step_01_resource_description.constants import DOMINANT_MODES, TASK_NUMERIC_FIELDS, TASK_TYPES


class TaskVectorizer:
    """Convert task dictionaries into fixed-length numeric vectors."""

    def __init__(self) -> None:
        self.dim = len(TASK_TYPES) + len(DOMINANT_MODES) + len(TASK_NUMERIC_FIELDS)

    def transform_one(self, task: dict[str, Any]) -> np.ndarray:
        """Vectorize one task."""

        req = task.get("requirements", task)
        task_type = task.get("task_type", req.get("task_type", "mixed"))
        dominant_mode = task.get("dominant_mode", req.get("dominant_mode", "mixed"))
        values: list[float] = []
        values.extend(1.0 if task_type == item else 0.0 for item in TASK_TYPES)
        values.extend(1.0 if dominant_mode == item else 0.0 for item in DOMINANT_MODES)
        for field in TASK_NUMERIC_FIELDS:
            value = req.get(field, 0.0)
            values.append(float(value))
        arr = np.asarray(values, dtype=np.float32)
        return np.nan_to_num(arr)

    def transform(self, tasks: list[dict[str, Any]]) -> np.ndarray:
        """Vectorize a list of tasks."""

        return np.stack([self.transform_one(task) for task in tasks], axis=0)
