from app.output.message_envelope import build_envelope
from app.output.resource_profile import cluster_id, profile_version
from app.schemas.resource_schema import MessageEnvelope, ProcessedResourceState, ResourceTopologyPayload


class ResourceTopologyOutput:
    def build(self, state: ProcessedResourceState) -> MessageEnvelope:
        cid = cluster_id(state)
        version = self._topology_version(state)
        payload = {
            "cluster_id": cid,
            "topology_id": f"RT-{cid}-{version}",
            "topology_version": version,
            "profile_version": profile_version(state),
            "generated_time": state.timestamp,
            "nodes": [self._node_topology(state, resource) for resource in state.resources],
        }
        self._validate_payload(payload)
        payload = ResourceTopologyPayload.model_validate(payload).model_dump(exclude_none=True)

        return build_envelope(
            state=state,
            message_type="ResourceTopology",
            target_module=[
                "Module-2.2-ResourceAdaptation",
                "Module-2.3-TaskResourceMapping",
                "Module-3.1-StaticScheduling",
                "Module-3.2-OnlineScheduling",
                "Module-3.3-DistributedScheduling",
            ],
            payload=payload,
            sequence=3,
        )

    def _topology_version(self, state: ProcessedResourceState) -> str:
        if not state.resources:
            return "v1"
        return str(state.resources[0].attributes.get("topology_version") or "v1")

    def _node_topology(self, state: ProcessedResourceState, resource) -> dict:
        attrs = resource.attributes
        topology = attrs.get("topology", {})
        node_id = attrs.get("node_id", resource.id)
        return {
            "node_id": node_id,
            "rack_id": topology.get("rack_id"),
            "topology_neighbors": topology.get("topology_neighbors", []),
            "link_cost_to_nodes": self._link_costs(state, resource.id),
        }

    def _link_costs(self, state: ProcessedResourceState, source_resource_id: str) -> dict:
        resource_id_to_node_id = {
            resource.id: resource.attributes.get("node_id", resource.id)
            for resource in state.resources
        }
        links = {}
        for edge in state.edges:
            if edge.source != source_resource_id:
                continue
            target_node_id = resource_id_to_node_id.get(edge.target, edge.target)
            links[target_node_id] = {
                "latency_ms": edge.latency_ms,
                "bandwidth_gbps": edge.bandwidth_gbps,
                "interconnect_type": edge.relation_type,
                "cost_score": edge.weight,
            }
        return links

    def _validate_payload(self, payload: dict) -> None:
        missing = []
        for field in ("cluster_id", "topology_id", "topology_version", "profile_version", "nodes"):
            self._require(payload, field, f"payload.{field}", missing)

        nodes = payload.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            missing.append("payload.nodes")
        else:
            for index, node in enumerate(nodes):
                self._validate_node(node, index, missing)

        if missing:
            raise ValueError("ResourceTopology missing required fields: " + ", ".join(missing))

    def _validate_node(self, node: dict, index: int, missing: list[str]) -> None:
        prefix = f"payload.nodes[{index}]"
        self._require(node, "node_id", f"{prefix}.node_id", missing)

        links = node.get("link_cost_to_nodes")
        if isinstance(links, dict):
            for target_node_id, link in links.items():
                link_prefix = f"{prefix}.link_cost_to_nodes.{target_node_id}"
                self._require(link, "latency_ms", f"{link_prefix}.latency_ms", missing)
                self._require(link, "bandwidth_gbps", f"{link_prefix}.bandwidth_gbps", missing)
                self._require(link, "interconnect_type", f"{link_prefix}.interconnect_type", missing)

    def _require(self, payload: dict, field: str, label: str, missing: list[str]) -> None:
        if field not in payload or payload[field] is None or payload[field] == "":
            missing.append(label)


resource_topology_output = ResourceTopologyOutput()
