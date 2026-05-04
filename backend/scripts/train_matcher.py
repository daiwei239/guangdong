from __future__ import annotations

import random
import sys
from pathlib import Path

import torch
from torch import nn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.algorithms.feature_builder import RESOURCE_INPUT_DIMS, TASK_INPUT_DIM, build_mock_heterodata_from_resources, build_task_feature_tensor
from app.algorithms.matcher_model import TaskResourceMatcher
from app.algorithms.score import ScoreCalculator
from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_task_generator import MockTaskGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator


def build_mock_training_batch(num_samples: int = 8):
    resource_generator = MockResourceGenerator()
    topology_generator = MockTopologyGenerator()
    task_generator = MockTaskGenerator()
    scorer = ScoreCalculator()
    samples = []

    for _ in range(num_samples):
        resources = resource_generator.generate_resources()
        edges = topology_generator.generate_edges(resources)
        task = task_generator.generate_task_profile()
        data = build_mock_heterodata_from_resources(resources, edges)
        task_vec = build_task_feature_tensor(task)
        resource_lookup = {resource.id: resource for resource in resources}
        candidate_ids = [resource.id for resource in resources[: random.randint(6, 10)]]
        rule_candidate = scorer.score_candidate(task, resource_lookup, scorer_graph(resources, edges), candidate_ids, rank=1)
        label = torch.tensor([[1.0 if rule_candidate.final_score >= 55.0 else 0.0]], dtype=torch.float32)
        samples.append((data, task_vec, label))
    return samples


def scorer_graph(resources, edges):
    import networkx as nx

    graph = nx.Graph()
    for resource in resources:
        graph.add_node(resource.id)
    for edge in edges:
        payload = edge.model_dump() if hasattr(edge, "model_dump") else edge.dict()
        graph.add_edge(edge.source, edge.target, **payload)
    return graph


def main() -> None:
    model = TaskResourceMatcher(input_dims=RESOURCE_INPUT_DIMS, task_dim=TASK_INPUT_DIM, hidden_dim=64, out_dim=64)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.BCEWithLogitsLoss()
    samples = build_mock_training_batch(num_samples=10)

    model.train()
    for epoch in range(3):
        total_loss = 0.0
        for data, task_vec, label in samples:
            optimizer.zero_grad()
            score, _, _ = model(data, task_vec)
            loss = criterion(score, label)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
        print({"epoch": epoch + 1, "avg_loss": round(total_loss / len(samples), 4)})


if __name__ == "__main__":
    main()
