import importlib.util
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_run_pipeline_module():
    spec = importlib.util.spec_from_file_location("run_pipeline", BACKEND_ROOT / "scripts" / "run_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_schema_version_is_centralized_and_can_be_incremented_when_needed() -> None:
    from app.output.message_envelope import build_envelope
    from app.schemas.resource_schema import DEFAULT_SCHEMA_VERSION, ProcessedResourceState

    state = ProcessedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-07-03T10:30:00+08:00",
        processed_at="2026-07-03T10:30:01+08:00",
        trace_id="TRACE-R20260703-000001",
        resources=[],
        edges=[],
    )

    default_envelope = build_envelope(
        state=state,
        message_type="ResourceState",
        target_module=["Module-2.2-ResourceProcessing"],
        payload={},
        sequence=1,
    )
    bumped_envelope = build_envelope(
        state=state,
        message_type="ResourceState",
        target_module=["Module-2.2-ResourceProcessing"],
        payload={},
        sequence=1,
        schema_version="1.1",
    )

    assert DEFAULT_SCHEMA_VERSION == "1.0"
    assert default_envelope.schema_version == DEFAULT_SCHEMA_VERSION
    assert bumped_envelope.schema_version == "1.1"


def test_pipeline_outputs_three_enveloped_resource_json_files() -> None:
    run_pipeline = load_run_pipeline_module()
    temp_dir = BACKEND_ROOT / ".pytest_tmp"
    input_path = temp_dir / "ResourceInput.json"
    output_dir = temp_dir / "outputs"
    temp_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    input_path.write_text(
        json.dumps(
            {
                "source": "Module-2.1-ResourceSensing",
                "timestamp": "2026-05-18T10:32:00+08:00",
                "trace_id": "TRACE-R20260703-000001",
                "resources": [
                    {
                        "id": "cpu-1",
                        "type": "CPU",
                        "attributes": {
                            "cluster_id": "C-HYBRID-01",
                            "profile_version": "v1",
                            "cluster_type": "Hybrid",
                            "region": "DataCenter-A",
                            "node_id": "N-C01-0001",
                            "node_role": "compute",
                            "cpu": {
                                "cpu_arch": "ARM",
                                "cpu_model": "Kunpeng-920",
                                "cpu_total_cores": 64,
                                "cpu_frequency_ghz": 2.6,
                            },
                            "accelerator": {
                                "accelerator_type": "NPU",
                                "accelerator_vendor": "Huawei",
                                "accelerator_model": "Ascend-910",
                                "accelerator_total_count": 4,
                                "accelerator_slice_total": 32,
                                "accelerator_memory_total_gb": 128,
                            },
                            "memory": {"memory_total_gb": 512, "memory_bandwidth_gbps": 180},
                            "storage": {"local_storage_total_gb": 4096, "shared_storage_access": True},
                            "network_capability": {"network_bandwidth_gbps": 100},
                            "software": {
                                "os_version": "openEuler-22.03",
                                "driver_version": "CANN-8.0",
                                "runtime_stack": ["Kubernetes", "Containerd"],
                                "ai_frameworks": ["MindSpore", "PyTorch"],
                                "hpc_libraries": ["OpenMPI", "OpenBLAS"],
                                "operator_library": ["CANN"],
                            },
                            "topology": {
                                "rack_id": "RACK-A03",
                                "numa_topology": {"numa_nodes": 2, "cores_per_numa": 32},
                                "topology_neighbors": ["N-C01-0002"],
                            },
                        },
                        "metrics": {
                            "node_status": "Ready",
                            "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                            "accelerator": {
                                "accelerator_available_count": 2,
                                "accelerator_slice_available": 14,
                                "accelerator_utilization": 52.0,
                                "accelerator_temperature_celsius": 61.5,
                            },
                            "memory": {"memory_available_gb": 260},
                            "storage": {
                                "local_storage_available_gb": 1850,
                                "storage_read_bw_gbps": 12.5,
                                "storage_write_bw_gbps": 8.0,
                            },
                            "network": {"network_latency_ms": 0.35, "packet_loss_rate": 0.001},
                            "queue_state": {
                                "queue_length": 5,
                                "expected_wait_time_s": 180,
                                "reserved_resources": {"cpu_cores": 12, "npu_slices": 8, "memory_gb": 96},
                            },
                            "dynamic_state": {
                                "running_task_count": 8,
                                "load_1min": 4.7,
                                "resource_fragmentation_score": 0.28,
                                "availability_score": 0.82,
                            },
                            "energy_state": {"power_current_w": 1850, "energy_efficiency_score": 0.76},
                            "reliability_state": {"failure_rate_recent": 0.02, "maintenance_state": "normal"},
                        },
                    },
                    {
                        "id": "gpu-1",
                        "type": "GPU",
                        "attributes": {
                            "cluster_id": "C-HYBRID-01",
                            "node_id": "N-C01-0002",
                            "node_role": "compute",
                            "cpu": {
                                "cpu_arch": "x86_64",
                                "cpu_model": "Intel-Xeon",
                                "cpu_total_cores": 32,
                            },
                            "memory": {"memory_total_gb": 256},
                            "storage": {"shared_storage_access": True},
                            "network_capability": {"network_bandwidth_gbps": 100},
                            "software": {
                                "os_version": "openEuler-22.03",
                                "runtime_stack": ["Kubernetes"],
                            },
                            "topology": {"rack_id": "RACK-A03"},
                        },
                        "metrics": {
                            "node_status": "Ready",
                            "cpu": {"cpu_available_cores": 16, "cpu_utilization": 12.5},
                            "memory": {"memory_available_gb": 128},
                            "queue_state": {"queue_length": 0},
                            "dynamic_state": {"running_task_count": 1, "availability_score": 0.95},
                        },
                    },
                ],
                "edges": [
                    {
                        "edge_id": "edge-1",
                        "source": "cpu-1",
                        "target": "gpu-1",
                        "relation_type": "PCIE",
                        "bandwidth_gbps": 64,
                        "latency_ms": 0.1,
                        "weight": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8-sig",
    )

    try:
        payload = run_pipeline.run_pipeline(input_path, output_dir=output_dir)
        written = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in output_dir.glob("*.json")}
    finally:
        for path in output_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        input_path.unlink(missing_ok=True)
        output_dir.rmdir()
        temp_dir.rmdir()

    assert set(payload) == {"ResourceProfile", "ResourceState", "ResourceTopology"}
    assert set(written) == {
        "ResourceProfile-C-HYBRID-01-20260518103200.json",
        "ResourceState-C-HYBRID-01-20260518103200.json",
        "ResourceTopology-C-HYBRID-01-20260518103200.json",
    }
    assert payload["ResourceProfile"] == written["ResourceProfile-C-HYBRID-01-20260518103200.json"]
    assert payload["ResourceState"] == written["ResourceState-C-HYBRID-01-20260518103200.json"]
    assert payload["ResourceTopology"] == written["ResourceTopology-C-HYBRID-01-20260518103200.json"]

    for message_type, envelope in payload.items():
        assert envelope["schema_version"] == "1.0"
        assert envelope["message_type"] == message_type
        assert envelope["source_module"] == "Module-2.1-ResourceDescription"
        assert envelope["timestamp"] == "2026-05-18T10:32:00+08:00"
        assert envelope["trace_id"] == "TRACE-R20260703-000001"
        assert envelope["message_id"].startswith("MSG-20260518-")
        assert "payload" in envelope

    profile_payload = payload["ResourceProfile"]["payload"]
    assert profile_payload["cluster_id"] == "C-HYBRID-01"
    assert profile_payload["profile_id"] == "RP-C-HYBRID-01-v1"
    assert profile_payload["profile_version"] == "v1"
    assert profile_payload["cluster_type"] == "Hybrid"
    assert profile_payload["region"] == "DataCenter-A"
    assert profile_payload["generated_time"] == "2026-05-18T10:32:00+08:00"
    assert profile_payload["nodes"][0]["node_id"] == "N-C01-0001"
    assert profile_payload["nodes"][0]["cpu"]["cpu_model"] == "Kunpeng-920"
    assert profile_payload["nodes"][0]["cpu"]["numa_topology"] == {"numa_nodes": 2, "cores_per_numa": 32}
    assert profile_payload["nodes"][0]["software"]["runtime_stack"] == ["Kubernetes", "Containerd"]

    state_payload = payload["ResourceState"]["payload"]
    assert state_payload["cluster_id"] == "C-HYBRID-01"
    assert state_payload["snapshot_id"] == "RS-C-HYBRID-01-20260518103200"
    assert state_payload["snapshot_time"] == "2026-05-18T10:32:00+08:00"
    assert state_payload["profile_version"] == "v1"
    assert state_payload["nodes"][0]["node_id"] == "N-C01-0001"
    assert state_payload["nodes"][0]["cpu"] == {"cpu_available_cores": 40, "cpu_utilization": 37.5}
    assert state_payload["nodes"][0]["accelerator"]["accelerator_temperature"] == 61.5
    assert "accelerator_temperature_celsius" not in state_payload["nodes"][0]["accelerator"]
    assert state_payload["nodes"][0]["queue_state"]["reserved_resources"] == {"cpu_cores": 12, "npu_slices": 8, "memory_gb": 96}
    assert state_payload["nodes"][0]["energy_state"] == {"power_current_w": 1850, "energy_efficiency_score": 0.76}

    topology_payload = payload["ResourceTopology"]["payload"]
    assert topology_payload["cluster_id"] == "C-HYBRID-01"
    assert topology_payload["topology_id"] == "RT-C-HYBRID-01-v1"
    assert topology_payload["topology_version"] == "v1"
    assert topology_payload["profile_version"] == "v1"
    assert topology_payload["generated_time"] == "2026-05-18T10:32:00+08:00"
    assert topology_payload["nodes"][0]["node_id"] == "N-C01-0001"
    assert topology_payload["nodes"][0]["rack_id"] == "RACK-A03"
    assert "numa_topology" not in topology_payload["nodes"][0]
    assert topology_payload["nodes"][0]["topology_neighbors"] == ["N-C01-0002"]
    assert topology_payload["nodes"][0]["link_cost_to_nodes"] == {
        "N-C01-0002": {
            "latency_ms": 0.1,
            "bandwidth_gbps": 64,
            "interconnect_type": "PCIE",
            "cost_score": 1.0,
        }
    }


def test_process_layer_normalizes_resource_identifiers() -> None:
    from app.process.normalizer import resource_process_layer
    from app.schemas.resource_schema import RawResourceRecord, SensedResourceState

    state = SensedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            RawResourceRecord(
                id="raw-1",
                type="NPU",
                attributes={
                    "cluster_id": "bad-cluster",
                    "cluster_type": "Hybrid",
                    "node_id": "bad-node",
                    "accelerator": {"accelerator_type": "NPU", "accelerator_total_count": 2},
                },
                metrics={},
            ),
            RawResourceRecord(
                id="raw-2",
                type="CPU",
                attributes={
                    "cluster_type": "Hybrid",
                    "accelerator": {"accelerator_type": "None", "accelerator_total_count": 0},
                },
                metrics={},
            ),
        ],
        edges=[],
    )

    processed = resource_process_layer.normalize(state)

    assert processed.resources[0].attributes["cluster_id"] == "C-HYBRID-01"
    assert processed.resources[1].attributes["cluster_id"] == "C-HYBRID-01"
    assert processed.resources[0].attributes["node_id"] == "N-C01-0001"
    assert processed.resources[1].attributes["node_id"] == "N-C01-0002"
    assert processed.resources[0].attributes["accelerator"]["device_ids"] == [
        "D-N-C01-0001-NPU-0",
        "D-N-C01-0001-NPU-1",
    ]
    assert "device_ids" not in processed.resources[1].attributes["accelerator"]


def test_payload_models_validate_required_fields_and_allow_realtime_extensions() -> None:
    from pydantic import ValidationError

    from app.schemas.resource_schema import ResourceProfilePayload, ResourceStatePayload, ResourceTopologyPayload

    profile = ResourceProfilePayload.model_validate(
        {
            "cluster_id": "C-HYBRID-01",
            "profile_id": "RP-C-HYBRID-01-v1",
            "profile_version": "v1",
            "cluster_type": "Hybrid",
            "nodes": [
                {
                    "node_id": "N-C01-0001",
                    "node_role": "compute",
                    "cpu": {"cpu_arch": "ARM", "cpu_model": "Kunpeng-920", "cpu_total_cores": 64},
                    "accelerator": {"accelerator_type": "NPU", "vendor_health_score": 0.98},
                    "memory": {"memory_total_gb": 512},
                    "storage": {"shared_storage_access": True},
                    "network_capability": {"network_bandwidth_gbps": 100},
                    "software": {"os_version": "openEuler-22.03", "runtime_stack": ["Kubernetes"]},
                }
            ],
        }
    )
    assert profile.nodes[0].accelerator.model_extra["vendor_health_score"] == 0.98

    state = ResourceStatePayload.model_validate(
        {
            "cluster_id": "C-HYBRID-01",
            "snapshot_id": "RS-C-HYBRID-01-20260518103200",
            "snapshot_time": "2026-05-18T10:32:00+08:00",
            "profile_version": "v1",
            "nodes": [
                {
                    "node_id": "N-C01-0001",
                    "node_status": "Ready",
                    "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                    "memory": {"memory_available_gb": 260},
                    "queue_state": {"queue_length": 5},
                    "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                }
            ],
        }
    )
    assert state.nodes[0].cpu.cpu_utilization == 37.5

    topology = ResourceTopologyPayload.model_validate(
        {
            "cluster_id": "C-HYBRID-01",
            "topology_id": "RT-C-HYBRID-01-v1",
            "topology_version": "v1",
            "profile_version": "v1",
            "nodes": [
                {
                    "node_id": "N-C01-0001",
                    "link_cost_to_nodes": {
                        "N-C01-0002": {
                            "latency_ms": 0.1,
                            "bandwidth_gbps": 64,
                            "interconnect_type": "PCIE",
                        }
                    },
                }
            ],
        }
    )
    assert topology.nodes[0].link_cost_to_nodes["N-C01-0002"].bandwidth_gbps == 64

    try:
        ResourceStatePayload.model_validate(
            {
                "cluster_id": "C-HYBRID-01",
                "snapshot_id": "RS-C-HYBRID-01-20260518103200",
                "snapshot_time": "2026-05-18T10:32:00+08:00",
                "profile_version": "v1",
                "nodes": [
                    {
                        "node_id": "N-C01-0001",
                        "node_status": "Ready",
                        "cpu": {"cpu_available_cores": 40},
                        "memory": {"memory_available_gb": 260},
                        "queue_state": {"queue_length": 5},
                        "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                    }
                ],
            }
        )
    except ValidationError as exc:
        assert "cpu_utilization" in str(exc)
    else:
        raise AssertionError("ResourceStatePayload should reject missing required CPU utilization")


def test_resource_state_rejects_missing_required_fields() -> None:
    from app.output.resource_state import resource_state_output
    from app.schemas.resource_schema import ProcessedResourceRecord, ProcessedResourceState

    state = ProcessedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        processed_at="2026-05-18T10:32:01+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            ProcessedResourceRecord(
                id="cpu-1",
                type="CPU",
                attributes={"cluster_id": "C-HYBRID-01", "node_id": "N-C01-0001"},
                metrics={
                    "node_status": "Ready",
                    "cpu": {"cpu_available_cores": 40},
                    "memory": {},
                    "queue_state": {},
                    "dynamic_state": {"running_task_count": 8},
                },
                normalized_metrics={},
            )
        ],
        edges=[],
    )

    try:
        resource_state_output.build(state)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("ResourceState validation should reject missing required fields")

    assert "payload.nodes[0].cpu.cpu_utilization" in message
    assert "payload.nodes[0].memory.memory_available_gb" in message
    assert "payload.nodes[0].queue_state.queue_length" in message
    assert "payload.nodes[0].dynamic_state.availability_score" in message


def test_resource_profile_rejects_missing_required_fields() -> None:
    from app.output.resource_profile import resource_profile_output
    from app.schemas.resource_schema import ProcessedResourceRecord, ProcessedResourceState

    state = ProcessedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        processed_at="2026-05-18T10:32:01+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            ProcessedResourceRecord(
                id="cpu-1",
                type="CPU",
                attributes={
                    "cluster_id": "C-HYBRID-01",
                    "node_id": "N-C01-0001",
                    "node_role": "compute",
                    "cpu": {"cpu_arch": "ARM"},
                    "accelerator": {"accelerator_type": "NPU"},
                    "memory": {},
                    "storage": {},
                    "network_capability": {},
                    "software": {},
                },
                metrics={},
                normalized_metrics={},
            )
        ],
        edges=[],
    )

    try:
        resource_profile_output.build(state)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("ResourceProfile validation should reject missing required fields")

    assert "payload.cluster_type" in message
    assert "payload.nodes[0].cpu.cpu_model" in message
    assert "payload.nodes[0].cpu.cpu_total_cores" in message
    assert "payload.nodes[0].accelerator.accelerator_available_count" not in message
    assert "payload.nodes[0].accelerator.accelerator_vendor" in message
    assert "payload.nodes[0].memory.memory_total_gb" in message
    assert "payload.nodes[0].storage.shared_storage_access" in message
    assert "payload.nodes[0].network_capability.network_bandwidth_gbps" in message
    assert "payload.nodes[0].software.os_version" in message
    assert "payload.nodes[0].software.runtime_stack" in message


def test_resource_state_rejects_missing_conditional_fields() -> None:
    from app.output.resource_state import resource_state_output
    from app.schemas.resource_schema import ProcessedResourceRecord, ProcessedResourceState

    state = ProcessedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        processed_at="2026-05-18T10:32:01+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            ProcessedResourceRecord(
                id="npu-1",
                type="NPU",
                attributes={"cluster_id": "C-HYBRID-01", "node_id": "N-C01-0001"},
                metrics={
                    "node_status": "Ready",
                    "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                    "accelerator": {"accelerator_utilization": 52.0},
                    "memory": {"memory_available_gb": 260},
                    "queue_state": {"queue_length": 5, "reserved_resources": {"cpu_cores": 12}},
                    "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                },
                normalized_metrics={},
            )
        ],
        edges=[],
    )

    try:
        resource_state_output.build(state)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("ResourceState validation should reject missing conditional fields")

    assert "payload.nodes[0].accelerator.accelerator_available_count" in message
    assert "payload.nodes[0].queue_state.reserved_resources.npu_slices" in message
    assert "payload.nodes[0].queue_state.reserved_resources.memory_gb" in message


def test_resource_topology_rejects_missing_conditional_fields() -> None:
    from app.output.resource_topology import resource_topology_output
    from app.schemas.resource_schema import ProcessedResourceRecord, ProcessedResourceState, RawTopologyEdge

    state = ProcessedResourceState(
        source="Module-2.1-ResourceSensing",
        timestamp="2026-05-18T10:32:00+08:00",
        processed_at="2026-05-18T10:32:01+08:00",
        trace_id="TRACE-R20260518-000001",
        resources=[
            ProcessedResourceRecord(
                id="cpu-1",
                type="CPU",
                attributes={
                    "cluster_id": "C-HYBRID-01",
                    "node_id": "N-C01-0001",
                    "topology": {},
                },
                metrics={},
                normalized_metrics={},
            ),
            ProcessedResourceRecord(
                id="gpu-1",
                type="GPU",
                attributes={"cluster_id": "C-HYBRID-01", "node_id": "N-C01-0002"},
                metrics={},
                normalized_metrics={},
            ),
        ],
        edges=[RawTopologyEdge(edge_id="edge-1", source="cpu-1", target="gpu-1", relation_type="PCIE")],
    )

    try:
        resource_topology_output.build(state)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("ResourceTopology validation should reject missing conditional fields")

    assert "payload.nodes[0].link_cost_to_nodes.N-C01-0002.latency_ms" in message
    assert "payload.nodes[0].link_cost_to_nodes.N-C01-0002.bandwidth_gbps" in message
