from typing import Any

from app.input.resource_event import ResourceEvent, ResourceSourceBatch


def events_from_grouped_sources(payload: dict[str, Any]) -> list[ResourceEvent]:
    timestamp = payload.get("timestamp")
    trace_id = payload.get("trace_id")
    events: list[ResourceEvent] = []

    for source_type, source_payload in payload.get("sources", {}).items():
        source = ResourceSourceBatch.model_validate(source_payload)
        source_timestamp = source.timestamp or timestamp
        source_trace_id = source.trace_id or trace_id

        for node in source.nodes:
            events.append(
                ResourceEvent(
                    source_type=source_type,
                    source_name=source.source_name,
                    timestamp=source_timestamp,
                    trace_id=source_trace_id,
                    node_id=node.node_id,
                    resource_id=node.resource_id,
                    resource_type=node.resource_type,
                    attributes=node.attributes,
                    metrics=node.metrics,
                    topology=node.topology,
                    edges=[],
                )
            )

        if source.edges:
            edge_node_id = source.nodes[0].node_id if source.nodes else "__edges__"
            events.append(
                ResourceEvent(
                    source_type=source_type,
                    source_name=source.source_name,
                    timestamp=source_timestamp,
                    trace_id=source_trace_id,
                    node_id=edge_node_id,
                    attributes={},
                    metrics={},
                    topology={},
                    edges=source.edges,
                )
            )

    return events
