"""Command line training for the task-conditioned matcher."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from resource_mapping.dataset import CandidateDataset, collate_candidate_batch
from resource_mapping.graph_builder import ResourceGraphBuilder
from resource_mapping.io_utils import get_device, load_json, load_yaml, resolve_path, set_seed
from resource_mapping.losses import matching_loss
from resource_mapping.model import TaskConditionedResourceMatcher
from resource_mapping.task_vectorizer import TaskVectorizer


def _filter_labels(labels: list[dict[str, Any]], task_ids: set[str]) -> list[dict[str, Any]]:
    return [label for label in labels if label["task_id"] in task_ids]


def _topk_metrics(logits: torch.Tensor, labels: torch.Tensor, task_ids: list[str], k: int = 5) -> tuple[float, float]:
    scores = logits.view(-1).detach().cpu()
    ys = labels.view(-1).detach().cpu()
    groups: dict[str, list[int]] = {}
    for idx, tid in enumerate(task_ids):
        groups.setdefault(tid, []).append(idx)
    top1_hits = 0
    topk_hits = 0
    for idxs in groups.values():
        order = sorted(idxs, key=lambda i: float(scores[i]), reverse=True)
        top1_hits += int(ys[order[0]] > 0.5)
        topk_hits += int(any(ys[i] > 0.5 for i in order[:k]))
    denom = max(1, len(groups))
    return top1_hits / denom, topk_hits / denom


def run_epoch(model: TaskConditionedResourceMatcher, data: Any, loader: DataLoader, optimizer: torch.optim.Optimizer | None, cfg: dict[str, Any], device: torch.device) -> tuple[float, float, float]:
    """Run one train or validation epoch."""

    is_train = optimizer is not None
    model.train(is_train)
    total_loss = 0.0
    all_logits = []
    all_labels = []
    all_task_ids: list[str] = []
    for batch in loader:
        task_vectors = batch["task_vectors"].to(device)
        labels = batch["labels"].to(device)
        if is_train:
            optimizer.zero_grad()
        logits, _ = model(data, task_vectors, batch["candidate_nodes"])
        loss = matching_loss(logits, labels, batch["task_ids"], cfg["lambda_rank"], cfg.get("lambda_constraint", 0.0), margin=cfg["margin"])
        if is_train:
            loss.backward()
            optimizer.step()
        total_loss += float(loss.detach()) * labels.size(0)
        all_logits.append(logits.detach())
        all_labels.append(labels.detach())
        all_task_ids.extend(batch["task_ids"])
    logits_cat = torch.cat(all_logits, dim=0)
    labels_cat = torch.cat(all_labels, dim=0)
    top1, top5 = _topk_metrics(logits_cat, labels_cat, all_task_ids, k=5)
    return total_loss / max(1, len(loader.dataset)), top1, top5


def main() -> None:
    """Train a matcher and save the best checkpoint."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    project_dir = Path.cwd()
    cfg = load_yaml(resolve_path(project_dir, args.config))
    set_seed(int(cfg["seed"]))
    paths = cfg["paths"]
    resources = load_json(resolve_path(project_dir, paths["resources"]))
    edges = load_json(resolve_path(project_dir, paths["edges"]))
    tasks = load_json(resolve_path(project_dir, paths["tasks"]))
    candidates = load_json(resolve_path(project_dir, paths["candidates"]))
    labels = load_json(resolve_path(project_dir, paths["labels"]))
    splits = load_json(resolve_path(project_dir, paths["splits"]))

    builder = ResourceGraphBuilder()
    data = builder.build(resources, edges)
    device = get_device(cfg["device"])
    data = data.to(device)
    train_ds = CandidateDataset(tasks, candidates, _filter_labels(labels, set(splits["train"])), builder)
    val_ds = CandidateDataset(tasks, candidates, _filter_labels(labels, set(splits["val"])), builder)
    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True, collate_fn=collate_candidate_batch)
    val_loader = DataLoader(val_ds, batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate_candidate_batch)

    model = TaskConditionedResourceMatcher(data.metadata(), TaskVectorizer().dim, cfg["hidden_dim"], cfg["num_layers"], cfg["num_heads"], cfg["dropout"]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    best_top1 = -1.0
    ckpt_path = resolve_path(project_dir, paths["checkpoint"])
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, cfg["epochs"] + 1):
        train_loss, _, _ = run_epoch(model, data, train_loader, optimizer, cfg, device)
        with torch.no_grad():
            val_loss, val_top1, val_top5 = run_epoch(model, data, val_loader, None, cfg, device)
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_top1={val_top1:.4f} val_top5={val_top5:.4f}")
        if val_top1 > best_top1:
            best_top1 = val_top1
            torch.save({"model_state": model.state_dict(), "config": cfg, "metadata": data.metadata(), "task_dim": TaskVectorizer().dim}, ckpt_path)


if __name__ == "__main__":
    main()
