from copy import deepcopy
from typing import Any

from app.input.resource_event import ResourceEvent
from app.schemas.resource_schema import RawResourceRecord, RawTopologyEdge, SensedResourceState, utc_now_iso


AGGREGATED_INPUT_SOURCE = "Module-2.1-ResourceInputAggregator"


class StateAggregator:
    def __init__(self, timestamp: str | None = None, trace_id: str | None = None) -> None:
        self.timestamp = timestamp
        self.trace_id = trace_id
        self._resources: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, RawTopologyEdge] = {}

    def ingest(self, event: ResourceEvent) -> None:
        resource_id = event.resource_id or event.node_id
        resource = self._resources.setdefault(
            resource_id,
            {
                "id": resource_id,
                "type": event.resource_type,
                "attributes": {"node_id": event.node_id},
                "metrics": {},
            },
        )
        if event.resource_type != "resource":
            resource["type"] = event.resource_type

        self._merge_dict(resource["attributes"], event.attributes)
        resource["attributes"].setdefault("node_id", event.node_id)
        if event.topology:
            topology = resource["attributes"].setdefault("topology", {})
            if isinstance(topology, dict):
                self._merge_dict(topology, event.topology)

        self._merge_dict(resource["metrics"], event.metrics)

        for edge in event.edges:
            self._edges[edge.edge_id] = edge

        self._advance_timestamp(event.timestamp)
        if event.trace_id and not self.trace_id:
            self.trace_id = event.trace_id

    def build_state(self) -> SensedResourceState:
        resources = [
            RawResourceRecord(
                id=resource["id"],
                type=resource["type"],
                attributes=resource["attributes"],
                metrics=resource["metrics"],
            )
            for resource in self._resources.values()
        ]
        return SensedResourceState(
            source=AGGREGATED_INPUT_SOURCE,
            timestamp=self.timestamp or utc_now_iso(),
            trace_id=self.trace_id or "TRACE-RESOURCE-STATE",
            resources=resources,
            edges=list(self._edges.values()),
        )

    def _advance_timestamp(self, timestamp: str | None) -> None:
        if not timestamp:
            return
        if self.timestamp is None or timestamp > self.timestamp:
            self.timestamp = timestamp

    def _merge_dict(self, target: dict[str, Any], incoming: dict[str, Any]) -> None:
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge_dict(target[key], value)
            else:
                target[key] = deepcopy(value)
