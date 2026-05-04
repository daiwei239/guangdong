from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_task_generator import MockTaskGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator
from app.services.graph_service import GraphService
from app.services.matching_service import MatchingService


def test_matching_service_returns_three_ranked_candidates_and_top1() -> None:
    resources = MockResourceGenerator().generate_resources()
    edges = MockTopologyGenerator().generate_edges(resources)
    task = MockTaskGenerator().generate_task_profile()

    graph_service = GraphService()
    graph = graph_service.build_networkx_graph(resources, edges)

    matching_service = MatchingService()
    result = matching_service.match_task(task, resources, edges, graph)

    assert len(result.candidates) == 3
    assert result.top1.is_top1 is True
    assert result.top1.rank == 1
    assert result.verification.capacity_ok in {True, False}
    assert result.verification.performance_ok in {True, False}
    assert result.verification.topology_ok in {True, False}
    assert result.verification.qos_ok in {True, False}

    artifacts = matching_service.get_encoding_artifacts(task.task_id)
    assert artifacts is not None
    assert artifacts["encoder_used"] is True
    assert len(artifacts["full_graph_embedding"]) == 64
    assert len(artifacts["candidate_embeddings"]) >= 1
    assert len(artifacts["top1_embedding"]) == 64
