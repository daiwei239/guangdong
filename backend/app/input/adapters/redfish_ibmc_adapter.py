import base64
import json
import ssl
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.input.resource_event import ResourceEvent
from app.input.state_aggregator import StateAggregator
from app.schemas.resource_schema import SensedResourceState


REDFISH_IBMC_SOURCE_TYPE = "ibmc_redfish"
REDFISH_SYSTEMS_PATH = "/redfish/v1/Systems"


class RedfishIbmcAdapter:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        verify_tls: bool = True,
        timeout_seconds: float = 10.0,
        request_json: Callable[[str], dict[str, Any]] | None = None,
        timestamp: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout_seconds = timeout_seconds
        self.request_json = request_json
        self.timestamp = timestamp
        self.trace_id = trace_id
        self.source_name = urlparse(self.base_url).netloc or self.base_url.rstrip("/")

    def fetch_state(self) -> SensedResourceState:
        aggregator = StateAggregator(timestamp=self.timestamp, trace_id=self.trace_id)
        for event in self.fetch_events():
            aggregator.ingest(event)
        return aggregator.build_state()

    def fetch_events(self) -> list[ResourceEvent]:
        systems = self._request(REDFISH_SYSTEMS_PATH)
        events: list[ResourceEvent] = []
        for member in systems.get("Members", []):
            member_path = member.get("@odata.id")
            if not member_path:
                continue
            events.append(self._event_from_system(self._request(member_path)))
        return events

    def _request(self, path: str) -> dict[str, Any]:
        if self.request_json is not None:
            return self.request_json(path)

        url = self._url_for_path(path)
        request = Request(url, headers={"Accept": "application/json"})
        if self.username is not None and self.password is not None:
            token = f"{self.username}:{self.password}".encode("utf-8")
            request.add_header("Authorization", f"Basic {base64.b64encode(token).decode('ascii')}")

        context = None
        if url.startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()

        with urlopen(request, timeout=self.timeout_seconds, context=context) as response:
            return json.loads(response.read().decode("utf-8"))

    def _url_for_path(self, path: str) -> str:
        if path.startswith("/"):
            parsed = urlparse(self.base_url)
            origin = f"{parsed.scheme}://{parsed.netloc}/"
            return urljoin(origin, path.lstrip("/"))
        return urljoin(self.base_url, path)

    def _event_from_system(self, system: dict[str, Any]) -> ResourceEvent:
        node_id = self._system_identifier(system)
        status = system.get("Status") if isinstance(system.get("Status"), dict) else {}

        attributes = {
            "cluster_type": "Hybrid",
            "node_role": "compute",
            "source": {
                "source_type": REDFISH_IBMC_SOURCE_TYPE,
                "source_name": self.source_name,
                "redfish_id": system.get("@odata.id"),
            },
            "hardware": {
                "name": system.get("Name"),
                "manufacturer": system.get("Manufacturer"),
                "model": system.get("Model"),
                "serial_number": system.get("SerialNumber"),
                "uuid": system.get("UUID"),
                "sku": system.get("SKU"),
                "part_number": system.get("PartNumber"),
                "bios_version": system.get("BiosVersion"),
                "host_name": system.get("HostName"),
            },
            "cpu": {
                "cpu_arch": "ARM",
                "cpu_model": self._cpu_model(system.get("ProcessorSummary")),
                "cpu_total_cores": self._cpu_total_cores(system.get("ProcessorSummary")),
            },
            "accelerator": {"accelerator_type": "None"},
            "memory": {
                "memory_total_gb": self._memory_total_gb(system.get("MemorySummary")),
            },
            "storage": {"shared_storage_access": False},
            "network_capability": {"network_bandwidth_gbps": 0},
            "software": {"os_version": "unknown", "runtime_stack": []},
            "processor_summary": self._processor_summary(system.get("ProcessorSummary")),
            "memory_summary": self._memory_summary(system.get("MemorySummary")),
        }

        metrics = {
            "node_status": self._node_status(system),
            "cpu": {
                "cpu_available_cores": self._available_cpu_cores(system),
                "cpu_utilization": 0,
            },
            "memory": {
                "memory_available_gb": self._memory_total_gb(system.get("MemorySummary")),
            },
            "queue_state": {"queue_length": 0},
            "dynamic_state": {
                "running_task_count": 0,
                "availability_score": self._availability_score(system),
            },
            "power_state": system.get("PowerState"),
            "indicator_led": system.get("IndicatorLED"),
            "status": {
                "health": status.get("Health"),
                "state": status.get("State"),
            },
        }

        return ResourceEvent(
            source_type=REDFISH_IBMC_SOURCE_TYPE,
            source_name=self.source_name,
            timestamp=self.timestamp,
            trace_id=self.trace_id,
            node_id=node_id,
            resource_id=node_id,
            resource_type="physical_server",
            attributes=self._drop_none(attributes),
            metrics=self._drop_none(metrics),
        )

    def _system_identifier(self, system: dict[str, Any]) -> str:
        for key in ("UUID", "SerialNumber", "Id", "Name"):
            value = system.get(key)
            if value:
                return str(value)
        raise ValueError("Redfish system payload must include UUID, SerialNumber, Id, or Name")

    def _processor_summary(self, summary: Any) -> dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        return {
            "count": summary.get("Count"),
            "model": summary.get("Model"),
            "status": summary.get("Status"),
        }

    def _cpu_model(self, summary: Any) -> str:
        if isinstance(summary, dict) and summary.get("Model"):
            return str(summary["Model"])
        return "unknown"

    def _cpu_total_cores(self, summary: Any) -> int:
        if not isinstance(summary, dict):
            return 0
        for key in ("TotalEnabledCores", "TotalCores"):
            value = summary.get(key)
            if isinstance(value, int):
                return value
        return 0

    def _available_cpu_cores(self, system: dict[str, Any]) -> int:
        if system.get("PowerState") not in (None, "On"):
            return 0
        return self._cpu_total_cores(system.get("ProcessorSummary"))

    def _memory_summary(self, summary: Any) -> dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        return {
            "total_system_memory_gib": summary.get("TotalSystemMemoryGiB"),
            "status": summary.get("Status"),
        }

    def _memory_total_gb(self, summary: Any) -> float:
        if isinstance(summary, dict) and isinstance(summary.get("TotalSystemMemoryGiB"), (int, float)):
            return float(summary["TotalSystemMemoryGiB"])
        return 0.0

    def _node_status(self, system: dict[str, Any]) -> str:
        if system.get("PowerState") not in (None, "On"):
            return "Offline"

        status = system.get("Status") if isinstance(system.get("Status"), dict) else {}
        health = status.get("Health")
        if health in ("Critical", "Failed"):
            return "Fault"
        return "Ready"

    def _availability_score(self, system: dict[str, Any]) -> float:
        if self._node_status(system) == "Offline":
            return 0.0

        status = system.get("Status") if isinstance(system.get("Status"), dict) else {}
        if status.get("Health") == "Warning":
            return 0.5
        if status.get("Health") in ("Critical", "Failed"):
            return 0.0
        return 1.0

    def _drop_none(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._drop_none(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [self._drop_none(item) for item in value if item is not None]
        return value
