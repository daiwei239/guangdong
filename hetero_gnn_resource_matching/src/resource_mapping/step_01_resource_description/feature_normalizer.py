"""Simple per-type feature normalization."""

from __future__ import annotations

import torch


class FeatureNormalizer:
    """Normalize node features per type with z-score statistics."""

    def __init__(self) -> None:
        self.stats: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}

    def fit(self, x_dict: dict[str, torch.Tensor]) -> "FeatureNormalizer":
        """Fit mean and std for each node type."""

        for node_type, x in x_dict.items():
            mean = x.mean(dim=0, keepdim=True)
            std = x.std(dim=0, keepdim=True).clamp_min(1e-6)
            self.stats[node_type] = (mean, std)
        return self

    def transform(self, x_dict: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Transform each node feature tensor."""

        return {k: (x - self.stats[k][0]) / self.stats[k][1] for k, x in x_dict.items()}
