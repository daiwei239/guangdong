from typing import Any, Dict
from copy import deepcopy

from app.process.identifier import build_device_ids, normalize_cluster_id, normalize_node_id
from app.schemas.resource_schema import ProcessedResourceRecord, ProcessedResourceState, SensedResourceState, utc_now_iso


class ResourceProcessLayer:
    def normalize(self, state: SensedResourceState) -> ProcessedResourceState:
        resources = [
            self._normalize_resource(resource, index + 1)
            for index, resource in enumerate(state.resources)
        ]
        return ProcessedResourceState(
            source=state.source,
            timestamp=state.timestamp,
            processed_at=utc_now_iso(),
            trace_id=state.trace_id,
            resources=resources,
            edges=state.edges,
        )

    def _normalize_resource(self, resource, sequence: int) -> ProcessedResourceRecord:
        attributes = deepcopy(resource.attributes)
        metrics = deepcopy(resource.metrics)

        cluster_id = normalize_cluster_id(attributes)
        node_id = normalize_node_id(attributes, cluster_id, sequence)
        attributes["cluster_id"] = cluster_id
        attributes["node_id"] = node_id

        self._move_numa_topology_to_cpu(attributes)
        self._normalize_accelerator_temperature(metrics)
        self._normalize_device_ids(attributes, node_id)

        return ProcessedResourceRecord(
            id=resource.id,
            type=resource.type,
            attributes=attributes,
            metrics=metrics,
            normalized_metrics=self._normalize_metrics(metrics),
        )

    def _move_numa_topology_to_cpu(self, attributes: dict[str, Any]) -> None:
        topology = attributes.get("topology")
        if not isinstance(topology, dict) or "numa_topology" not in topology:
            return

        cpu = attributes.setdefault("cpu", {})
        if isinstance(cpu, dict) and "numa_topology" not in cpu:
            cpu["numa_topology"] = topology["numa_topology"]
        topology.pop("numa_topology", None)

    def _normalize_accelerator_temperature(self, metrics: dict[str, Any]) -> None:
        accelerator = metrics.get("accelerator")
        if not isinstance(accelerator, dict):
            return
        if "accelerator_temperature" not in accelerator and "accelerator_temperature_celsius" in accelerator:
            accelerator["accelerator_temperature"] = accelerator["accelerator_temperature_celsius"]
        accelerator.pop("accelerator_temperature_celsius", None)

    def _normalize_device_ids(self, attributes: dict[str, Any], node_id: str) -> None:
        accelerator = attributes.get("accelerator")
        if not isinstance(accelerator, dict):
            return
        device_ids = build_device_ids(node_id, accelerator)
        if device_ids:
            accelerator["device_ids"] = device_ids
        else:
            accelerator.pop("device_ids", None)

    def _normalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        normalized = {}
        for key in sorted(metrics):
            value = metrics[key]
            converted = self._normalize_value(value)
            if converted is not None:
                normalized[key] = converted
        return normalized

    def _normalize_value(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric < 0:
                return 0.0
            if numeric <= 1:
                return round(numeric, 6)
            return round(min(numeric / 100.0, 1.0), 6)
        return None


resource_process_layer = ResourceProcessLayer()
