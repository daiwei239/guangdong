"""Evaluate saved matcher on the test split."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score

from resource_mapping.dataset import CandidateDataset, collate_candidate_batch
from resource_mapping.graph_builder import ResourceGraphBuilder
from resource_mapping.io_utils import get_device, load_json, load_yaml, resolve_path, save_json
from resource_mapping.model import TaskConditionedResourceMatcher
from resource_mapping.task_vectorizer import TaskVectorizer
from resource_mapping.verify import ResourceVerifier


def main() -> None:
    """Evaluate ranking, classification and verification metrics."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", default="outputs/checkpoints/best_model.pt")
    args = parser.parse_args()
    project_dir = Path.cwd()
    cfg = load_yaml(resolve_path(project_dir, args.config))
    resources = load_json(resolve_path(project_dir, cfg["paths"]["resources"]))
    edges = load_json(resolve_path(project_dir, cfg["paths"]["edges"]))
    tasks = load_json(resolve_path(project_dir, cfg["paths"]["tasks"]))
    candidates = load_json(resolve_path(project_dir, cfg["paths"]["candidates"]))
    labels = load_json(resolve_path(project_dir, cfg["paths"]["labels"]))
    splits = load_json(resolve_path(project_dir, cfg["paths"]["splits"]))
    test_ids = set(splits["test"])
    test_labels = [l for l in labels if l["task_id"] in test_ids]
    builder = ResourceGraphBuilder()
    data = builder.build(resources, edges)
    device = get_device(cfg["device"])
    data = data.to(device)
    ds = CandidateDataset(tasks, candidates, test_labels, builder)
    model = TaskConditionedResourceMatcher(data.metadata(), TaskVectorizer().dim, cfg["hidden_dim"], cfg["num_layers"], cfg["num_heads"], cfg["dropout"]).to(device)
    model.load_state_dict(torch.load(resolve_path(project_dir, args.checkpoint), map_location=device)["model_state"])
    model.eval()
    start = time.perf_counter()
    batch = collate_candidate_batch([ds[i] for i in range(len(ds))])
    with torch.no_grad():
        _, scores = model(data, batch["task_vectors"].to(device), batch["candidate_nodes"])
    gnn_time = time.perf_counter() - start
    y_true = batch["labels"].view(-1).numpy()
    y_score = scores.view(-1).detach().cpu().numpy()
    y_pred = (y_score >= 0.5).astype(int)
    groups: dict[str, list[int]] = {}
    for idx, tid in enumerate(batch["task_ids"]):
        groups.setdefault(tid, []).append(idx)
    top1 = top5 = mrr = 0.0
    for idxs in groups.values():
        order = sorted(idxs, key=lambda i: float(y_score[i]), reverse=True)
        top1 += float(y_true[order[0]] > 0.5)
        top5 += float(any(y_true[i] > 0.5 for i in order[:5]))
        ranks = [rank + 1 for rank, i in enumerate(order) if y_true[i] > 0.5]
        mrr += 1.0 / ranks[0] if ranks else 0.0
    denom = max(1, len(groups))
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    auc = roc_auc_score(y_true, y_score) if len(set(y_true.tolist())) > 1 else 0.0
    verifier = ResourceVerifier(resources, edges)
    task_by_id = {t["task_id"]: t for t in tasks}
    cand_by_id = {c["candidate_id"]: c for c in candidates}
    verified = [not verifier.verify(task_by_id[tid], cand_by_id[cid])["violations"] for tid, cid in zip(batch["task_ids"], batch["candidate_ids"])]
    metrics: dict[str, Any] = {
        "top1_accuracy": top1 / denom,
        "top5_hit_rate": top5 / denom,
        "mean_reciprocal_rank": mrr / denom,
        "qos_satisfaction_rate": float(sum(verified) / max(1, len(verified))),
        "avg_candidate_search_time_ms": 0.0,
        "avg_gnn_inference_time_ms": 1000.0 * gnn_time / max(1, len(ds)),
        "constraint_satisfaction_rate": float(sum(verified) / max(1, len(verified))),
        "auc": float(auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }
    save_json(metrics, resolve_path(project_dir, cfg["paths"]["evaluation"]))
    print(metrics)


if __name__ == "__main__":
    main()
