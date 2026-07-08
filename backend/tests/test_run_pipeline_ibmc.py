import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_run_pipeline_from_ibmc_uses_redfish_adapter(monkeypatch) -> None:
    from app.schemas.resource_schema import SensedResourceState
    from scripts import run_pipeline

    sensed_state = SensedResourceState(
        source="ibmc-test",
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-IBMC-0001",
        resources=[],
        edges=[],
    )
    captured = {}

    class FakeAdapter:
        def __init__(self, **kwargs) -> None:
            captured["adapter_kwargs"] = kwargs

        def fetch_state(self) -> SensedResourceState:
            captured["fetch_called"] = True
            return sensed_state

    def fake_run_pipeline_from_state(state, output_dir=None):
        captured["state"] = state
        captured["output_dir"] = output_dir
        return {"ok": True}

    monkeypatch.setattr(run_pipeline, "RedfishIbmcAdapter", FakeAdapter)
    monkeypatch.setattr(run_pipeline, "run_pipeline_from_state", fake_run_pipeline_from_state)

    result = run_pipeline.run_pipeline_from_ibmc(
        base_url="https://ibmc.example",
        username="admin",
        password="secret",
        verify_tls=False,
        output_dir=Path("out"),
    )

    assert result == {"ok": True}
    assert captured["adapter_kwargs"] == {
        "base_url": "https://ibmc.example",
        "username": "admin",
        "password": "secret",
        "verify_tls": False,
    }
    assert captured["fetch_called"] is True
    assert captured["state"] is sensed_state
    assert captured["output_dir"] == Path("out")


def test_redfish_ibmc_state_runs_through_pipeline_outputs() -> None:
    from app.input.adapters.redfish_ibmc_adapter import RedfishIbmcAdapter
    from scripts.run_pipeline import run_pipeline_from_state

    responses = {
        "/redfish/v1/Systems": {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]},
        "/redfish/v1/Systems/1": {
            "Id": "1",
            "UUID": "UUID-KP-0001",
            "Manufacturer": "Huawei",
            "Model": "TaiShan 200",
            "ProcessorSummary": {"Model": "Kunpeng 920", "TotalCores": 64},
            "MemorySummary": {"TotalSystemMemoryGiB": 512},
            "PowerState": "On",
            "Status": {"Health": "OK", "State": "Enabled"},
        },
    }

    state = RedfishIbmcAdapter(
        base_url="https://ibmc.example/redfish/v1/",
        request_json=lambda path: responses[path],
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-IBMC-0001",
    ).fetch_state()

    payload = run_pipeline_from_state(state)

    assert sorted(payload) == ["ResourceProfile", "ResourceState", "ResourceTopology"]
    assert payload["ResourceProfile"]["payload"]["nodes"][0]["cpu"]["cpu_total_cores"] == 64
    assert payload["ResourceState"]["payload"]["nodes"][0]["cpu"]["cpu_available_cores"] == 64
