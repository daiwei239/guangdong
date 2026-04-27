"""Test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sample_resources() -> list[dict]:
    """Return a small resource inventory."""

    return [
        {"id": "cpu_000", "type": "cpu", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"cores": 64, "frequency_ghz": 3.0, "memory_gb": 128, "numa_nodes": 2, "utilization": 0.1, "queue_length": 0, "power_w": 150, "available": 1}},
        {"id": "gpu_000", "type": "gpu", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"fp32_tflops": 80, "tensor_tflops": 500, "vram_gb": 80, "memory_bandwidth_gbps": 2000, "utilization": 0.1, "temperature": 50, "power_w": 300, "available": 1}},
        {"id": "fpga_000", "type": "fpga", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"logic_units": 500000, "dsp_blocks": 4000, "bram_mb": 256, "frequency_mhz": 400, "utilization": 0.2, "power_w": 90, "available": 1}},
        {"id": "memory_000", "type": "memory", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"capacity_gb": 512, "bandwidth_gbps": 200, "utilization": 0.1, "numa_distance": 1, "available": 1}},
        {"id": "storage_000", "type": "storage", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"capacity_tb": 8, "read_bw_gbps": 12, "write_bw_gbps": 10, "iops": 200000, "utilization": 0.2, "available": 1}},
        {"id": "nic_000", "type": "nic", "node_id": "host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"bandwidth_gbps": 200, "latency_us": 5, "packet_loss": 0, "utilization": 0.1, "rdma_support": 1, "available": 1}},
        {"id": "switch_000", "type": "switch", "node_id": "switch_host_0", "rack_id": "rack_0", "switch_id": "switch_000", "features": {"bandwidth_gbps": 800, "latency_us": 2, "port_count": 64, "utilization": 0.1, "available": 1}},
    ]


def sample_edges() -> list[dict]:
    """Return typed bidirectional edges."""

    return [
        {"source": "cpu_000", "target": "gpu_000", "source_type": "cpu", "target_type": "gpu", "relation": "same_node"},
        {"source": "gpu_000", "target": "cpu_000", "source_type": "gpu", "target_type": "cpu", "relation": "same_node"},
        {"source": "cpu_000", "target": "memory_000", "source_type": "cpu", "target_type": "memory", "relation": "connected_to"},
        {"source": "memory_000", "target": "cpu_000", "source_type": "memory", "target_type": "cpu", "relation": "connected_to"},
        {"source": "gpu_000", "target": "nic_000", "source_type": "gpu", "target_type": "nic", "relation": "pcie_connect"},
        {"source": "nic_000", "target": "gpu_000", "source_type": "nic", "target_type": "gpu", "relation": "pcie_connect"},
        {"source": "nic_000", "target": "switch_000", "source_type": "nic", "target_type": "switch", "relation": "network_connect"},
        {"source": "switch_000", "target": "nic_000", "source_type": "switch", "target_type": "nic", "relation": "network_connect"},
        {"source": "cpu_000", "target": "storage_000", "source_type": "cpu", "target_type": "storage", "relation": "storage_connect"},
        {"source": "storage_000", "target": "cpu_000", "source_type": "storage", "target_type": "cpu", "relation": "storage_connect"},
        {"source": "gpu_000", "target": "gpu_000", "source_type": "gpu", "target_type": "gpu", "relation": "share_bandwidth"},
        {"source": "cpu_000", "target": "cpu_000", "source_type": "cpu", "target_type": "cpu", "relation": "share_memory"},
    ]


def sample_task() -> dict:
    """Return a feasible task."""

    return {
        "task_id": "task_0000",
        "task_type": "llm_inference",
        "dominant_mode": "compute_intensive",
        "requirements": {
            "min_compute_tflops": 20,
            "min_tensor_tflops": 100,
            "min_gpu_memory_gb": 16,
            "min_cpu_cores": 8,
            "min_memory_gb": 64,
            "min_storage_bw_gbps": 5,
            "min_network_bw_gbps": 50,
            "max_latency_us": 20,
            "max_power_w": 2000,
            "deadline_ms": 1000,
            "priority": 3,
            "prefer_same_node": 1,
            "prefer_low_load": 1,
            "prefer_low_energy": 0,
            "need_rdma": 1,
        },
    }


def sample_candidate() -> dict:
    """Return a feasible candidate."""

    return {"candidate_id": "task_0000_cand_000", "task_id": "task_0000", "nodes": {"cpu": ["cpu_000"], "gpu": ["gpu_000"], "fpga": [], "memory": ["memory_000"], "storage": ["storage_000"], "nic": ["nic_000"], "switch": ["switch_000"]}}
