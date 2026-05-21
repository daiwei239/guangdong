from datetime import datetime

import networkx as nx
import torch

from app.algorithms.beam_search import BeamSearchSubgraphFinder
from app.algorithms.feature_builder import (
    RESOURCE_INPUT_DIMS,
    RESOURCE_TYPES,
    build_mock_heterodata_from_resources,
)
from app.algorithms.feature_encoder import ResourceFeatureEncoder
from app.algorithms.gnn_encoder import ResourceGraphEncoder
from app.algorithms.score import ScoreCalculator
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead


def _now():
    return datetime.utcnow()


def _node(node_id, resource_type, static_attrs, dynamic_state, host_id="server-1", rack_id="rack-1"):
    return ResourceNodeRead(
        id=node_id,
        name=node_id,
        type=resource_type,
        cluster_id="cluster-1",
        host_id=host_id,
        topo_context={
            "server_id": host_id,
            "rack_id": rack_id,
            "cluster_id": "cluster-1",
            "network_tier": 1,
            "hop_level": 1,
        },
        static_attrs=static_attrs,
        dynamic_state=dynamic_state,
        semantic_tags=[resource_type.lower()],
        created_at=_now(),
        updated_at=_now(),
    )


def _edge(edge_id, source, target, relation_type, bandwidth=100.0, latency=1.0, weight=0.8):
    return ResourceEdgeRead(
        id=edge_id,
        source=source,
        target=target,
        relation_type=relation_type,
        bandwidth_gbps=bandwidth,
        latency_ms=latency,
        weight=weight,
    )


def _mock_resources():
    return [
        _node(
            "cpu-1",
            "CPU",
            {"cores": 64, "frequency": 3.2},
            {"utilization": 30, "queue_length": 2, "power_watt": 180, "available": True},
        ),
        _node(
            "gpu-1",
            "GPU",
            {"memory_total": 80, "fp16_tflops": 300, "fp32_tflops": 150, "interconnect": "NVLink"},
            {"memory_free": 60, "utilization": 35, "temperature": 60, "power_watt": 350, "queue_length": 1, "available": True},
        ),
        _node(
            "memory-1",
            "MEMORY",
            {"capacity_gb": 512, "bandwidth_gbps": 400},
            {"memory_free": 384, "utilization": 25, "available": True},
        ),
        _node(
            "storage-1",
            "STORAGE",
            {"capacity_tb": 8, "throughput_gbps": 20, "iops": 1000000, "latency_ms": 0.5},
            {"storage_free": 6, "utilization": 20, "available": True},
        ),
        _node(
            "nic-1",
            "NIC",
            {"bandwidth_gbps": 200, "latency_ms": 1.0, "rdma_enabled": True},
            {"utilization": 25, "packet_loss": 0.01, "available": True},
        ),
        _node(
            "switch-1",
            "SWITCH",
            {"ports": 64, "bandwidth_gbps": 400, "latency_ms": 0.8},
            {"utilization": 20, "congestion": 0.1, "available": True},
        ),
    ]


def _mock_edges():
    return [
        _edge("e-cpu-mem", "cpu-1", "memory-1", "SHARES_MEMORY", bandwidth=300, latency=0.6),
        _edge("e-gpu-cpu", "gpu-1", "cpu-1", "SAME_HOST", bandwidth=200, latency=0.8),
        _edge("e-gpu-nic", "gpu-1", "nic-1", "CONNECTED_TO", bandwidth=200, latency=1.0),
        _edge("e-nic-switch", "nic-1", "switch-1", "CONNECTED_TO", bandwidth=200, latency=0.8),
        _edge("e-switch-storage", "switch-1", "storage-1", "LOW_LATENCY_LINK", bandwidth=100, latency=1.5),
        _edge("e-mem-nic", "memory-1", "nic-1", "SAME_RACK", bandwidth=160, latency=1.2),
    ]


def _mock_task():
    return TaskProfileRead(
        task_id="task-1",
        task_type="计算密集型",
        dag_nodes=[],
        compute_req={"cpu_cores": 16, "gpu_count": 1, "fp16_tflops": 120},
        memory_req={"capacity_gb": 128},
        storage_req={"capacity_tb": 2, "throughput_gbps": 5},
        network_req={"bandwidth_gbps": 100, "latency_ms": 5},
        energy_limit=2000.0,
        qos_deadline_sec=120.0,
        priority=5,
        constraints={
            "min_gpu_memory_gb": 40,
            "min_storage_throughput_gbps": 5,
            "max_network_latency_ms": 5,
            "max_resource_utilization": 90,
            "prefer_same_rack": True,
            "prefer_low_latency": True,
        },
    )


def _to_networkx_graph(resources, edges):
    graph = nx.Graph()
    for resource in resources:
        payload = resource.model_dump() if hasattr(resource, "model_dump") else resource.dict()
        graph.add_node(resource.id, **payload)
    for edge in edges:
        payload = edge.model_dump() if hasattr(edge, "model_dump") else edge.dict()
        graph.add_edge(edge.source, edge.target, **payload)
    return graph


def test_type_specific_encoder_accepts_lowercase_cpu_key():
    encoder = ResourceFeatureEncoder({"cpu": 5}, hidden_dim=8)
    output = encoder({"cpu": torch.ones((2, 5), dtype=torch.float32)})
    assert output["cpu"].shape == (2, 8)


def test_step2_builds_heterodata_and_runs_resource_gnn_forward():
    resources = _mock_resources()
    edges = _mock_edges()
    data = build_mock_heterodata_from_resources(resources, edges)

    for resource_type in RESOURCE_TYPES:
        assert resource_type in data.x_dict
        assert data.x_dict[resource_type].shape[1] == RESOURCE_INPUT_DIMS[resource_type]

    assert data.edge_index_dict
    assert data.edge_attr_dict
    assert any(edge_type[1] == "CONNECTED_TO" for edge_type in data.edge_index_dict)
    assert any(edge_type[1] == "REV_CONNECTED_TO" for edge_type in data.edge_index_dict)

    encoder = ResourceGraphEncoder(
        RESOURCE_INPUT_DIMS,
        hidden_dim=16,
        out_dim=16,
        num_layers=1,
        heads=1,
        dropout=0.0,
    )
    z_subgraph, node_embeddings = encoder(data, task_type="计算密集型")

    assert z_subgraph.shape == (1, 16)
    assert node_embeddings["GPU"].shape == (1, 16)
    assert node_embeddings["CPU"].shape == (1, 16)


def test_candidate_subnet_search_and_rule_score_pipeline():
    resources = _mock_resources()
    edges = _mock_edges()
    task = _mock_task()
    graph = _to_networkx_graph(resources, edges)

    finder = BeamSearchSubgraphFinder(beam_width=3, target_candidates=2)
    candidates = finder.search(task, resources, graph)

    assert candidates
    assert len(candidates[0]) >= 3
    assert nx.is_connected(graph.subgraph(candidates[0]))

    resources_by_id = {resource.id: resource for resource in resources}
    scorer = ScoreCalculator()
    scored = scorer.score_candidate(task, resources_by_id, graph, candidates[0], rank=1)
    verification = scorer.validate_top1(task, scored)

    assert 0.0 <= scored.final_score <= 100.0
    assert scored.nodes == candidates[0]
    assert verification.recommendation
