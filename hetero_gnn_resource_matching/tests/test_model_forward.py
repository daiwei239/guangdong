import torch

from resource_mapping.step_02_resource_graph.graph_builder import ResourceGraphBuilder
from resource_mapping.step_03_task_expression.task_vectorizer import TaskVectorizer
from resource_mapping.step_04_candidate_gnn_matching.model import TaskConditionedResourceMatcher


def test_model_forward_outputs_batch_logits() -> None:
    from conftest import sample_candidate, sample_edges, sample_resources, sample_task

    builder = ResourceGraphBuilder()
    data = builder.build(sample_resources(), sample_edges())
    candidate = builder.ids_to_indices(sample_candidate()["nodes"])
    vectorizer = TaskVectorizer()
    task_vectors = torch.tensor([vectorizer.transform_one(sample_task()), vectorizer.transform_one(sample_task())], dtype=torch.float)
    model = TaskConditionedResourceMatcher(data.metadata(), vectorizer.dim, hidden_dim=32, num_layers=1, num_heads=2, dropout=0.0)
    logits, scores = model(data, task_vectors, [candidate, candidate])
    assert logits.shape == (2, 1)
    assert scores.shape == (2, 1)
