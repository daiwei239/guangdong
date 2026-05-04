import torch

from app.algorithms.feature_builder import EDGE_ATTR_DIM, RESOURCE_INPUT_DIMS, build_mock_heterodata_from_resources
from app.algorithms.gnn_encoder import ResourceGraphEncoder
from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator
from app.schemas.resource_schema import ResourceEdgeRead
from app.utils.id_generator import generate_id


def _build_targeted_edges(resources):
    cpu = next(resource for resource in resources if resource.type == "CPU")
    gpu_nodes = [resource for resource in resources if resource.type == "GPU"]
    nic = next(resource for resource in resources if resource.type == "NIC")
    gpu_a, gpu_b = gpu_nodes[0], gpu_nodes[1]
    return [
        ResourceEdgeRead(
            id=generate_id("edge"),
            source=cpu.id,
            target=gpu_a.id,
            relation_type="SAME_HOST",
            bandwidth_gbps=120.0,
            latency_ms=0.5,
            weight=0.8,
        ),
        ResourceEdgeRead(
            id=generate_id("edge"),
            source=gpu_a.id,
            target=nic.id,
            relation_type="LOW_LATENCY_LINK",
            bandwidth_gbps=200.0,
            latency_ms=0.2,
            weight=0.9,
        ),
        ResourceEdgeRead(
            id=generate_id("edge"),
            source=gpu_a.id,
            target=gpu_b.id,
            relation_type="COMPETES_BANDWIDTH",
            bandwidth_gbps=80.0,
            latency_ms=1.0,
            weight=0.4,
        ),
    ]


def test_edge_type_not_dropped() -> None:
    resources = MockResourceGenerator().generate_resources()
    data = build_mock_heterodata_from_resources(resources, _build_targeted_edges(resources))

    encoder = ResourceGraphEncoder(input_dims=RESOURCE_INPUT_DIMS, hidden_dim=32, out_dim=16, num_layers=2, heads=2)
    z_subgraph, x_dict = encoder(data)

    assert ("CPU", "SAME_HOST", "GPU") in encoder.last_edge_types
    assert ("GPU", "LOW_LATENCY_LINK", "NIC") in encoder.last_edge_types
    assert ("GPU", "COMPETES_BANDWIDTH", "GPU") in encoder.last_edge_types
    assert ("GPU", "REV_SAME_HOST", "CPU") in encoder.last_edge_types
    assert z_subgraph.shape == (1, 16)
    assert x_dict["GPU"].shape[-1] == 16


def test_output_shape() -> None:
    resources = MockResourceGenerator().generate_resources()
    edges = MockTopologyGenerator().generate_edges(resources)
    data = build_mock_heterodata_from_resources(resources, edges)

    encoder = ResourceGraphEncoder(input_dims=RESOURCE_INPUT_DIMS, hidden_dim=64, out_dim=64)
    z_subgraph, x_dict = encoder(data, task_type="计算密集型")

    assert z_subgraph.shape == (1, 64)
    for resource_type, tensor in x_dict.items():
        assert tensor.shape[-1] == 64


def test_task_aware_pooling() -> None:
    encoder = ResourceGraphEncoder(input_dims=RESOURCE_INPUT_DIMS, hidden_dim=16, out_dim=8)
    x_dict = {
        "CPU": torch.ones(2, 8),
        "GPU": torch.full((2, 8), 2.0),
        "FPGA": torch.full((1, 8), 3.0),
        "MEMORY": torch.full((1, 8), 4.0),
        "STORAGE": torch.full((1, 8), 5.0),
        "NIC": torch.full((1, 8), 6.0),
        "SWITCH": torch.full((1, 8), 7.0),
    }

    compute_pool = encoder.pool_subgraph(x_dict, task_type="计算密集型")
    communication_pool = encoder.pool_subgraph(x_dict, task_type="通信密集型")

    assert compute_pool.shape == (1, 8)
    assert communication_pool.shape == (1, 8)
    assert not torch.allclose(compute_pool, communication_pool)
