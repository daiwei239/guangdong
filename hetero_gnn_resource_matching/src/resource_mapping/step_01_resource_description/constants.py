"""Shared constants for resource matching."""

from __future__ import annotations

NODE_TYPES = ["cpu", "gpu", "fpga", "memory", "storage", "nic", "switch"]

EDGE_TYPES = [
    ("cpu", "same_node", "gpu"),
    ("gpu", "same_node", "cpu"),
    ("cpu", "connected_to", "memory"),
    ("memory", "connected_to", "cpu"),
    ("gpu", "pcie_connect", "nic"),
    ("nic", "pcie_connect", "gpu"),
    ("nic", "network_connect", "switch"),
    ("switch", "network_connect", "nic"),
    ("cpu", "storage_connect", "storage"),
    ("storage", "storage_connect", "cpu"),
    ("gpu", "share_bandwidth", "gpu"),
    ("cpu", "share_memory", "cpu"),
]

FEATURE_FIELDS = {
    "cpu": ["cores", "frequency_ghz", "memory_gb", "numa_nodes", "utilization", "queue_length", "power_w", "available"],
    "gpu": ["fp32_tflops", "tensor_tflops", "vram_gb", "memory_bandwidth_gbps", "utilization", "temperature", "power_w", "available"],
    "fpga": ["logic_units", "dsp_blocks", "bram_mb", "frequency_mhz", "utilization", "power_w", "available"],
    "memory": ["capacity_gb", "bandwidth_gbps", "utilization", "numa_distance", "available"],
    "storage": ["capacity_tb", "read_bw_gbps", "write_bw_gbps", "iops", "utilization", "available"],
    "nic": ["bandwidth_gbps", "latency_us", "packet_loss", "utilization", "rdma_support", "available"],
    "switch": ["bandwidth_gbps", "latency_us", "port_count", "utilization", "available"],
}

TASK_TYPES = ["llm_inference", "llm_training", "hpc_simulation", "big_data", "graph_analytics", "video_processing", "mixed"]
DOMINANT_MODES = ["compute_intensive", "data_intensive", "communication_intensive", "mixed"]

TASK_NUMERIC_FIELDS = [
    "min_compute_tflops",
    "min_tensor_tflops",
    "min_gpu_memory_gb",
    "min_cpu_cores",
    "min_memory_gb",
    "min_storage_bw_gbps",
    "min_network_bw_gbps",
    "max_latency_us",
    "max_power_w",
    "deadline_ms",
    "priority",
    "prefer_same_node",
    "prefer_low_load",
    "prefer_low_energy",
    "need_rdma",
]

CANDIDATE_NODE_TEMPLATE = {node_type: [] for node_type in NODE_TYPES}
