import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_process_layer_standardizes_fields_and_units() -> None:
    from app.process.normalizer import resource_process_layer
    from app.schemas.resource_schema import RawResourceRecord, SensedResourceState

    state = SensedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            RawResourceRecord(
                id="raw-1",
                type="CPU",
                attributes={
                    "cluster_type": "Hybrid",
                    "node_role": "compute",
                    "cpu": {
                        "arch": "ARM",
                        "model": "Kunpeng-920",
                        "total_cores": 64,
                    },
                    "accelerator": {"type": "None"},
                    "memory": {"memory_total_mb": 524288},
                    "storage": {"shared_storage_access": True},
                    "network_capability": {"network_bandwidth_mbps": 100000},
                    "software": {"os_version": "openEuler-22.03", "runtime_stack": ["Kubernetes"]},
                },
                metrics={
                    "node_status": "Ready",
                    "cpu": {"available_cores": 40, "cpu_utilization_ratio": 0.375},
                    "memory": {"memory_available_mb": 266240},
                    "queue_state": {"queue_length": 5},
                    "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                },
            )
        ],
        edges=[],
    )

    processed = resource_process_layer.normalize(state)
    resource = processed.resources[0]

    assert resource.attributes["cpu"]["cpu_arch"] == "ARM"
    assert resource.attributes["cpu"]["cpu_model"] == "Kunpeng-920"
    assert resource.attributes["cpu"]["cpu_total_cores"] == 64
    assert resource.attributes["accelerator"]["accelerator_type"] == "None"
    assert resource.attributes["memory"]["memory_total_gb"] == 512
    assert resource.attributes["network_capability"]["network_bandwidth_gbps"] == 100
    assert resource.metrics["cpu"]["cpu_available_cores"] == 40
    assert resource.metrics["cpu"]["cpu_utilization"] == 37.5
    assert resource.metrics["memory"]["memory_available_gb"] == 260


def test_process_layer_clamps_realtime_quality_ranges_and_leaves_topology_weight_empty() -> None:
    from app.process.normalizer import resource_process_layer
    from app.schemas.resource_schema import RawResourceRecord, RawTopologyEdge, SensedResourceState

    state = SensedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            RawResourceRecord(
                id="N-C01-0001",
                type="CPU",
                attributes={
                    "cluster_type": "Hybrid",
                    "node_id": "N-C01-0001",
                    "node_role": "compute",
                    "cpu": {"cpu_arch": "ARM", "cpu_model": "Kunpeng-920", "cpu_total_cores": 64},
                    "accelerator": {"accelerator_type": "None"},
                    "memory": {"memory_total_gb": 512},
                    "storage": {"shared_storage_access": True},
                    "network_capability": {"network_bandwidth_gbps": 100},
                    "software": {"os_version": "openEuler-22.03", "runtime_stack": ["Kubernetes"]},
                },
                metrics={
                    "node_status": "Ready",
                    "cpu": {"cpu_available_cores": -4, "cpu_utilization": 135},
                    "memory": {"memory_available_gb": -1},
                    "queue_state": {"queue_length": -3},
                    "dynamic_state": {"running_task_count": -8, "availability_score": 1.2},
                    "accelerator": {"accelerator_utilization": -2, "accelerator_temperature": -10},
                },
            )
        ],
        edges=[
            RawTopologyEdge(
                edge_id="edge-1",
                source="N-C01-0001",
                target="N-C01-0002",
                relation_type="RoCE",
                bandwidth_gbps=100,
                latency_ms=0.3,
                weight=None,
            )
        ],
    )

    processed = resource_process_layer.normalize(state)
    resource = processed.resources[0]

    assert resource.metrics["cpu"]["cpu_available_cores"] == 0
    assert resource.metrics["cpu"]["cpu_utilization"] == 100
    assert resource.metrics["memory"]["memory_available_gb"] == 0
    assert resource.metrics["queue_state"]["queue_length"] == 0
    assert resource.metrics["dynamic_state"]["running_task_count"] == 0
    assert resource.metrics["dynamic_state"]["availability_score"] == 1
    assert resource.metrics["accelerator"]["accelerator_utilization"] == 0
    assert resource.metrics["accelerator"]["accelerator_temperature"] == 0
    assert processed.edges[0].weight is None
