from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pipeline import run_pipeline_from_huawei_management


Record = dict[str, int | float | str]


def run_latency_benchmark(
    config_paths: Iterable[Path],
    samples: int,
    output_root: Path,
    csv_path: Path,
    chart_path: Path,
    runner: Callable[[Path, Path | None], dict] = run_pipeline_from_huawei_management,
    timer: Callable[[], float] = perf_counter,
) -> list[Record]:
    configs = [Path(path) for path in config_paths]
    if not configs:
        raise ValueError("At least one config path is required.")
    if samples < 1:
        raise ValueError("samples must be greater than 0.")

    output_root.mkdir(parents=True, exist_ok=True)
    records: list[Record] = []

    for index in range(samples):
        config_path = configs[index % len(configs)]
        output_dir = output_root / f"sample_{index + 1:06d}"
        start = timer()
        payload = runner(config_path, output_dir=output_dir)
        end = timer()

        state_payload = payload.get("ResourceState", {}).get("payload", {})
        node_count = len(state_payload.get("nodes", [])) if isinstance(state_payload, dict) else 0
        records.append(
            {
                "sample_index": index + 1,
                "config_path": str(config_path),
                "output_dir": str(output_dir),
                "snapshot_time": str(state_payload.get("snapshot_time", "")) if isinstance(state_payload, dict) else "",
                "node_count": node_count,
                "latency_ms": round((end - start) * 1000, 3),
            }
        )

    write_csv(records, csv_path)
    write_chart(records, chart_path)
    return records


def run_timeseries_latency_benchmark(
    timeseries_jsonl: Path,
    static_nodes_path: Path,
    samples: int | None,
    output_root: Path,
    csv_path: Path,
    chart_path: Path,
    runner: Callable[[Path, Path | None], dict] = run_pipeline_from_huawei_management,
    timer: Callable[[], float] = perf_counter,
) -> list[Record]:
    static_inventory = json.loads(static_nodes_path.read_text(encoding="utf-8"))
    static_nodes = {node["node_id"]: node for node in static_inventory.get("nodes", [])}
    if not static_nodes:
        raise ValueError("static nodes file must include a non-empty nodes list.")

    output_root.mkdir(parents=True, exist_ok=True)
    input_root = output_root / "_sample_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    records: list[Record] = []

    with timeseries_jsonl.open("r", encoding="utf-8") as fh:
        for line_index, line in enumerate(fh, start=1):
            if samples is not None and line_index > samples:
                break
            if not line.strip():
                continue

            snapshot = json.loads(line)
            payload = build_huawei_payload_from_snapshot(snapshot, static_nodes)
            payload_path = input_root / f"sample_{line_index:06d}_payload.json"
            config_path = input_root / f"sample_{line_index:06d}_config.json"
            output_dir = output_root / f"sample_{line_index:06d}"

            payload_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            config = {
                "timestamp": snapshot.get("timestamp"),
                "trace_id": snapshot.get("trace_id"),
                "platforms": [
                    {
                        "source_type": snapshot.get("source_type", "ascend_device_manager"),
                        "source_name": snapshot.get("source_name", "mindcluster-npu-exporter-simulator"),
                        "file_path": payload_path.name,
                    }
                ],
            }
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            start = timer()
            result = runner(config_path, output_dir=output_dir)
            end = timer()
            state_payload = result.get("ResourceState", {}).get("payload", {})
            node_count = len(state_payload.get("nodes", [])) if isinstance(state_payload, dict) else 0
            records.append(
                {
                    "sample_index": int(snapshot.get("sample_index", line_index)),
                    "config_path": str(config_path),
                    "output_dir": str(output_dir),
                    "snapshot_time": str(state_payload.get("snapshot_time", snapshot.get("timestamp", "")))
                    if isinstance(state_payload, dict)
                    else str(snapshot.get("timestamp", "")),
                    "node_count": node_count,
                    "latency_ms": round((end - start) * 1000, 3),
                }
            )

    write_csv(records, csv_path)
    write_chart(records, chart_path)
    return records


def build_huawei_payload_from_snapshot(snapshot: dict, static_nodes: dict[str, dict]) -> dict:
    nodes = []
    for dynamic_node in snapshot.get("nodes", []):
        node_id = dynamic_node["node_id"]
        static_node = static_nodes[node_id]
        nodes.append(
            {
                "node_id": node_id,
                "resource_id": static_node.get("resource_id", node_id),
                "resource_type": static_node.get("resource_type", "physical_server"),
                "attributes": {
                    "cluster_id": static_node.get("cluster_id"),
                    "cluster_type": static_node.get("cluster_type"),
                    "region": static_node.get("region"),
                    "node_role": static_node.get("node_role", "compute"),
                    "topology_version": "v1",
                    "cpu": static_node.get("cpu", {}),
                    "accelerator": {
                        "accelerator_type": static_node.get("accelerator", {}).get("accelerator_type", "NPU"),
                        "accelerator_vendor": static_node.get("accelerator", {}).get("accelerator_vendor", "Huawei"),
                        "accelerator_model": static_node.get("accelerator", {}).get("accelerator_model", "Ascend 910B"),
                        "accelerator_total_count": static_node.get("accelerator", {}).get("accelerator_total_count", 8),
                        "accelerator_slice_total": static_node.get("accelerator", {}).get("accelerator_slice_total", 8),
                        "accelerator_memory_total_gb": static_node.get("accelerator", {}).get(
                            "accelerator_memory_total_gb", 512
                        ),
                        "device_ids": [
                            f"D-{node_id}-NPU-{device.get('device_id', index)}"
                            for index, device in enumerate(static_node.get("accelerator", {}).get("devices", []))
                        ],
                    },
                    "memory": static_node.get("memory", {}),
                    "storage": static_node.get("storage", {}),
                    "network_capability": static_node.get("network_capability", {}),
                    "software": static_node.get("software", {}),
                    "topology": {
                        "rack_id": static_node.get("rack_id"),
                        "topology_neighbors": static_node.get("topology_neighbors", []),
                    },
                    "source": {
                        "source_type": snapshot.get("source_type", "ascend_device_manager"),
                        "source_name": snapshot.get("source_name", "mindcluster-npu-exporter-simulator"),
                    },
                },
                "metrics": {
                    "node_status": dynamic_node.get("node_status", "Ready"),
                    **dynamic_node.get("metrics", {}),
                },
            }
        )

    return {
        "timestamp": snapshot.get("timestamp"),
        "trace_id": snapshot.get("trace_id"),
        "manager_metadata": {
            "cluster_id": snapshot.get("cluster_id"),
            "sample_index": snapshot.get("sample_index"),
            "sample_interval_seconds": snapshot.get("sample_interval_seconds"),
            "source_type": snapshot.get("source_type", "ascend_device_manager"),
        },
        "nodes": nodes,
    }


def write_csv(records: list[Record], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sample_index", "config_path", "output_dir", "snapshot_time", "node_count", "latency_ms"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["latency_ms"] = f"{float(record['latency_ms']):.3f}"
            writer.writerow(row)


def write_chart(records: list[Record], chart_path: Path) -> None:
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    latencies = [float(record["latency_ms"]) for record in records]
    width = 1100
    height = 420
    padding = 48
    max_latency = max(latencies) if latencies else 1.0
    min_latency = min(latencies) if latencies else 0.0
    span = max(max_latency - min_latency, 1.0)

    points = []
    for offset, latency in enumerate(latencies):
        x = padding if len(latencies) == 1 else padding + offset * (width - padding * 2) / (len(latencies) - 1)
        y = height - padding - ((latency - min_latency) / span) * (height - padding * 2)
        points.append(f"{x:.2f},{y:.2f}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    title = "Huawei Input Pipeline Latency"
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    .metric {{ display: inline-block; margin-right: 24px; }}
    svg {{ border: 1px solid #d1d5db; background: #ffffff; }}
    .axis {{ stroke: #6b7280; stroke-width: 1; }}
    .line {{ fill: none; stroke: #2563eb; stroke-width: 2; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p>
    <span class="metric">samples: {len(records)}</span>
    <span class="metric">min: {min_latency:.3f} ms</span>
    <span class="metric">max: {max_latency:.3f} ms</span>
    <span class="metric">avg: {avg_latency:.3f} ms</span>
  </p>
  <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
    <line class="axis" x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}"></line>
    <line class="axis" x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}"></line>
    <text x="{padding}" y="28">latency_ms</text>
    <text x="{width - padding - 80}" y="{height - 12}">sample</text>
    <text x="{padding + 8}" y="{padding + 6}">{max_latency:.3f} ms</text>
    <text x="{padding + 8}" y="{height - padding - 8}">{min_latency:.3f} ms</text>
    <polyline class="line" points="{' '.join(points)}"></polyline>
  </svg>
</body>
</html>
"""
    chart_path.write_text(html_text, encoding="utf-8")


def expand_config_paths(config: Path | None, config_glob: str | None) -> list[Path]:
    paths: list[Path] = []
    if config is not None:
        paths.append(config)
    if config_glob:
        paths.extend(sorted(Path().glob(config_glob)))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Huawei management input-to-output JSON latency.")
    parser.add_argument("--config", type=Path, help="Huawei management config path to repeat.")
    parser.add_argument("--config-glob", help="Glob for per-sample Huawei management configs.")
    parser.add_argument("--timeseries-jsonl", type=Path, help="JSONL snapshots to benchmark one sample per line.")
    parser.add_argument("--static-nodes", type=Path, help="Static node inventory used with --timeseries-jsonl.")
    parser.add_argument("--samples", type=int, default=1, help="Number of samples to run.")
    parser.add_argument("--output-root", type=Path, default=Path("benchmark_outputs/huawei_latency/json"))
    parser.add_argument("--csv", type=Path, default=Path("benchmark_outputs/huawei_latency/latency.csv"))
    parser.add_argument("--chart", type=Path, default=Path("benchmark_outputs/huawei_latency/latency.html"))
    args = parser.parse_args()

    if args.timeseries_jsonl:
        if args.static_nodes is None:
            parser.error("--static-nodes is required with --timeseries-jsonl.")
        records = run_timeseries_latency_benchmark(
            timeseries_jsonl=args.timeseries_jsonl,
            static_nodes_path=args.static_nodes,
            samples=args.samples,
            output_root=args.output_root,
            csv_path=args.csv,
            chart_path=args.chart,
        )
    else:
        records = run_latency_benchmark(
            config_paths=expand_config_paths(args.config, args.config_glob),
            samples=args.samples,
            output_root=args.output_root,
            csv_path=args.csv,
            chart_path=args.chart,
        )
    print(json.dumps({"samples": len(records), "csv": str(args.csv), "chart": str(args.chart)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
