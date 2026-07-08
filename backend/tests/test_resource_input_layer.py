import json
import shutil
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_input_layer_aggregates_grouped_realtime_sources() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_input_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "ResourceSources.json"
    input_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-18T10:32:00+08:00",
                "trace_id": "TRACE-R20260518-000001",
                "sources": {
                    "management_config": {
                        "source_name": "ClusterManager",
                        "nodes": [
                            {
                                "node_id": "N-C01-0001",
                                "attributes": {
                                    "cluster_id": "C-HYBRID-01",
                                    "cluster_type": "Hybrid",
                                    "node_role": "compute",
                                    "storage": {"shared_storage_access": True},
                                    "network_capability": {"network_bandwidth_gbps": 100},
                                    "software": {"runtime_stack": ["Kubernetes"]},
                                },
                            }
                        ],
                    },
                    "agent_collect": {
                        "source_name": "NodeAgent",
                        "nodes": [
                            {
                                "node_id": "N-C01-0001",
                                "resource_type": "NPU",
                                "attributes": {
                                    "cpu": {
                                        "cpu_arch": "ARM",
                                        "cpu_model": "Kunpeng-920",
                                        "cpu_total_cores": 64,
                                    },
                                    "accelerator": {
                                        "accelerator_type": "NPU",
                                        "accelerator_total_count": 2,
                                    },
                                    "memory": {"memory_total_gb": 512},
                                    "software": {"os_version": "openEuler-22.03"},
                                },
                            }
                        ],
                    },
                    "realtime_monitor": {
                        "source_name": "Prometheus",
                        "nodes": [
                            {
                                "node_id": "N-C01-0001",
                                "metrics": {
                                    "node_status": "Ready",
                                    "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                                    "memory": {"memory_available_gb": 260},
                                    "queue_state": {"queue_length": 5},
                                    "dynamic_state": {
                                        "running_task_count": 8,
                                        "availability_score": 0.82,
                                    },
                                },
                            }
                        ],
                    },
                    "topology_probe": {
                        "source_name": "TopologyProbe",
                        "nodes": [
                            {
                                "node_id": "N-C01-0001",
                                "topology": {"rack_id": "RACK-A03", "topology_neighbors": ["N-C01-0002"]},
                            }
                        ],
                        "edges": [
                            {
                                "edge_id": "edge-1",
                                "source": "N-C01-0001",
                                "target": "N-C01-0002",
                                "relation_type": "RoCE",
                                "bandwidth_gbps": 100,
                                "latency_ms": 0.3,
                                "weight": 0.12,
                            }
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        state = resource_input_layer.read_resource_state(input_path)
    finally:
        input_path.unlink(missing_ok=True)
        temp_dir.rmdir()

    assert state.source == "Module-2.1-ResourceInputAggregator"
    assert state.timestamp == "2026-05-18T10:32:00+08:00"
    assert state.trace_id == "TRACE-R20260518-000001"
    assert len(state.resources) == 1
    resource = state.resources[0]
    assert resource.id == "N-C01-0001"
    assert resource.type == "NPU"
    assert resource.attributes["cluster_id"] == "C-HYBRID-01"
    assert resource.attributes["cpu"]["cpu_model"] == "Kunpeng-920"
    assert resource.attributes["software"] == {
        "runtime_stack": ["Kubernetes"],
        "os_version": "openEuler-22.03",
    }
    assert resource.attributes["topology"]["rack_id"] == "RACK-A03"
    assert resource.metrics["cpu"]["cpu_utilization"] == 37.5
    assert len(state.edges) == 1
    assert state.edges[0].source == "N-C01-0001"


def test_input_layer_aggregates_flat_resource_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_input_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "ResourceEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "agent_collect",
                        "source_name": "NodeAgent",
                        "timestamp": "2026-05-18T10:31:59+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "resource_type": "CPU",
                        "attributes": {
                            "cluster_type": "Hybrid",
                            "cpu": {
                                "cpu_arch": "ARM",
                                "cpu_model": "Kunpeng-920",
                                "cpu_total_cores": 64,
                            },
                            "accelerator": {"accelerator_type": "None"},
                            "memory": {"memory_total_gb": 512},
                            "storage": {"shared_storage_access": True},
                            "network_capability": {"network_bandwidth_gbps": 100},
                            "software": {"os_version": "openEuler-22.03", "runtime_stack": ["Kubernetes"]},
                            "node_role": "compute",
                        },
                    },
                    {
                        "source_type": "realtime_monitor",
                        "source_name": "Prometheus",
                        "timestamp": "2026-05-18T10:32:00+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "metrics": {
                            "node_status": "Ready",
                            "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                            "memory": {"memory_available_gb": 260},
                            "queue_state": {"queue_length": 5},
                            "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        state = resource_input_layer.read_resource_state(input_path)
    finally:
        input_path.unlink(missing_ok=True)
        temp_dir.rmdir()

    assert len(state.resources) == 1
    assert state.resources[0].attributes["cpu"]["cpu_total_cores"] == 64
    assert state.resources[0].metrics["dynamic_state"]["availability_score"] == 0.82


def test_input_layer_rejects_invalid_cluster_type_in_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_invalid_cluster_type_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "InvalidClusterTypeEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "agent_collect",
                        "source_name": "NodeAgent",
                        "timestamp": "2026-05-18T10:31:59+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "resource_type": "CPU",
                        "attributes": {
                            "cluster_type": "invalid",
                            "node_role": "compute",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(ValueError, match="cluster_type"):
            resource_input_layer.read_resource_state(input_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_input_layer_rejects_invalid_node_role_in_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_invalid_node_role_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "InvalidNodeRoleEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "agent_collect",
                        "source_name": "NodeAgent",
                        "timestamp": "2026-05-18T10:31:59+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "resource_type": "CPU",
                        "attributes": {
                            "cluster_type": "Hybrid",
                            "node_role": "invalid",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(ValueError, match="node_role"):
            resource_input_layer.read_resource_state(input_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_input_layer_rejects_invalid_node_status_in_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_invalid_node_status_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "InvalidNodeStatusEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "realtime_monitor",
                        "source_name": "Prometheus",
                        "timestamp": "2026-05-18T10:32:00+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "metrics": {
                            "node_status": "invalid",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(ValueError, match="node_status"):
            resource_input_layer.read_resource_state(input_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_input_layer_rejects_invalid_accelerator_type_in_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_invalid_accelerator_type_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "InvalidAcceleratorTypeEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "agent_collect",
                        "source_name": "NodeAgent",
                        "timestamp": "2026-05-18T10:31:59+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "resource_type": "CPU",
                        "attributes": {
                            "cluster_type": "Hybrid",
                            "node_role": "compute",
                            "accelerator": {
                                "accelerator_type": "invalid",
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(ValueError, match="accelerator_type"):
            resource_input_layer.read_resource_state(input_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_input_layer_rejects_invalid_maintenance_state_in_events() -> None:
    from app.input.resource_input import resource_input_layer

    temp_dir = BACKEND_ROOT / ".pytest_invalid_maintenance_state_tmp"
    temp_dir.mkdir(exist_ok=True)
    input_path = temp_dir / "InvalidMaintenanceStateEvents.json"
    input_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source_type": "realtime_monitor",
                        "source_name": "Prometheus",
                        "timestamp": "2026-05-18T10:32:00+08:00",
                        "trace_id": "TRACE-R20260518-000001",
                        "node_id": "N-C01-0001",
                        "metrics": {
                            "node_status": "Ready",
                            "reliability_state": {
                                "maintenance_state": "invalid",
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(ValueError, match="maintenance_state"):
            resource_input_layer.read_resource_state(input_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
