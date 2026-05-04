from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.algorithms.beam_search import BeamSearchSubgraphFinder
from app.algorithms.feature_builder import RESOURCE_INPUT_DIMS, TASK_INPUT_DIM, build_mock_heterodata_from_resources, build_task_feature_tensor
from app.algorithms.matcher_model import TaskResourceMatcher
from app.algorithms.score import ScoreCalculator
from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_task_generator import MockTaskGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator


def build_graph(resources, edges):
    graph = nx.Graph()
    for resource in resources:
        payload = resource.model_dump() if hasattr(resource, "model_dump") else resource.dict()
        graph.add_node(resource.id, **payload)
    for edge in edges:
        payload = edge.model_dump() if hasattr(edge, "model_dump") else edge.dict()
        graph.add_edge(edge.source, edge.target, **payload)
    return graph


def main() -> None:
    resource_generator = MockResourceGenerator()
    topology_generator = MockTopologyGenerator()
    task_generator = MockTaskGenerator()
    scorer = ScoreCalculator()
    matcher = TaskResourceMatcher(input_dims=RESOURCE_INPUT_DIMS, task_dim=TASK_INPUT_DIM, hidden_dim=64, out_dim=64)
    matcher.eval()

    resources = resource_generator.generate_resources()
    edges = topology_generator.generate_edges(resources)
    task = task_generator.generate_task_profile()
    task_vec = build_task_feature_tensor(task)
    graph = build_graph(resources, edges)
    searcher = BeamSearchSubgraphFinder()
    candidate_node_sets = searcher.search(task, resources, graph)[:3]
    resource_lookup = {resource.id: resource for resource in resources}
    ranking = []

    with torch.no_grad():
        for rank, node_ids in enumerate(candidate_node_sets, start=1):
            sub_resources = [resource_lookup[node_id] for node_id in node_ids]
            sub_edges = [edge for edge in edges if edge.source in node_ids and edge.target in node_ids]
            data = build_mock_heterodata_from_resources(sub_resources, sub_edges)
            model_score, z_subgraph, _ = matcher(data, task_vec)
            rule_candidate = scorer.score_candidate(task, resource_lookup, graph, node_ids, rank=rank)
            ranking.append(
                {
                    "rank": rank,
                    "subgraph_id": rule_candidate.subgraph_id,
                    "nodes": node_ids,
                    "model_score": round(float(torch.sigmoid(model_score).item()), 4),
                    "rule_final_score": rule_candidate.final_score,
                    "z_subgraph_shape": list(z_subgraph.shape),
                }
            )

    ranking.sort(key=lambda item: (item["rule_final_score"], item["model_score"]), reverse=True)
    print(json.dumps({"task_id": task.task_id, "candidates": ranking}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
