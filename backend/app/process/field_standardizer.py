from typing import Any


def standardize_resource_fields(attributes: dict[str, Any], metrics: dict[str, Any]) -> None:
    _standardize_profile_attributes(attributes)
    _standardize_state_metrics(metrics)


def _standardize_profile_attributes(attributes: dict[str, Any]) -> None:
    cpu = attributes.get("cpu")
    if isinstance(cpu, dict):
        _rename(cpu, "arch", "cpu_arch")
        _rename(cpu, "model", "cpu_model")
        _rename(cpu, "total_cores", "cpu_total_cores")

    accelerator = attributes.get("accelerator")
    if isinstance(accelerator, dict):
        _rename(accelerator, "type", "accelerator_type")
        _rename(accelerator, "vendor", "accelerator_vendor")
        _rename(accelerator, "model", "accelerator_model")
        _rename(accelerator, "total_count", "accelerator_total_count")

    memory = attributes.get("memory")
    if isinstance(memory, dict):
        _mb_to_gb(memory, "memory_total_mb", "memory_total_gb")

    network = attributes.get("network_capability")
    if isinstance(network, dict):
        _mbps_to_gbps(network, "network_bandwidth_mbps", "network_bandwidth_gbps")


def _standardize_state_metrics(metrics: dict[str, Any]) -> None:
    cpu = metrics.get("cpu")
    if isinstance(cpu, dict):
        _rename(cpu, "available_cores", "cpu_available_cores")
        if "cpu_utilization" not in cpu and "cpu_utilization_ratio" in cpu:
            cpu["cpu_utilization"] = round(float(cpu["cpu_utilization_ratio"]) * 100, 6)
        cpu.pop("cpu_utilization_ratio", None)

    memory = metrics.get("memory")
    if isinstance(memory, dict):
        _mb_to_gb(memory, "memory_available_mb", "memory_available_gb")

    accelerator = metrics.get("accelerator")
    if isinstance(accelerator, dict):
        _rename(accelerator, "temperature", "accelerator_temperature")
        _rename(accelerator, "utilization", "accelerator_utilization")


def _rename(payload: dict[str, Any], old: str, new: str) -> None:
    if new not in payload and old in payload:
        payload[new] = payload[old]
    payload.pop(old, None)


def _mb_to_gb(payload: dict[str, Any], old: str, new: str) -> None:
    if new not in payload and old in payload:
        payload[new] = round(float(payload[old]) / 1024, 6)
    payload.pop(old, None)


def _mbps_to_gbps(payload: dict[str, Any], old: str, new: str) -> None:
    if new not in payload and old in payload:
        payload[new] = round(float(payload[old]) / 1000, 6)
    payload.pop(old, None)
