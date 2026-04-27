"""Training losses for matching and ranking."""

from __future__ import annotations

import torch
from torch import nn


def pairwise_ranking_loss(logits: torch.Tensor, labels: torch.Tensor, task_ids: list[str], margin: float = 0.2) -> torch.Tensor:
    """Compute pairwise ranking loss within each task."""

    losses = []
    flat_logits = logits.view(-1)
    flat_labels = labels.view(-1)
    for task_id in sorted(set(task_ids)):
        idx = [i for i, tid in enumerate(task_ids) if tid == task_id]
        pos = [i for i in idx if flat_labels[i] > 0.5]
        neg = [i for i in idx if flat_labels[i] <= 0.5]
        for p in pos:
            for n in neg:
                losses.append(torch.relu(torch.tensor(margin, device=logits.device) - flat_logits[p] + flat_logits[n]))
    if not losses:
        return torch.zeros((), device=logits.device)
    return torch.stack(losses).mean()


def matching_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    task_ids: list[str],
    lambda_rank: float = 0.5,
    lambda_constraint: float = 0.0,
    constraint_penalty: torch.Tensor | None = None,
    margin: float = 0.2,
) -> torch.Tensor:
    """Compute BCE + ranking + optional constraint penalty."""

    score_loss = nn.BCEWithLogitsLoss()(logits, labels)
    rank_loss = pairwise_ranking_loss(logits, labels, task_ids, margin)
    constraint_loss = constraint_penalty.mean() if constraint_penalty is not None else torch.zeros((), device=logits.device)
    return score_loss + lambda_rank * rank_loss + lambda_constraint * constraint_loss
