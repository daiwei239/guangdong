import networkx as nx

from app.algorithms.rule_filter import RuleFilter
from app.algorithms.score import ScoreCalculator
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


def test_topo_context_affects_seed_scoring() -> None:
    task = MockTaskGenerator().generate_task_profile()
    task.constraints["prefer_low_latency"] = True
    filter_ = RuleFilter()

    resource_good = MockResourceGenerator().generate_resources()[0].model_copy(deep=True)
    resource_bad = resource_good.model_copy(deep=True)
    resource_good.topo_context = {
        "server_id": "host-1",
        "rack_id": "rack-1",
        "cluster_id": "cluster-1",
        "zone_id": "zone-1",
        "network_tier": 1,
        "hop_level": 1,
    }
    resource_bad.topo_context = {
        "server_id": "host-8",
        "rack_id": "rack-4",
        "cluster_id": "cluster-3",
        "zone_id": "zone-2",
        "network_tier": 3,
        "hop_level": 4,
    }

    assert filter_.score_seed_fit(task, resource_good) > filter_.score_seed_fit(task, resource_bad)


def test_topo_context_affects_topology_score() -> None:
    calculator = ScoreCalculator()
    task = MockTaskGenerator().generate_task_profile()

    graph_good = nx.Graph()
    graph_good.add_node(
        "gpu-a",
        topo_context={"server_id": "host-1", "rack_id": "rack-1", "cluster_id": "cluster-1", "network_tier": 1, "hop_level": 1},
    )
    graph_good.add_node(
        "nic-a",
        topo_context={"server_id": "host-1", "rack_id": "rack-1", "cluster_id": "cluster-1", "network_tier": 1, "hop_level": 1},
    )
    graph_good.add_edge("gpu-a", "nic-a", latency_ms=2.5, bandwidth_gbps=40.0)

    graph_bad = nx.Graph()
    graph_bad.add_node(
        "gpu-b",
        topo_context={"server_id": "host-7", "rack_id": "rack-4", "cluster_id": "cluster-3", "network_tier": 3, "hop_level": 4},
    )
    graph_bad.add_node(
        "nic-b",
        topo_context={"server_id": "host-9", "rack_id": "rack-5", "cluster_id": "cluster-3", "network_tier": 3, "hop_level": 4},
    )
    graph_bad.add_edge("gpu-b", "nic-b", latency_ms=2.5, bandwidth_gbps=40.0)

    assert calculator.compute_topology_score(task, graph_good) > calculator.compute_topology_score(task, graph_bad)
