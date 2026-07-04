import json
import os
from typing import Any, Iterable

from app.input.resource_event import ResourceEvent
from app.input.state_aggregator import StateAggregator
from app.schemas.resource_schema import SensedResourceState


def default_topic_mapping(prefix: str = "resource") -> dict[str, str]:
    return {
        f"{prefix}.management_config": "management_config",
        f"{prefix}.agent_collect": "agent_collect",
        f"{prefix}.realtime_monitor": "realtime_monitor",
        f"{prefix}.device_plugin": "device_plugin",
        f"{prefix}.topology_probe": "topology_probe",
        f"{prefix}.scheduler_queue": "scheduler_queue",
        f"{prefix}.asset_ops": "asset_ops",
        f"{prefix}.analytics_history": "analytics_history",
    }


class KafkaInputAdapter:
    def __init__(
        self,
        consumer=None,
        topic_mapping: dict[str, str] | None = None,
        bootstrap_servers: str | None = None,
        group_id: str | None = None,
    ) -> None:
        self.topic_mapping = topic_mapping or default_topic_mapping(os.getenv("KAFKA_TOPIC_PREFIX", "resource"))
        self.consumer = consumer or self._build_consumer(
            bootstrap_servers=bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            group_id=group_id or os.getenv("KAFKA_GROUP_ID", "resource-2-1-input"),
        )

    def consume_state(self, max_messages: int | None = None) -> SensedResourceState:
        self.consumer.subscribe(list(self.topic_mapping))
        aggregator = StateAggregator()

        for index, message in enumerate(self.consumer):
            if max_messages is not None and index >= max_messages:
                break
            event = self._event_from_message(message)
            aggregator.ingest(event)

        return aggregator.build_state()

    def _event_from_message(self, message) -> ResourceEvent:
        payload = self._decode_message_value(message.value)
        topic = message.topic
        source_type = payload.get("source_type") or self.topic_mapping.get(topic)
        if not source_type:
            raise ValueError(f"Kafka topic is not mapped to a resource source type: {topic}")

        if not payload.get("node_id") and getattr(message, "key", None):
            payload["node_id"] = self._decode_key(message.key)

        payload.setdefault("source_type", source_type)
        payload.setdefault("source_name", topic)
        return ResourceEvent.model_validate(payload)

    def _decode_message_value(self, value: bytes | str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    def _decode_key(self, key: bytes | str) -> str:
        if isinstance(key, bytes):
            return key.decode("utf-8")
        return key

    def _build_consumer(self, bootstrap_servers: str, group_id: str):
        try:
            from kafka import KafkaConsumer
        except ImportError as exc:
            raise RuntimeError("Kafka input requires kafka-python. Install backend/requirements.txt first.") from exc

        return KafkaConsumer(
            bootstrap_servers=bootstrap_servers.split(","),
            group_id=group_id,
            enable_auto_commit=True,
            auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest"),
        )
