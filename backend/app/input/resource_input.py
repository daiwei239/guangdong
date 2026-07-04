import json
from pathlib import Path

from app.input.adapters.source_adapter import events_from_grouped_sources
from app.input.resource_event import ResourceEvent
from app.input.state_aggregator import StateAggregator
from app.schemas.resource_schema import ResourceStateInput, SensedResourceState, utc_now_iso


class ResourceInputLayer:
    def read_resource_state(self, path: Path) -> SensedResourceState:
        with path.open("r", encoding="utf-8-sig") as fh:
            payload = json.load(fh)

        if "events" in payload:
            return self._read_events(payload)
        if "sources" in payload:
            return self._read_grouped_sources(payload)

        return self._read_legacy_state(payload)

    def _read_legacy_state(self, payload: dict) -> SensedResourceState:
        state = ResourceStateInput.model_validate(payload)
        return SensedResourceState(
            source=state.source,
            timestamp=state.timestamp or utc_now_iso(),
            trace_id=state.trace_id or "TRACE-RESOURCE-STATE",
            resources=state.resources,
            edges=state.edges,
        )

    def _read_events(self, payload: dict) -> SensedResourceState:
        aggregator = StateAggregator(timestamp=payload.get("timestamp"), trace_id=payload.get("trace_id"))
        for event_payload in payload.get("events", []):
            aggregator.ingest(ResourceEvent.model_validate(event_payload))
        return aggregator.build_state()

    def _read_grouped_sources(self, payload: dict) -> SensedResourceState:
        aggregator = StateAggregator(timestamp=payload.get("timestamp"), trace_id=payload.get("trace_id"))
        for event in events_from_grouped_sources(payload):
            aggregator.ingest(event)
        return aggregator.build_state()


resource_input_layer = ResourceInputLayer()
