"""Generate a static HTML visualization report for evaluation results."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from resource_mapping.io_utils import load_json, load_yaml, resolve_path


def _safe_load_json(path: Path, default: Any) -> Any:
    """Load JSON if it exists and is non-empty, otherwise return default."""

    if not path.exists() or path.stat().st_size == 0:
        return default
    return load_json(path)


def _format_value(value: Any) -> str:
    """Format values for metric display."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if 0.0 <= value <= 1.0:
            return f"{value:.2%}"
        return f"{value:.4f}"
    return html.escape(str(value))


def _bar(width: float, label: str = "") -> str:
    """Render a compact horizontal bar."""

    pct = max(0.0, min(100.0, width * 100.0))
    return f'<div class="bar"><span style="width:{pct:.1f}%"></span></div><small>{html.escape(label)}</small>'


def _metric_cards(metrics: dict[str, Any]) -> str:
    """Render metric cards."""

    if not metrics:
        return '<p class="muted">No evaluation metrics found. Run evaluate.py first.</p>'
    cards = []
    for key, value in metrics.items():
        cards.append(f'<article class="metric"><strong>{html.escape(key)}</strong><span>{_format_value(value)}</span></article>')
    return "\n".join(cards)


def _metric_bars(metrics: dict[str, Any]) -> str:
    """Render normalized metric bars for values in [0, 1]."""

    preferred = [
        "top1_accuracy",
        "top5_hit_rate",
        "mean_reciprocal_rank",
        "qos_satisfaction_rate",
        "constraint_satisfaction_rate",
        "auc",
        "precision",
        "recall",
        "f1",
    ]
    rows = []
    for key in preferred:
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            rows.append(f"<tr><td>{html.escape(key)}</td><td>{_bar(float(value), _format_value(float(value)))}</td></tr>")
    return "\n".join(rows) or '<tr><td colspan="2" class="muted">No normalized metrics available.</td></tr>'


def _resource_bars(resources: list[dict[str, Any]]) -> str:
    """Render resource count bars."""

    counts = Counter(r.get("type", "unknown") for r in resources)
    max_count = max(counts.values() or [1])
    rows = []
    for node_type in ["cpu", "gpu", "fpga", "memory", "storage", "nic", "switch"]:
        count = counts.get(node_type, 0)
        rows.append(f"<tr><td>{node_type}</td><td>{_bar(count / max_count, str(count))}</td></tr>")
    return "\n".join(rows)


def _topk_table(topk: dict[str, Any]) -> str:
    """Render Top-K candidates."""

    candidates = topk.get("top_n_candidates", []) if isinstance(topk, dict) else []
    if not candidates:
        return '<p class="muted">No Top-K result found. Run infer.py first.</p>'
    rows = []
    max_score = max([float(item.get("score", 0.0)) for item in candidates] or [1.0])
    for rank, item in enumerate(candidates, start=1):
        score = float(item.get("score", 0.0))
        verified = bool(item.get("verified", False))
        badge = '<span class="badge ok">verified</span>' if verified else '<span class="badge bad">failed</span>'
        rows.append(
            "<tr>"
            f"<td>{rank}</td>"
            f"<td>{html.escape(str(item.get('candidate_id', '')))}</td>"
            f"<td>{_bar(score / max_score if max_score else 0.0, f'{score:.4f}')}</td>"
            f"<td>{badge}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _top1_details(topk: dict[str, Any]) -> str:
    """Render Top-1 candidate nodes and verification."""

    top1 = topk.get("top_1_subnet") if isinstance(topk, dict) else None
    if not top1:
        return '<p class="muted">No Top-1 subnet available.</p>'
    nodes = top1.get("nodes", {})
    node_rows = "\n".join(
        f"<tr><td>{html.escape(node_type)}</td><td>{html.escape(', '.join(node_ids) if node_ids else '-')}</td></tr>"
        for node_type, node_ids in nodes.items()
    )
    verification = top1.get("verification", {})
    verify_rows = []
    for key in ["capacity_satisfied", "performance_satisfied", "topology_satisfied", "qos_satisfied"]:
        value = bool(verification.get(key, False))
        badge = '<span class="badge ok">true</span>' if value else '<span class="badge bad">false</span>'
        verify_rows.append(f"<tr><td>{html.escape(key)}</td><td>{badge}</td></tr>")
    violations = verification.get("violations", [])
    violation_text = ", ".join(violations) if violations else "none"
    return f"""
    <div class="grid two">
      <section>
        <h3>Top-1 subnet nodes</h3>
        <table><tbody>{node_rows}</tbody></table>
      </section>
      <section>
        <h3>Verification</h3>
        <table><tbody>{''.join(verify_rows)}<tr><td>violations</td><td>{html.escape(violation_text)}</td></tr></tbody></table>
      </section>
    </div>
    """


def build_report(
    metrics: dict[str, Any],
    topk: dict[str, Any],
    resources: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    splits: dict[str, list[str]],
) -> str:
    """Build a self-contained HTML report."""

    relation_counts = Counter(edge.get("relation", "unknown") for edge in edges)
    split_text = ", ".join(f"{k}: {len(v)}" for k, v in splits.items()) if splits else "unknown"
    top_task = topk.get("task_id", "not generated") if isinstance(topk, dict) else "not generated"
    relation_text = ", ".join(f"{rel}={count}" for rel, count in relation_counts.items())
    payload = html.escape(json.dumps({"metrics": metrics, "topk": topk}, ensure_ascii=False, indent=2))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resource Matching Evaluation Report</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #18202a;
      --muted: #687385;
      --line: #d8dde6;
      --blue: #2563eb;
      --green: #0f9f6e;
      --red: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.55 "Segoe UI", Arial, sans-serif; }}
    header {{ padding: 28px 36px; background: #15202f; color: white; }}
    header h1 {{ margin: 0 0 6px; font-size: 26px; font-weight: 650; }}
    header p {{ margin: 0; color: #c7d2e3; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0 0 10px; font-size: 15px; }}
    .grid {{ display: grid; gap: 14px; }}
    .two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .metrics {{ grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }}
    .metric {{ background: #f9fafb; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .metric strong {{ display: block; color: var(--muted); font-size: 12px; font-weight: 600; }}
    .metric span {{ display: block; margin-top: 8px; font-size: 22px; font-weight: 700; }}
    .flow {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }}
    .step {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfe; min-height: 92px; }}
    .step b {{ display: block; margin-bottom: 6px; }}
    .step small, .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: middle; }}
    th {{ color: var(--muted); font-weight: 650; }}
    .bar {{ display: inline-block; width: min(380px, 80%); height: 10px; background: #e6eaf0; border-radius: 999px; overflow: hidden; vertical-align: middle; margin-right: 8px; }}
    .bar span {{ display: block; height: 100%; background: var(--blue); border-radius: inherit; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .ok {{ color: #065f46; background: #d1fae5; }}
    .bad {{ color: #9a3412; background: #ffedd5; }}
    pre {{ white-space: pre-wrap; overflow: auto; background: #0f172a; color: #dbeafe; padding: 14px; border-radius: 8px; }}
    @media (max-width: 860px) {{ .two, .flow {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Resource Matching Evaluation Report</h1>
    <p>Task-conditioned HGT resource matching, candidate ranking, and rule verification.</p>
  </header>
  <main>
    <section>
      <h2>Evaluation Pipeline</h2>
      <div class="flow">
        <div class="step"><b>1. Resource JSON</b><small>{len(resources)} nodes, {len(edges)} edges</small></div>
        <div class="step"><b>2. HeteroData</b><small>CPU/GPU/FPGA/MEMORY/STORAGE/NIC/SWITCH</small></div>
        <div class="step"><b>3. Candidate Search</b><small>{len(candidates)} candidate subnets</small></div>
        <div class="step"><b>4. HGT Scoring</b><small>task vector + subnet embedding</small></div>
        <div class="step"><b>5. Top-K Ranking</b><small>task: {html.escape(str(top_task))}</small></div>
        <div class="step"><b>6. Verification</b><small>capacity, performance, topology, QoS</small></div>
      </div>
    </section>

    <section>
      <h2>Dataset Overview</h2>
      <div class="grid two">
        <div>
          <h3>Resource counts</h3>
          <table><tbody>{_resource_bars(resources)}</tbody></table>
        </div>
        <div>
          <h3>Data summary</h3>
          <table><tbody>
            <tr><td>tasks</td><td>{len(tasks)}</td></tr>
            <tr><td>candidates</td><td>{len(candidates)}</td></tr>
            <tr><td>splits</td><td>{html.escape(split_text)}</td></tr>
            <tr><td>edge relations</td><td>{html.escape(relation_text)}</td></tr>
          </tbody></table>
        </div>
      </div>
    </section>

    <section>
      <h2>Evaluation Metrics</h2>
      <div class="grid metrics">{_metric_cards(metrics)}</div>
    </section>

    <section>
      <h2>Metric Bars</h2>
      <table><thead><tr><th>metric</th><th>value</th></tr></thead><tbody>{_metric_bars(metrics)}</tbody></table>
    </section>

    <section>
      <h2>Top-K Candidate Ranking</h2>
      <table><thead><tr><th>rank</th><th>candidate</th><th>score</th><th>verification</th></tr></thead><tbody>{_topk_table(topk)}</tbody></table>
    </section>

    <section>
      <h2>Top-1 Details</h2>
      {_top1_details(topk)}
    </section>

    <section>
      <h2>Raw Result Snapshot</h2>
      <pre>{payload}</pre>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    """CLI entrypoint for HTML report generation."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    project_dir = Path.cwd()
    cfg = load_yaml(resolve_path(project_dir, args.config))
    paths = cfg["paths"]
    resources = _safe_load_json(resolve_path(project_dir, paths["resources"]), [])
    edges = _safe_load_json(resolve_path(project_dir, paths["edges"]), [])
    tasks = _safe_load_json(resolve_path(project_dir, paths["tasks"]), [])
    candidates = _safe_load_json(resolve_path(project_dir, paths["candidates"]), [])
    splits = _safe_load_json(resolve_path(project_dir, paths["splits"]), {})
    metrics = _safe_load_json(resolve_path(project_dir, paths["evaluation"]), {})
    topk = _safe_load_json(resolve_path(project_dir, paths["topk_results"]), {})
    output = resolve_path(project_dir, args.output or paths.get("evaluation_report", "outputs/evaluation_report.html"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(metrics, topk, resources, edges, tasks, candidates, splits), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
