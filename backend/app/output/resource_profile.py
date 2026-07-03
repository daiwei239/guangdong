from app.output.message_envelope import build_envelope
from app.schemas.resource_schema import MessageEnvelope, ProcessedResourceState, ResourceProfilePayload


def cluster_id(state: ProcessedResourceState) -> str:
    if not state.resources:
        return "UNKNOWN"
    return str(state.resources[0].attributes.get("cluster_id") or "UNKNOWN")


def profile_version(state: ProcessedResourceState) -> str:
    if not state.resources:
        return "v1"
    return str(state.resources[0].attributes.get("profile_version") or "v1")


class ResourceProfileOutput:
    def build(self, state: ProcessedResourceState) -> MessageEnvelope:
        cid = cluster_id(state)
        version = profile_version(state)
        payload = {
            "cluster_id": cid,
            "profile_id": f"RP-{cid}-{version}",
            "profile_version": version,
            "cluster_type": self._cluster_attr(state, "cluster_type"),
            "region": self._cluster_attr(state, "region"),
            "generated_time": state.timestamp,
            "nodes": [self._node_profile(resource) for resource in state.resources],
        }
        self._validate_payload(payload)
        payload = ResourceProfilePayload.model_validate(payload).model_dump(exclude_none=True)

        return build_envelope(
            state=state,
            message_type="ResourceProfile",
            target_module=[
                "Module-2.2-ResourceAdaptation",
                "Module-2.3-TaskResourceMapping",
                "Module-3.1-StaticScheduling",
                "Module-3.2-OnlineScheduling",
                "Module-3.3-DistributedScheduling",
            ],
            payload=payload,
            sequence=1,
        )

    def _cluster_attr(self, state: ProcessedResourceState, key: str, default=None):
        if not state.resources:
            return default
        return state.resources[0].attributes.get(key, default)

    def _node_profile(self, resource) -> dict:
        attrs = resource.attributes
        return {
            "node_id": attrs.get("node_id", resource.id),
            "node_role": attrs.get("node_role", "compute"),
            "cpu": attrs.get("cpu", {}),
            "accelerator": attrs.get("accelerator", {"accelerator_type": "None", "accelerator_total_count": 0}),
            "memory": attrs.get("memory", {}),
            "storage": attrs.get("storage", {}),
            "network_capability": attrs.get("network_capability", {}),
            "software": attrs.get("software", {}),
        }

    def _validate_payload(self, payload: dict) -> None:
        missing = []
        for field in ("cluster_id", "profile_id", "profile_version", "cluster_type", "nodes"):
            self._require(payload, field, f"payload.{field}", missing)

        nodes = payload.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            missing.append("payload.nodes")
        else:
            for index, node in enumerate(nodes):
                self._validate_node(node, index, missing)

        if missing:
            raise ValueError("ResourceProfile missing required fields: " + ", ".join(missing))

    def _validate_node(self, node: dict, index: int, missing: list[str]) -> None:
        prefix = f"payload.nodes[{index}]"
        self._require(node, "node_id", f"{prefix}.node_id", missing)
        self._require(node, "node_role", f"{prefix}.node_role", missing)
        self._require_nested(node, ("cpu", "cpu_arch"), f"{prefix}.cpu.cpu_arch", missing)
        self._require_nested(node, ("cpu", "cpu_model"), f"{prefix}.cpu.cpu_model", missing)
        self._require_nested(node, ("cpu", "cpu_total_cores"), f"{prefix}.cpu.cpu_total_cores", missing)
        self._require_nested(node, ("accelerator", "accelerator_type"), f"{prefix}.accelerator.accelerator_type", missing)
        self._require_nested(node, ("memory", "memory_total_gb"), f"{prefix}.memory.memory_total_gb", missing)
        self._require_nested(node, ("storage", "shared_storage_access"), f"{prefix}.storage.shared_storage_access", missing)
        self._require_nested(node, ("network_capability", "network_bandwidth_gbps"), f"{prefix}.network_capability.network_bandwidth_gbps", missing)
        self._require_nested(node, ("software", "os_version"), f"{prefix}.software.os_version", missing)
        self._require_nested(node, ("software", "runtime_stack"), f"{prefix}.software.runtime_stack", missing)

        accelerator = node.get("accelerator", {})
        accelerator_type = accelerator.get("accelerator_type")
        if accelerator_type and accelerator_type != "None":
            for field in (
                "accelerator_vendor",
                "accelerator_model",
                "accelerator_total_count",
                "accelerator_memory_total_gb",
            ):
                self._require(accelerator, field, f"{prefix}.accelerator.{field}", missing)

    def _require_nested(self, payload: dict, path: tuple[str, str], label: str, missing: list[str]) -> None:
        parent = payload.get(path[0])
        if not isinstance(parent, dict):
            missing.append(label)
            return
        self._require(parent, path[1], label, missing)

    def _require(self, payload: dict, field: str, label: str, missing: list[str]) -> None:
        if field not in payload or payload[field] is None or payload[field] == "":
            missing.append(label)


resource_profile_output = ResourceProfileOutput()
