from app.output.message_envelope import build_envelope
from app.output.resource_profile import cluster_id, profile_version
from app.schemas.resource_schema import MessageEnvelope, ProcessedResourceState, ResourceStatePayload


def compact_timestamp(timestamp: str) -> str:
    digits = "".join(char for char in timestamp if char.isdigit())
    if len(digits) >= 14:
        return digits[:14]
    return digits.ljust(14, "0")


class ResourceStateOutput:
    def build(self, state: ProcessedResourceState) -> MessageEnvelope:
        cid = cluster_id(state)
        payload = {
            "cluster_id": cid,
            "snapshot_id": f"RS-{cid}-{compact_timestamp(state.timestamp)}",
            "snapshot_time": state.timestamp,
            "profile_version": profile_version(state),
            "nodes": [self._node_state(resource) for resource in state.resources],
        }
        self._validate_payload(payload)
        payload = ResourceStatePayload.model_validate(payload).model_dump(exclude_none=True)
        return build_envelope(
            state=state,
            message_type="ResourceState",
            target_module=[
                "Module-2.2-ResourceAdaptation",
                "Module-2.3-TaskResourceMapping",
                "Module-3.1-StaticScheduling",
                "Module-3.2-OnlineScheduling",
                "Module-3.3-DistributedScheduling",
            ],
            payload=payload,
            sequence=2,
        )

    def _node_state(self, resource) -> dict:
        metrics = resource.metrics
        attrs = resource.attributes
        return {
            "node_id": attrs.get("node_id", resource.id),
            "node_status": metrics.get("node_status", "Ready"),
            "cpu": metrics.get("cpu", {}),
            "accelerator": metrics.get("accelerator", {}),
            "memory": metrics.get("memory", {}),
            "storage": metrics.get("storage", {}),
            "network": metrics.get("network", {}),
            "queue_state": metrics.get("queue_state", {}),
            "dynamic_state": metrics.get("dynamic_state", {}),
            "energy_state": metrics.get("energy_state", {}),
            "reliability_state": metrics.get("reliability_state", {}),
        }

    def _validate_payload(self, payload: dict) -> None:
        missing = []
        for field in ("cluster_id", "snapshot_id", "snapshot_time", "profile_version"):
            self._require(payload, field, f"payload.{field}", missing)

        nodes = payload.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            missing.append("payload.nodes")
        else:
            for index, node in enumerate(nodes):
                self._validate_node(node, index, missing)

        if missing:
            raise ValueError("ResourceState missing required fields: " + ", ".join(missing))

    def _validate_node(self, node: dict, index: int, missing: list[str]) -> None:
        prefix = f"payload.nodes[{index}]"
        self._require(node, "node_id", f"{prefix}.node_id", missing)
        self._require(node, "node_status", f"{prefix}.node_status", missing)
        self._require_nested(node, ("cpu", "cpu_available_cores"), f"{prefix}.cpu.cpu_available_cores", missing)
        self._require_nested(node, ("cpu", "cpu_utilization"), f"{prefix}.cpu.cpu_utilization", missing)
        self._require_nested(node, ("memory", "memory_available_gb"), f"{prefix}.memory.memory_available_gb", missing)
        self._require_nested(node, ("queue_state", "queue_length"), f"{prefix}.queue_state.queue_length", missing)
        self._require_nested(node, ("dynamic_state", "running_task_count"), f"{prefix}.dynamic_state.running_task_count", missing)
        self._require_nested(node, ("dynamic_state", "availability_score"), f"{prefix}.dynamic_state.availability_score", missing)

        accelerator = node.get("accelerator")
        if isinstance(accelerator, dict) and accelerator:
            self._require(accelerator, "accelerator_available_count", f"{prefix}.accelerator.accelerator_available_count", missing)

        reserved = node.get("queue_state", {}).get("reserved_resources")
        if isinstance(reserved, dict) and reserved:
            for field in ("cpu_cores", "npu_slices", "memory_gb"):
                self._require(reserved, field, f"{prefix}.queue_state.reserved_resources.{field}", missing)

    def _require_nested(self, payload: dict, path: tuple[str, str], label: str, missing: list[str]) -> None:
        parent = payload.get(path[0])
        if not isinstance(parent, dict):
            missing.append(label)
            return
        self._require(parent, path[1], label, missing)

    def _require(self, payload: dict, field: str, label: str, missing: list[str]) -> None:
        if field not in payload or payload[field] is None or payload[field] == "":
            missing.append(label)


resource_state_output = ResourceStateOutput()
