import re
from typing import Any


CLUSTER_ID_PATTERN = re.compile(r"^C-[A-Z]+-\d{2}$")
NODE_ID_PATTERN = re.compile(r"^N-C\d{2}-\d{4}$")


def normalize_cluster_id(attributes: dict[str, Any]) -> str:
    cluster_id = attributes.get("cluster_id")
    if isinstance(cluster_id, str) and CLUSTER_ID_PATTERN.match(cluster_id):
        return cluster_id

    cluster_type = str(attributes.get("cluster_type") or "UNKNOWN").upper()
    return f"C-{cluster_type}-01"


def cluster_short_code(cluster_id: str) -> str:
    parts = cluster_id.split("-")
    if len(parts) == 3 and parts[0] == "C" and parts[2].isdigit():
        return f"C{int(parts[2]):02d}"
    return "C01"


def normalize_node_id(attributes: dict[str, Any], cluster_id: str, sequence: int) -> str:
    node_id = attributes.get("node_id")
    if isinstance(node_id, str) and NODE_ID_PATTERN.match(node_id):
        return node_id
    return f"N-{cluster_short_code(cluster_id)}-{sequence:04d}"


def build_device_ids(node_id: str, accelerator: dict[str, Any]) -> list[str]:
    accelerator_type = accelerator.get("accelerator_type")
    if not accelerator_type or accelerator_type == "None":
        return []

    total_count = accelerator.get("accelerator_total_count") or 0
    try:
        count = int(total_count)
    except (TypeError, ValueError):
        count = 0

    return [f"D-{node_id}-{accelerator_type}-{index}" for index in range(count)]
