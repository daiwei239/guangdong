import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_latency_benchmark_writes_csv_and_chart(tmp_path) -> None:
    from scripts.benchmark_huawei_input_latency import run_latency_benchmark

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    output_root = tmp_path / "pipeline_outputs"
    csv_path = tmp_path / "latency.csv"
    chart_path = tmp_path / "latency.html"
    ticks = iter([10.0, 10.0123, 20.0, 20.0456])
    calls = []

    def fake_runner(path, output_dir=None):
        calls.append((path, output_dir))
        return {
            "ResourceState": {
                "payload": {
                    "snapshot_time": "2026-07-08T00:00:00+08:00",
                    "nodes": [{"node_id": "N-ASCEND-SZ-0001"}],
                }
            }
        }

    records = run_latency_benchmark(
        config_paths=[config_path],
        samples=2,
        output_root=output_root,
        csv_path=csv_path,
        chart_path=chart_path,
        runner=fake_runner,
        timer=lambda: next(ticks),
    )

    assert [record["sample_index"] for record in records] == [1, 2]
    assert records[0]["latency_ms"] == 12.3
    assert records[1]["latency_ms"] == 45.6
    assert calls[0][1] == output_root / "sample_000001"
    assert calls[1][1] == output_root / "sample_000002"

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "sample_index,config_path,output_dir,snapshot_time,node_count,latency_ms" in csv_text
    assert "12.300" in csv_text
    assert "45.600" in csv_text

    chart_text = chart_path.read_text(encoding="utf-8")
    assert "Huawei Input Pipeline Latency" in chart_text
    assert "polyline" in chart_text
