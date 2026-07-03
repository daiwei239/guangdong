import json
from pathlib import Path

from app.schemas.resource_schema import ResourceStateInput, SensedResourceState, utc_now_iso


class ResourceInputLayer:
    def read_resource_state(self, path: Path) -> SensedResourceState:
        with path.open("r", encoding="utf-8-sig") as fh:
            payload = json.load(fh)

        state = ResourceStateInput.model_validate(payload)
        return SensedResourceState(
            source=state.source,
            timestamp=state.timestamp or utc_now_iso(),
            trace_id=state.trace_id or "TRACE-RESOURCE-STATE",
            resources=state.resources,
            edges=state.edges,
        )


resource_input_layer = ResourceInputLayer()
