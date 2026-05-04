from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator
from app.services.graph_service import GraphService


def test_graph_service_builds_resource_graph_with_frontend_fields() -> None:
    resources = MockResourceGenerator().generate_resources()
    edges = MockTopologyGenerator().generate_edges(resources)

    graph_service = GraphService()
    result = graph_service.build_graph_snapshot(resources, edges)

    assert len(result["nodes"]) == 36
    assert 50 <= len(result["edges"]) <= 70

    node = result["nodes"][0]
    assert {
        "id",
        "label",
        "type",
        "cluster_id",
        "x",
        "y",
        "status",
        "utilization",
        "available",
        "is_candidate",
        "is_top1",
    } <= set(node)

    edge = result["edges"][0]
    assert {
        "id",
        "source",
        "target",
        "relation_type",
        "bandwidth_gbps",
        "latency_ms",
        "is_candidate_edge",
        "is_top1_edge",
    } <= set(edge)
