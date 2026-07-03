import json
import re
from pathlib import Path

from app.output.resource_profile import resource_profile_output
from app.output.resource_state import resource_state_output
from app.output.resource_topology import resource_topology_output
from app.schemas.resource_schema import MessageEnvelope, ProcessedResourceState


class ResourceOutputLayer:
    def build_outputs(self, state: ProcessedResourceState) -> dict[str, MessageEnvelope]:
        return {
            "ResourceProfile": resource_profile_output.build(state),
            "ResourceState": resource_state_output.build(state),
            "ResourceTopology": resource_topology_output.build(state),
        }

    def dump_outputs(self, outputs: dict[str, MessageEnvelope]) -> dict[str, dict]:
        return {name: envelope.model_dump() for name, envelope in outputs.items()}

    def write_outputs(self, outputs: dict[str, MessageEnvelope], output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        cluster_id = self._cluster_id(outputs)
        for name, envelope in outputs.items():
            path = output_dir / self.file_name(name, envelope, cluster_id)
            path.write_text(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    def file_name(self, message_type: str, envelope: MessageEnvelope, cluster_id: str | None = None) -> str:
        cluster = cluster_id or self._cluster_id({message_type: envelope})
        timestamp = self._compact_timestamp(envelope.timestamp)
        return f"{message_type}-{cluster}-{timestamp}.json"

    def _cluster_id(self, outputs: dict[str, MessageEnvelope]) -> str:
        profile = outputs.get("ResourceProfile")
        if profile is None:
            return "UNKNOWN"
        return str(profile.payload.get("cluster_id") or "UNKNOWN")

    def _compact_timestamp(self, timestamp: str) -> str:
        digits = re.sub(r"\D", "", timestamp)
        if len(digits) >= 14:
            return digits[:14]
        return digits.ljust(14, "0")


resource_output_layer = ResourceOutputLayer()
