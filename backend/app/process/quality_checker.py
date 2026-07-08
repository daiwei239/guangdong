from typing import Any


def sanitize_realtime_metrics(metrics: dict[str, Any]) -> None:
    cpu = metrics.get("cpu")
    if isinstance(cpu, dict):
        _clamp_min(cpu, "cpu_available_cores", 0)
        _clamp_range(cpu, "cpu_utilization", 0, 100)

    accelerator = metrics.get("accelerator")
    if isinstance(accelerator, dict):
        _clamp_min(accelerator, "accelerator_available_count", 0)
        _clamp_min(accelerator, "accelerator_slice_available", 0)
        _clamp_range(accelerator, "accelerator_utilization", 0, 100)
        _clamp_min(accelerator, "accelerator_temperature", 0)

    memory = metrics.get("memory")
    if isinstance(memory, dict):
        _clamp_min(memory, "memory_available_gb", 0)

    storage = metrics.get("storage")
    if isinstance(storage, dict):
        _clamp_min(storage, "local_storage_available_gb", 0)
        _clamp_min(storage, "storage_read_bw_gbps", 0)
        _clamp_min(storage, "storage_write_bw_gbps", 0)

    network = metrics.get("network")
    if isinstance(network, dict):
        _clamp_min(network, "network_latency_ms", 0)
        _clamp_range(network, "packet_loss_rate", 0, 1)

    queue_state = metrics.get("queue_state")
    if isinstance(queue_state, dict):
        _clamp_min(queue_state, "queue_length", 0)
        _clamp_min(queue_state, "expected_wait_time_s", 0)
        reserved = queue_state.get("reserved_resources")
        if isinstance(reserved, dict):
            for field in ("cpu_cores", "npu_slices", "memory_gb"):
                _clamp_min(reserved, field, 0)

    dynamic_state = metrics.get("dynamic_state")
    if isinstance(dynamic_state, dict):
        _clamp_min(dynamic_state, "running_task_count", 0)
        _clamp_min(dynamic_state, "load_1min", 0)
        _clamp_range(dynamic_state, "resource_fragmentation_score", 0, 1)
        _clamp_range(dynamic_state, "availability_score", 0, 1)

    energy_state = metrics.get("energy_state")
    if isinstance(energy_state, dict):
        _clamp_min(energy_state, "power_current_w", 0)
        _clamp_range(energy_state, "energy_efficiency_score", 0, 1)

    reliability_state = metrics.get("reliability_state")
    if isinstance(reliability_state, dict):
        _clamp_range(reliability_state, "failure_rate_recent", 0, 1)


def _clamp_min(payload: dict[str, Any], field: str, minimum: float) -> None:
    if field in payload and isinstance(payload[field], (int, float)):
        payload[field] = max(payload[field], minimum)


def _clamp_range(payload: dict[str, Any], field: str, minimum: float, maximum: float) -> None:
    if field in payload and isinstance(payload[field], (int, float)):
        payload[field] = min(max(payload[field], minimum), maximum)
