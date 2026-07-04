import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class FakeMessage:
    def __init__(self, topic: str, key: str, value: dict) -> None:
        self.topic = topic
        self.key = key.encode("utf-8")
        self.value = json.dumps(value).encode("utf-8")


class FakeConsumer:
    def __init__(self, messages) -> None:
        self.messages = list(messages)
        self.subscribed_topics = None

    def subscribe(self, topics) -> None:
        self.subscribed_topics = topics

    def __iter__(self):
        return iter(self.messages)


def test_kafka_adapter_consumes_topic_messages_as_resource_events() -> None:
    from app.input.adapters.kafka_adapter import KafkaInputAdapter, default_topic_mapping

    consumer = FakeConsumer(
        [
            FakeMessage(
                "resource.agent_collect",
                "N-C01-0001",
                {
                    "timestamp": "2026-05-18T10:31:59+08:00",
                    "trace_id": "TRACE-R20260518-000001",
                    "node_id": "N-C01-0001",
                    "resource_type": "CPU",
                    "attributes": {
                        "cluster_type": "Hybrid",
                        "node_role": "compute",
                        "cpu": {
                            "cpu_arch": "ARM",
                            "cpu_model": "Kunpeng-920",
                            "cpu_total_cores": 64,
                        },
                        "accelerator": {"accelerator_type": "None"},
                        "memory": {"memory_total_gb": 512},
                        "storage": {"shared_storage_access": True},
                        "network_capability": {"network_bandwidth_gbps": 100},
                        "software": {"os_version": "openEuler-22.03", "runtime_stack": ["Kubernetes"]},
                    },
                },
            ),
            FakeMessage(
                "resource.realtime_monitor",
                "N-C01-0001",
                {
                    "timestamp": "2026-05-18T10:32:00+08:00",
                    "trace_id": "TRACE-R20260518-000001",
                    "node_id": "N-C01-0001",
                    "metrics": {
                        "node_status": "Ready",
                        "cpu": {"cpu_available_cores": 40, "cpu_utilization": 37.5},
                        "memory": {"memory_available_gb": 260},
                        "queue_state": {"queue_length": 5},
                        "dynamic_state": {"running_task_count": 8, "availability_score": 0.82},
                    },
                },
            ),
        ]
    )

    adapter = KafkaInputAdapter(consumer=consumer, topic_mapping=default_topic_mapping())
    state = adapter.consume_state(max_messages=2)

    assert consumer.subscribed_topics == list(default_topic_mapping())
    assert state.source == "Module-2.1-ResourceInputAggregator"
    assert state.timestamp == "2026-05-18T10:32:00+08:00"
    assert state.trace_id == "TRACE-R20260518-000001"
    assert len(state.resources) == 1
    assert state.resources[0].attributes["cpu"]["cpu_model"] == "Kunpeng-920"
    assert state.resources[0].metrics["cpu"]["cpu_utilization"] == 37.5
