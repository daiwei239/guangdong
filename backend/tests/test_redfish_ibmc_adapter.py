import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_redfish_ibmc_adapter_fetches_systems_as_resource_state() -> None:
    from app.input.adapters.redfish_ibmc_adapter import RedfishIbmcAdapter

    responses = {
        "/redfish/v1/Systems": {
            "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
        },
        "/redfish/v1/Systems/1": {
            "Id": "1",
            "Name": "Kunpeng Node 1",
            "Manufacturer": "Huawei",
            "Model": "TaiShan 200",
            "SerialNumber": "SN-KP-0001",
            "UUID": "UUID-KP-0001",
            "HostName": "kp-node-01",
            "BiosVersion": "1.05",
            "PowerState": "On",
            "Status": {"Health": "OK", "State": "Enabled"},
            "ProcessorSummary": {"Count": 2, "Model": "Kunpeng 920"},
            "MemorySummary": {"TotalSystemMemoryGiB": 512},
        },
    }

    adapter = RedfishIbmcAdapter(
        base_url="https://ibmc.example",
        request_json=lambda path: responses[path],
        timestamp="2026-05-18T10:32:00+08:00",
        trace_id="TRACE-IBMC-0001",
    )

    state = adapter.fetch_state()

    assert state.source == "Module-2.1-ResourceInputAggregator"
    assert state.timestamp == "2026-05-18T10:32:00+08:00"
    assert state.trace_id == "TRACE-IBMC-0001"
    assert len(state.resources) == 1
    resource = state.resources[0]
    assert resource.id == "UUID-KP-0001"
    assert resource.type == "physical_server"
    assert resource.attributes["node_id"] == "UUID-KP-0001"
    assert resource.attributes["source"]["source_type"] == "ibmc_redfish"
    assert resource.attributes["hardware"]["manufacturer"] == "Huawei"
    assert resource.attributes["hardware"]["model"] == "TaiShan 200"
    assert resource.attributes["cluster_type"] == "Hybrid"
    assert resource.attributes["node_role"] == "compute"
    assert resource.attributes["cpu"]["cpu_arch"] == "ARM"
    assert resource.attributes["cpu"]["cpu_model"] == "Kunpeng 920"
    assert resource.attributes["cpu"]["cpu_total_cores"] == 0
    assert resource.attributes["memory"]["memory_total_gb"] == 512
    assert resource.attributes["accelerator"]["accelerator_type"] == "None"
    assert resource.attributes["storage"]["shared_storage_access"] is False
    assert resource.attributes["network_capability"]["network_bandwidth_gbps"] == 0
    assert resource.attributes["software"]["os_version"] == "unknown"
    assert resource.attributes["processor_summary"]["model"] == "Kunpeng 920"
    assert resource.attributes["memory_summary"]["total_system_memory_gib"] == 512
    assert resource.metrics["power_state"] == "On"
    assert resource.metrics["status"]["health"] == "OK"


def test_redfish_ibmc_adapter_uses_system_id_when_uuid_is_absent() -> None:
    from app.input.adapters.redfish_ibmc_adapter import RedfishIbmcAdapter

    responses = {
        "/redfish/v1/Systems": {"Members": [{"@odata.id": "/redfish/v1/Systems/System-1"}]},
        "/redfish/v1/Systems/System-1": {
            "Id": "System-1",
            "Name": "Fallback Node",
            "Status": {"Health": "Warning"},
        },
    }

    adapter = RedfishIbmcAdapter(
        base_url="https://ibmc.example",
        request_json=lambda path: responses[path],
    )

    state = adapter.fetch_state()

    assert state.resources[0].id == "System-1"
    assert state.resources[0].attributes["node_id"] == "System-1"
    assert state.resources[0].metrics["status"]["health"] == "Warning"


def test_redfish_ibmc_adapter_uses_redfish_absolute_paths_from_host_origin(monkeypatch) -> None:
    import app.input.adapters.redfish_ibmc_adapter as module

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    adapter = module.RedfishIbmcAdapter(base_url="https://ibmc.example/redfish/v1/")

    payload = adapter._request("/redfish/v1/Systems")

    assert payload == {"ok": True}
    assert captured["url"] == "https://ibmc.example/redfish/v1/Systems"
    assert captured["timeout"] == 10.0
    assert captured["context"] is None
