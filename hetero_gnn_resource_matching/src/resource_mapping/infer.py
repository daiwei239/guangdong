"""Command line inference for top-k candidate resource subnets."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from resource_mapping.candidate_generator import CandidateGenerator
from resource_mapping.graph_builder import ResourceGraphBuilder
from resource_mapping.io_utils import get_device, load_json, load_yaml, resolve_path, save_json
from resource_mapping.model import TaskConditionedResourceMatcher
from resource_mapping.task_vectorizer import TaskVectorizer
from resource_mapping.verify import ResourceVerifier


def main() -> None:
    """Rank candidates for one task and verify top-k."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", default="outputs/checkpoints/best_model.pt")
    parser.add_argument("--task_id", required=True)
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()
    project_dir = Path.cwd()
    cfg = load_yaml(resolve_path(project_dir, args.config))
    resources = load_json(resolve_path(project_dir, cfg["paths"]["resources"]))
    edges = load_json(resolve_path(project_dir, cfg["paths"]["edges"]))
    tasks = load_json(resolve_path(project_dir, cfg["paths"]["tasks"]))
    task = next(t for t in tasks if t["task_id"] == args.task_id)
    builder = ResourceGraphBuilder()
    data = builder.build(resources, edges)
    device = get_device(cfg["device"])
    data = data.to(device)
    vectorizer = TaskVectorizer()
    candidates = CandidateGenerator(resources, edges, cfg["seed"]).generate(task, cfg["max_candidates"])
    candidate_indices = [builder.ids_to_indices(c["nodes"]) for c in candidates]
    task_vectors = torch.tensor([vectorizer.transform_one(task) for _ in candidates], dtype=torch.float, device=device)
    model = TaskConditionedResourceMatcher(data.metadata(), vectorizer.dim, cfg["hidden_dim"], cfg["num_layers"], cfg["num_heads"], cfg["dropout"]).to(device)
    ckpt = torch.load(resolve_path(project_dir, args.checkpoint), map_location=device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    with torch.no_grad():
        _, scores = model(data, task_vectors, candidate_indices)
    ranked = sorted(zip(candidates, scores.view(-1).detach().cpu().tolist()), key=lambda item: item[1], reverse=True)
    verifier = ResourceVerifier(resources, edges)
    top_items = []
    for cand, score in ranked[: args.top_k]:
        verification = verifier.verify(task, cand)
        top_items.append({"candidate_id": cand["candidate_id"], "score": float(score), "verified": not verification["violations"], "nodes": cand["nodes"], "verification": verification})
    result = {"task_id": args.task_id, "top_1_subnet": top_items[0] if top_items else None, "top_n_candidates": [{"candidate_id": item["candidate_id"], "score": item["score"], "verified": item["verified"]} for item in top_items]}
    save_json(result, resolve_path(project_dir, cfg["paths"]["topk_results"]))
    print(result)


if __name__ == "__main__":
    main()
