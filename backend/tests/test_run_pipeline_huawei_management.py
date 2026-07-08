import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_build_huawei_management_adapter_from_config(monkeypatch) -> None:
    from scripts import run_pipeline

    captured = {}

    class FakeFusionDirectorAdapter:
        def __init__(self, **kwargs) -> None:
            captured.setdefault("adapters", []).append(("fusiondirector", kwargs))

        def fetch_events(self):
            return []

    class FakeJsonAdapter:
        def __init__(self, **kwargs) -> None:
            captured.setdefault("adapters", []).append(("json", kwargs))

        def fetch_events(self):
            return []

    class FakeManagementAdapter:
        def __init__(self, adapters, timestamp=None, trace_id=None) -> None:
            captured["management"] = {
                "adapter_count": len(list(adapters)),
                "timestamp": timestamp,
                "trace_id": trace_id,
            }

    monkeypatch.setattr(run_pipeline, "FusionDirectorAdapter", FakeFusionDirectorAdapter)
    monkeypatch.setattr(run_pipeline, "JsonPlatformAdapter", FakeJsonAdapter)
    monkeypatch.setattr(run_pipeline, "HuaweiManagementInputAdapter", FakeManagementAdapter)

    adapter = run_pipeline.build_huawei_management_adapter(
        {
            "timestamp": "2026-05-18T10:32:00+08:00",
            "trace_id": "TRACE-HUAWEI-0001",
            "platforms": [
                {
                    "source_type": "fusiondirector",
                    "source_name": "fusiondirector.example",
                    "base_url": "https://fusiondirector.example",
                    "path": "/api/resource-events",
                    "bearer_token": "token-a",
                },
                {
                    "source_type": "mindx",
                    "source_name": "mindx.example",
                    "file_path": "examples/mindx_payload.json",
                },
            ],
        }
    )

    assert isinstance(adapter, FakeManagementAdapter)
    assert captured["management"] == {
        "adapter_count": 2,
        "timestamp": "2026-05-18T10:32:00+08:00",
        "trace_id": "TRACE-HUAWEI-0001",
    }
    assert captured["adapters"][0][0] == "fusiondirector"
    assert captured["adapters"][0][1]["bearer_token"] == "token-a"
    assert captured["adapters"][1][1]["source_type"] == "mindx"
    assert captured["adapters"][1][1]["file_path"] == "examples/mindx_payload.json"


def test_run_pipeline_from_huawei_management_config_uses_combined_adapter(monkeypatch) -> None:
    import json

    from app.schemas.resource_schema import SensedResourceState
    from scripts import run_pipeline

    payload_path = BACKEND_ROOT / ".pytest_mindx_payload.json"
    config_path = BACKEND_ROOT / ".pytest_huawei_management_config.json"
    payload_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    config_path.write_text(
        json.dumps({"platforms": [{"source_type": "mindx", "file_path": payload_path.name}]}),
        encoding="utf-8",
    )
    sensed_state = SensedResourceState(
        source="huawei-test",
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-HUAWEI-0001",
        resources=[],
        edges=[],
    )
    captured = {}

    class FakeAdapter:
        def fetch_state(self):
            captured["fetch_called"] = True
            return sensed_state

    def fake_build_huawei_management_adapter(config):
        captured["config"] = config
        return FakeAdapter()

    monkeypatch.setattr(run_pipeline, "build_huawei_management_adapter", fake_build_huawei_management_adapter)
    monkeypatch.setattr(
        run_pipeline,
        "run_pipeline_from_state",
        lambda state, output_dir=None: {"state_source": state.source, "output_dir": str(output_dir)},
    )

    try:
        result = run_pipeline.run_pipeline_from_huawei_management(config_path, output_dir=Path("out"))
    finally:
        config_path.unlink(missing_ok=True)
        payload_path.unlink(missing_ok=True)

    assert captured["fetch_called"] is True
    assert captured["config"]["platforms"][0]["file_path"] == str(payload_path)
    assert result == {"state_source": "huawei-test", "output_dir": "out"}


def test_local_huawei_management_example_reads_supported_sources() -> None:
    from scripts.run_pipeline import run_pipeline_from_huawei_management

    payload = run_pipeline_from_huawei_management(BACKEND_ROOT / "examples" / "huawei_management_local_config.example.json")

    profile_node = payload["ResourceProfile"]["payload"]["nodes"][0]
    state_node = payload["ResourceState"]["payload"]["nodes"][0]
    topology_node = payload["ResourceTopology"]["payload"]["nodes"][0]

    assert profile_node["cpu"]["cpu_model"] == "Kunpeng 920"
    assert profile_node["accelerator"]["accelerator_model"] == "Ascend 910"
    assert profile_node["software"]["runtime_stack"] == ["Slurm"]
    assert state_node["cpu"]["cpu_utilization"] == 25.5
    assert state_node["queue_state"]["queue_length"] == 3
    assert topology_node["rack_id"] == "rack-a01"