"""Generate synthetic resources, tasks, candidates and labels."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from resource_mapping.candidate_generator import CandidateGenerator
from resource_mapping.io_utils import save_json, set_seed
from resource_mapping.label_generator import LabelGenerator


def _resource(node_type: str, idx: int, rng: random.Random) -> dict[str, Any]:
    host = f"host_{idx % 20:03d}"
    rack = f"rack_{idx % 4:02d}"
    switch = f"switch_{idx % 4:03d}"
    rid = f"{node_type}_{idx:03d}"
    common = {"available": 1.0 if rng.random() > 0.05 else 0.0}
    if node_type == "cpu":
        feat = {"cores": rng.choice([16, 32, 64]), "frequency_ghz": rng.uniform(2.2, 3.8), "memory_gb": rng.choice([64, 128, 256]), "numa_nodes": rng.choice([1, 2, 4]), "utilization": rng.random() * 0.8, "queue_length": rng.randint(0, 12), "power_w": rng.uniform(80, 250), **common}
    elif node_type == "gpu":
        feat = {"fp32_tflops": rng.uniform(10, 80), "tensor_tflops": rng.uniform(80, 1000), "vram_gb": rng.choice([16, 24, 40, 80]), "memory_bandwidth_gbps": rng.uniform(500, 3000), "utilization": rng.random() * 0.85, "temperature": rng.uniform(35, 82), "power_w": rng.uniform(180, 650), **common}
    elif node_type == "fpga":
        feat = {"logic_units": rng.randint(200_000, 1_500_000), "dsp_blocks": rng.randint(1000, 8000), "bram_mb": rng.randint(64, 512), "frequency_mhz": rng.uniform(200, 600), "utilization": rng.random() * 0.75, "power_w": rng.uniform(40, 180), **common}
    elif node_type == "memory":
        feat = {"capacity_gb": rng.choice([128, 256, 512, 1024]), "bandwidth_gbps": rng.uniform(80, 500), "utilization": rng.random() * 0.75, "numa_distance": rng.uniform(1, 3), **common}
    elif node_type == "storage":
        feat = {"capacity_tb": rng.choice([4, 8, 16, 32]), "read_bw_gbps": rng.uniform(2, 24), "write_bw_gbps": rng.uniform(1, 18), "iops": rng.randint(50_000, 1_000_000), "utilization": rng.random() * 0.8, **common}
    elif node_type == "nic":
        feat = {"bandwidth_gbps": rng.choice([25, 50, 100, 200, 400]), "latency_us": rng.uniform(1, 50), "packet_loss": rng.random() * 0.01, "utilization": rng.random() * 0.7, "rdma_support": 1.0 if rng.random() > 0.25 else 0.0, **common}
    else:
        host = f"switch_host_{idx:03d}"
        feat = {"bandwidth_gbps": rng.choice([400, 800, 1600]), "latency_us": rng.uniform(0.5, 8), "port_count": rng.choice([32, 64]), "utilization": rng.random() * 0.6, **common}
    return {"id": rid, "type": node_type, "node_id": host, "rack_id": rack, "switch_id": switch, "features": feat}


def generate_resources(rng: random.Random) -> list[dict[str, Any]]:
    """Generate resource nodes."""

    counts = {"cpu": 20, "gpu": 20, "fpga": 5, "memory": 20, "storage": 10, "nic": 20, "switch": 4}
    return [_resource(t, i, rng) for t, n in counts.items() for i in range(n)]


def generate_edges(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate typed bidirectional topology edges."""

    by_type = {t: [r for r in resources if r["type"] == t] for t in ["cpu", "gpu", "memory", "storage", "nic", "switch"]}
    edges: list[dict[str, Any]] = []

    def add(a: dict[str, Any], rel: str, b: dict[str, Any]) -> None:
        edges.append({"source": a["id"], "target": b["id"], "source_type": a["type"], "target_type": b["type"], "relation": rel})

    for cpu in by_type["cpu"]:
        host = cpu["node_id"]
        for gpu in [r for r in by_type["gpu"] if r["node_id"] == host]:
            add(cpu, "same_node", gpu)
            add(gpu, "same_node", cpu)
        for mem in [r for r in by_type["memory"] if r["node_id"] == host]:
            add(cpu, "connected_to", mem)
            add(mem, "connected_to", cpu)
        for st in [r for r in by_type["storage"] if int(r["id"].split("_")[1]) % 20 == int(cpu["id"].split("_")[1]) % 20]:
            add(cpu, "storage_connect", st)
            add(st, "storage_connect", cpu)
    for gpu in by_type["gpu"]:
        for nic in [r for r in by_type["nic"] if r["node_id"] == gpu["node_id"]]:
            add(gpu, "pcie_connect", nic)
            add(nic, "pcie_connect", gpu)
        for other in by_type["gpu"]:
            if other["id"] != gpu["id"] and other["node_id"] == gpu["node_id"]:
                add(gpu, "share_bandwidth", other)
    for nic in by_type["nic"]:
        switch = next(s for s in by_type["switch"] if s["id"] == nic["switch_id"])
        add(nic, "network_connect", switch)
        add(switch, "network_connect", nic)
    for c1 in by_type["cpu"]:
        for c2 in by_type["cpu"]:
            if c1["id"] != c2["id"] and c1["node_id"] == c2["node_id"]:
                add(c1, "share_memory", c2)
    return edges


def generate_tasks(total: int, rng: random.Random) -> list[dict[str, Any]]:
    """Generate task requirements."""

    task_types = ["llm_inference", "llm_training", "hpc_simulation", "big_data", "graph_analytics", "video_processing", "mixed"]
    modes = ["compute_intensive", "data_intensive", "communication_intensive", "mixed"]
    tasks = []
    for i in range(total):
        mode = rng.choice(modes)
        req = {
            "min_compute_tflops": rng.uniform(5, 160) if mode != "data_intensive" else rng.uniform(0, 40),
            "min_tensor_tflops": rng.uniform(0, 800),
            "min_gpu_memory_gb": rng.choice([0, 16, 24, 40, 80]),
            "min_cpu_cores": rng.choice([4, 8, 16, 32]),
            "min_memory_gb": rng.choice([32, 64, 128, 256]),
            "min_storage_bw_gbps": rng.uniform(1, 16),
            "min_network_bw_gbps": rng.choice([10, 25, 50, 100, 200]),
            "max_latency_us": rng.uniform(5, 80),
            "max_power_w": rng.uniform(500, 2500),
            "deadline_ms": rng.uniform(30, 2000),
            "priority": rng.randint(1, 5),
            "prefer_same_node": 1.0 if rng.random() > 0.5 else 0.0,
            "prefer_low_load": 1.0 if rng.random() > 0.5 else 0.0,
            "prefer_low_energy": 1.0 if rng.random() > 0.5 else 0.0,
            "need_rdma": 1.0 if rng.random() > 0.55 else 0.0,
        }
        tasks.append({"task_id": f"task_{i:04d}", "task_type": rng.choice(task_types), "dominant_mode": mode, "requirements": req})
    return tasks


def main() -> None:
    """Generate all synthetic JSON files."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train", type=int, default=1000)
    parser.add_argument("--val", type=int, default=200)
    parser.add_argument("--test", type=int, default=200)
    parser.add_argument("--max-candidates", type=int, default=20)
    args = parser.parse_args()
    set_seed(args.seed)
    rng = random.Random(args.seed)
    out = Path(args.output)
    resources = generate_resources(rng)
    edges = generate_edges(resources)
    tasks = generate_tasks(args.train + args.val + args.test, rng)
    generator = CandidateGenerator(resources, edges, args.seed)
    candidates = [cand for task in tasks for cand in generator.generate(task, args.max_candidates)]
    labels = LabelGenerator(resources, edges).generate(tasks, candidates)
    splits = {"train": [t["task_id"] for t in tasks[: args.train]], "val": [t["task_id"] for t in tasks[args.train : args.train + args.val]], "test": [t["task_id"] for t in tasks[args.train + args.val :]]}
    save_json(resources, out / "data/raw/resources.json")
    save_json(edges, out / "data/raw/edges.json")
    save_json(tasks, out / "data/raw/tasks.json")
    save_json(candidates, out / "data/processed/candidates.json")
    save_json(labels, out / "data/processed/labels.json")
    save_json(splits, out / "data/processed/splits.json")


if __name__ == "__main__":
    main()
