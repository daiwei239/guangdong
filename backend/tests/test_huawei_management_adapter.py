import sys
import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_json_platform_adapter_converts_grouped_sources_to_events() -> None:
    from app.input.adapters.huawei_management_adapter import JsonPlatformAdapter

    payload = {
        "timestamp": "2026-05-18T10:32:00+08:00",
        "trace_id": "TRACE-HUAWEI-0001",
        "sources": {
            "fusiondirector": {
                "source_name": "fusiondirector.example",
                "nodes": [
                    {
                        "node_id": "UUID-KP-0001",
                        "resource_id": "UUID-KP-0001",
                        "attributes": {
                            "cluster_id": "cluster-a",
                            "cluster_type": "Hybrid",
                            "region": "shenzhen-a",
                            "node_role": "compute",
                            "network_capability": {
                                "network_bandwidth_gbps": 100,
                                "interconnect_type": "RoCE",
                            },
                            "storage": {"shared_storage_access": True},
                        },
                    }
                ],
            }
        },
    }

    adapter = JsonPlatformAdapter(
        source_type="fusiondirector",
        source_name="fusiondirector.example",
        request_json=lambda path: payload,
    )

    events = adapter.fetch_events()

    assert len(events) == 1
    assert events[0].source_type == "fusiondirector"
    assert events[0].node_id == "UUID-KP-0001"
    assert events[0].attributes["cluster_id"] == "cluster-a"
    assert events[0].attributes["network_capability"]["interconnect_type"] == "RoCE"


def test_json_platform_adapter_reads_payload_from_local_file() -> None:
    from app.input.adapters.huawei_management_adapter import JsonPlatformAdapter

    payload_path = BACKEND_ROOT / ".pytest_platform_payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "node_id": "UUID-KP-0001",
                        "resource_id": "UUID-KP-0001",
                        "attributes": {"cluster_id": "cluster-a"},
                        "metrics": {"queue_state": {"queue_length": 4}},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        adapter = JsonPlatformAdapter(
            source_type="scheduler_queue",
            source_name="local-scheduler",
            file_path=payload_path,
        )

        events = adapter.fetch_events()
    finally:
        payload_path.unlink(missing_ok=True)

    assert len(events) == 1
    assert events[0].source_type == "scheduler_queue"
    assert events[0].attributes["cluster_id"] == "cluster-a"
    assert events[0].metrics["queue_state"]["queue_length"] == 4


def test_fusiondirector_adapter_defaults_to_fusiondirector_source() -> None:
    from app.input.adapters.huawei_management_adapter import FusionDirectorAdapter

    payload = {
        "nodes": [
            {
                "node_id": "N-C01-0001",
                "resource_id": "N-C01-0001",
                "attributes": {
                    "cluster_id": "cluster-shenzhen-a",
                    "cluster_type": "Hybrid",
                    "region": "shenzhen-a",
                    "node_role": "compute",
                    "network_capability": {"network_bandwidth_gbps": 100},
                    "storage": {"shared_storage_access": True},
                },
            }
        ]
    }

    adapter = FusionDirectorAdapter(
        source_name="fusiondirector.example",
        request_json=lambda path: payload,
    )

    events = adapter.fetch_events()

    assert len(events) == 1
    assert events[0].source_type == "fusiondirector"
    assert events[0].source_name == "fusiondirector.example"
    assert events[0].node_id == "N-C01-0001"
    assert events[0].attributes["cluster_id"] == "cluster-shenzhen-a"


def test_huawei_management_adapter_merges_fusiondirector_and_mindx_sources() -> None:
    from app.input.adapters.huawei_management_adapter import HuaweiManagementInputAdapter, JsonPlatformAdapter

    fusiondirector_payload = {
        "sources": {
            "fusiondirector": {
                "source_name": "fusiondirector.example",
                "nodes": [
                    {
                        "node_id": "UUID-KP-0001",
                        "resource_id": "UUID-KP-0001",
                        "attributes": {
                            "cluster_id": "cluster-a",
                            "cluster_type": "Hybrid",
                            "region": "shenzhen-a",
                            "node_role": "compute",
                            "network_capability": {
                                "network_bandwidth_gbps": 100,
                                "interconnect_type": "RoCE",
                            },
                            "storage": {"shared_storage_access": True},
                            "software": {
                                "os_version": "openEuler-22.03",
                                "runtime_stack": ["Kubernetes", "MindX DL"],
                            },
                        },
                    }
                ],
            }
        }
    }
    mindx_payload = {
        "sources": {
            "mindx": {
                "source_name": "mindx.example",
                "nodes": [
                    {
                        "node_id": "UUID-KP-0001",
                        "resource_id": "UUID-KP-0001",
                        "attributes": {
                            "accelerator": {
                                "accelerator_type": "NPU",
                                "accelerator_vendor": "Huawei",
                                "accelerator_model": "Ascend 910",
                                "accelerator_total_count": 8,
                                "accelerator_memory_total_gb": 256,
                            }
                        },
                        "metrics": {
                            "accelerator": {
                                "accelerator_available_count": 6,
                                "accelerator_utilization": 73.5,
                            },
                            "queue_state": {"queue_length": 3, "expected_wait_time_s": 90},
                            "dynamic_state": {
                                "running_task_count": 5,
                                "availability_score": 0.82,
                            },
                        },
                    }
                ],
            }
        }
    }

    adapter = HuaweiManagementInputAdapter(
        adapters=[
            JsonPlatformAdapter(
                source_type="fusiondirector",
                source_name="fusiondirector.example",
                request_json=lambda path: fusiondirector_payload,
            ),
            JsonPlatformAdapter(
                source_type="mindx",
                source_name="mindx.example",
                request_json=lambda path: mindx_payload,
            ),
        ]
    )

    state = adapter.fetch_state()

    assert len(state.resources) == 1
    resource = state.resources[0]
    assert resource.id == "UUID-KP-0001"
    assert resource.attributes["cluster_id"] == "cluster-a"
    assert resource.attributes["network_capability"]["network_bandwidth_gbps"] == 100
    assert resource.attributes["software"]["runtime_stack"] == ["Kubernetes", "MindX DL"]
    assert resource.attributes["accelerator"]["accelerator_type"] == "NPU"
    assert resource.metrics["queue_state"]["queue_length"] == 3
    assert resource.metrics["accelerator"]["accelerator_available_count"] == 6
    assert resource.metrics["dynamic_state"]["running_task_count"] == 5
