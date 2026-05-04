import torch

from app.algorithms.feature_builder import EDGE_ATTR_DIM, build_edge_index_and_attr_dict, build_mock_heterodata_from_resources
from app.mock.mock_resource_generator import MockResourceGenerator
from app.schemas.resource_schema import ResourceEdgeRead
from app.utils.id_generator import generate_id


def _make_resources():
    return MockResourceGenerator().generate_resources()


def test_edge_attr_shape() -> None:
    resources = _make_resources()
    cpu = next(resource for resource in resources if resource.type == "CPU")
    gpu = next(resource for resource in resources if resource.type == "GPU")
    edge = ResourceEdgeRead(
        id=generate_id("edge"),
        source=cpu.id,
        target=gpu.id,
        relation_type="SAME_HOST",
        bandwidth_gbps=150.0,
        latency_ms=0.4,
        weight=0.7,
    )

    _, edge_attr_dict = build_edge_index_and_attr_dict(resources, [edge])

    assert edge_attr_dict[("CPU", "SAME_HOST", "GPU")].shape == (1, EDGE_ATTR_DIM)
    assert edge_attr_dict[("GPU", "REV_SAME_HOST", "CPU")].shape == (1, EDGE_ATTR_DIM)


def test_reverse_edges() -> None:
    resources = _make_resources()
    gpu = next(resource for resource in resources if resource.type == "GPU")
    nic = next(resource for resource in resources if resource.type == "NIC")
    edge = ResourceEdgeRead(
        id=generate_id("edge"),
        source=gpu.id,
        target=nic.id,
        relation_type="LOW_LATENCY_LINK",
        bandwidth_gbps=200.0,
        latency_ms=0.3,
        weight=0.9,
    )

    edge_index_dict, edge_attr_dict = build_edge_index_and_attr_dict(resources, [edge])

    assert ("GPU", "LOW_LATENCY_LINK", "NIC") in edge_index_dict
    assert ("NIC", "REV_LOW_LATENCY_LINK", "GPU") in edge_index_dict
    assert torch.equal(
        edge_attr_dict[("GPU", "LOW_LATENCY_LINK", "NIC")],
        edge_attr_dict[("NIC", "REV_LOW_LATENCY_LINK", "GPU")],
    )


def test_build_mock_heterodata_contains_edge_attr_dict() -> None:
    resources = _make_resources()
    storage = next(resource for resource in resources if resource.type == "STORAGE")
    nic = next(resource for resource in resources if resource.type == "NIC")
    edge = ResourceEdgeRead(
        id=generate_id("edge"),
        source=storage.id,
        target=nic.id,
        relation_type="LOW_LATENCY_LINK",
        bandwidth_gbps=120.0,
        latency_ms=0.6,
        weight=0.6,
    )

    data = build_mock_heterodata_from_resources(resources, [edge])

    assert data.edge_attr_dict[("STORAGE", "LOW_LATENCY_LINK", "NIC")].shape == (1, EDGE_ATTR_DIM)
