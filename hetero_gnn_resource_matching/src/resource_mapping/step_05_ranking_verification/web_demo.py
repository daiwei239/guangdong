"""Interactive web demo for task-conditioned resource matching."""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import torch

from resource_mapping.step_01_resource_description.io_utils import get_device, load_json, load_yaml, resolve_path
from resource_mapping.step_02_resource_graph.graph_builder import ResourceGraphBuilder
from resource_mapping.step_03_task_expression.task_vectorizer import TaskVectorizer
from resource_mapping.step_04_candidate_gnn_matching.candidate_generator import CandidateGenerator
from resource_mapping.step_04_candidate_gnn_matching.model import TaskConditionedResourceMatcher
from resource_mapping.step_05_ranking_verification.verify import ResourceVerifier


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>异构算力资源映射 Demo</title>
  <style>
    :root {
      --bg: #f4f6f8;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #687385;
      --line: #d7dde6;
      --blue: #2563eb;
      --green: #0f766e;
      --red: #c2410c;
      --amber: #b45309;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.5 "Segoe UI", Arial, "Microsoft YaHei", sans-serif; }
    header { background: #152033; color: white; padding: 18px 24px; border-bottom: 1px solid #0b1220; }
    header h1 { margin: 0; font-size: 20px; font-weight: 650; }
    header p { margin: 4px 0 0; color: #c7d2e3; }
    main { display: grid; grid-template-columns: 390px minmax(0, 1fr); gap: 16px; max-width: 1440px; margin: 0 auto; padding: 16px; }
    section { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
    h2 { margin: 0 0 12px; font-size: 16px; }
    h3 { margin: 0 0 8px; font-size: 14px; }
    label { display: block; margin: 9px 0 4px; color: #334155; font-weight: 600; font-size: 12px; }
    input, select { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px 9px; background: white; color: var(--ink); }
    input[type="checkbox"] { width: auto; margin-right: 6px; }
    button { width: 100%; border: 0; border-radius: 6px; padding: 10px 12px; margin-top: 12px; background: var(--blue); color: white; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .6; cursor: progress; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; }
    .grid { display: grid; gap: 12px; }
    .two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .pipeline { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
    .step { border: 1px solid var(--line); background: #fbfcfe; border-radius: 8px; padding: 10px; min-height: 78px; }
    .step b { display: block; margin-bottom: 4px; }
    .step span { color: var(--muted); font-size: 12px; }
    .step.active { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(37, 99, 235, .12); }
    .metric { border: 1px solid var(--line); background: #fbfcfe; border-radius: 8px; padding: 11px; }
    .metric strong { display: block; color: var(--muted); font-size: 12px; }
    .metric span { display: block; margin-top: 4px; font-size: 20px; font-weight: 750; }
    .candidate { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 10px; background: #fff; }
    .candidate.top { border-color: #8fb3ff; background: #f7faff; }
    .candidate-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
    .badge { display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }
    .ok { color: #065f46; background: #d1fae5; }
    .bad { color: #9a3412; background: #ffedd5; }
    .warn { color: #92400e; background: #fef3c7; }
    .bar { height: 9px; background: #e6eaf0; border-radius: 999px; overflow: hidden; }
    .bar span { display: block; height: 100%; background: var(--blue); }
    .nodes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
    .nodebox { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; min-height: 48px; }
    .nodebox b { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .nodebox span { word-break: break-word; font-size: 12px; }
    .muted { color: var(--muted); }
    .error { color: var(--red); background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 10px; }
    pre { max-height: 300px; overflow: auto; background: #0f172a; color: #dbeafe; border-radius: 8px; padding: 10px; }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .pipeline, .three, .two { grid-template-columns: 1fr; }
      .nodes { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>任务条件化异构资源映射</h1>
    <p>输入任务需求，生成候选资源子网，经 HGT-GNN 打分排序，再做容量、性能、拓扑和 QoS 验证。</p>
  </header>
  <main>
    <aside class="grid">
      <section>
        <h2>任务输入</h2>
        <form id="taskForm">
          <label>任务类型</label>
          <select name="task_type">
            <option value="llm_inference">llm_inference</option>
            <option value="llm_training">llm_training</option>
            <option value="hpc_simulation">hpc_simulation</option>
            <option value="big_data">big_data</option>
            <option value="graph_analytics">graph_analytics</option>
            <option value="video_processing">video_processing</option>
            <option value="mixed">mixed</option>
          </select>
          <label>主导模式</label>
          <select name="dominant_mode">
            <option value="compute_intensive">compute_intensive</option>
            <option value="data_intensive">data_intensive</option>
            <option value="communication_intensive">communication_intensive</option>
            <option value="mixed">mixed</option>
          </select>
          <div class="grid two">
            <div><label>FP32 TFLOPS</label><input name="min_compute_tflops" type="number" step="1" value="50"></div>
            <div><label>Tensor TFLOPS</label><input name="min_tensor_tflops" type="number" step="1" value="200"></div>
            <div><label>GPU 显存 GB</label><input name="min_gpu_memory_gb" type="number" step="1" value="40"></div>
            <div><label>CPU 核数</label><input name="min_cpu_cores" type="number" step="1" value="16"></div>
            <div><label>内存 GB</label><input name="min_memory_gb" type="number" step="1" value="128"></div>
            <div><label>存储带宽 Gbps</label><input name="min_storage_bw_gbps" type="number" step="1" value="5"></div>
            <div><label>网络带宽 Gbps</label><input name="min_network_bw_gbps" type="number" step="1" value="100"></div>
            <div><label>最大延迟 us</label><input name="max_latency_us" type="number" step="1" value="30"></div>
            <div><label>最大功耗 W</label><input name="max_power_w" type="number" step="1" value="1500"></div>
            <div><label>Deadline ms</label><input name="deadline_ms" type="number" step="1" value="1000"></div>
            <div><label>优先级</label><input name="priority" type="number" min="1" max="5" step="1" value="3"></div>
            <div><label>候选数量</label><input name="max_candidates" type="number" min="1" max="50" step="1" value="20"></div>
          </div>
          <label><input name="prefer_same_node" type="checkbox" checked>偏好同节点</label>
          <label><input name="prefer_low_load" type="checkbox" checked>偏好低负载</label>
          <label><input name="prefer_low_energy" type="checkbox">偏好低能耗</label>
          <label><input name="need_rdma" type="checkbox" checked>需要 RDMA</label>
          <button id="runBtn" type="submit">运行资源映射</button>
        </form>
      </section>
      <section>
        <h2>模型状态</h2>
        <div id="status" class="muted">等待输入任务。</div>
      </section>
    </aside>
    <div class="grid">
      <section>
        <h2>执行过程</h2>
        <div class="pipeline">
          <div class="step" id="s1"><b>1. 任务向量</b><span>将表单需求编码为 q_t</span></div>
          <div class="step" id="s2"><b>2. 候选子网</b><span>按模式生成资源组合</span></div>
          <div class="step" id="s3"><b>3. 资源图编码</b><span>HeteroData + HGTConv</span></div>
          <div class="step" id="s4"><b>4. GNN 打分</b><span>任务 embedding 融合排序</span></div>
          <div class="step" id="s5"><b>5. 规则验证</b><span>容量/性能/拓扑/QoS</span></div>
        </div>
        <div class="grid three" id="summary"></div>
      </section>
      <section>
        <h2>Top-K 结果</h2>
        <div id="results" class="muted">运行后这里会显示候选资源子网排名。</div>
      </section>
      <section>
        <h2>原始结果</h2>
        <pre id="raw">{}</pre>
      </section>
    </div>
  </main>
  <script>
    const form = document.getElementById('taskForm');
    const statusEl = document.getElementById('status');
    const resultsEl = document.getElementById('results');
    const summaryEl = document.getElementById('summary');
    const rawEl = document.getElementById('raw');
    const runBtn = document.getElementById('runBtn');
    const steps = ['s1', 's2', 's3', 's4', 's5'].map(id => document.getElementById(id));

    function setActive(idx) {
      steps.forEach((el, i) => el.classList.toggle('active', i <= idx));
    }

    function formPayload() {
      const fd = new FormData(form);
      const numeric = ['min_compute_tflops', 'min_tensor_tflops', 'min_gpu_memory_gb', 'min_cpu_cores', 'min_memory_gb', 'min_storage_bw_gbps', 'min_network_bw_gbps', 'max_latency_us', 'max_power_w', 'deadline_ms', 'priority'];
      const requirements = {};
      numeric.forEach(k => requirements[k] = Number(fd.get(k) || 0));
      ['prefer_same_node', 'prefer_low_load', 'prefer_low_energy', 'need_rdma'].forEach(k => requirements[k] = fd.has(k) ? 1 : 0);
      return {
        task_type: fd.get('task_type'),
        dominant_mode: fd.get('dominant_mode'),
        max_candidates: Number(fd.get('max_candidates') || 20),
        requirements
      };
    }

    function badge(ok) {
      return ok ? '<span class="badge ok">通过</span>' : '<span class="badge bad">未通过</span>';
    }

    function nodeBoxes(nodes) {
      const order = ['cpu', 'gpu', 'fpga', 'memory', 'storage', 'nic', 'switch'];
      return `<div class="nodes">${order.map(t => {
        const value = (nodes[t] || []).join(', ') || '-';
        return `<div class="nodebox"><b>${t}</b><span>${value}</span></div>`;
      }).join('')}</div>`;
    }

    function render(data) {
      rawEl.textContent = JSON.stringify(data, null, 2);
      statusEl.innerHTML = data.model_loaded
        ? `<span class="badge ok">已加载 GNN checkpoint</span><p class="muted">${data.checkpoint}</p>`
        : `<span class="badge warn">未加载 checkpoint</span>`;
      summaryEl.innerHTML = `
        <article class="metric"><strong>候选子网</strong><span>${data.num_candidates}</span></article>
        <article class="metric"><strong>GNN 推理耗时</strong><span>${data.gnn_time_ms.toFixed(2)} ms</span></article>
        <article class="metric"><strong>Top-1 分数</strong><span>${data.top_1_subnet ? data.top_1_subnet.score.toFixed(4) : '-'}</span></article>
      `;
      const maxScore = Math.max(...data.top_n_candidates.map(x => x.score), 1e-6);
      resultsEl.innerHTML = data.top_n_candidates.map((item, idx) => `
        <article class="candidate ${idx === 0 ? 'top' : ''}">
          <div class="candidate-head">
            <div><b>#${idx + 1} ${item.candidate_id}</b><div class="muted">score ${item.score.toFixed(4)}</div></div>
            <div>${item.verified ? '<span class="badge ok">verified</span>' : '<span class="badge bad">failed</span>'}</div>
          </div>
          <div class="bar"><span style="width:${Math.max(3, item.score / maxScore * 100).toFixed(1)}%"></span></div>
          ${nodeBoxes(item.nodes)}
          <table>
            <tbody>
              <tr><td>容量</td><td>${badge(item.verification.capacity_satisfied)}</td><td>性能</td><td>${badge(item.verification.performance_satisfied)}</td></tr>
              <tr><td>拓扑</td><td>${badge(item.verification.topology_satisfied)}</td><td>QoS</td><td>${badge(item.verification.qos_satisfied)}</td></tr>
              <tr><td>违反项</td><td colspan="3">${(item.verification.violations || []).join(', ') || 'none'}</td></tr>
            </tbody>
          </table>
        </article>
      `).join('');
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      runBtn.disabled = true;
      setActive(0);
      statusEl.textContent = '正在编码任务并生成候选资源子网...';
      resultsEl.textContent = '运行中...';
      try {
        setTimeout(() => setActive(1), 120);
        setTimeout(() => setActive(2), 240);
        setTimeout(() => setActive(3), 360);
        const response = await fetch('/api/match', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(formPayload())
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'request failed');
        }
        setActive(4);
        render(data);
      } catch (err) {
        resultsEl.innerHTML = `<div class="error">${err.message}</div>`;
        statusEl.innerHTML = '<span class="badge bad">运行失败</span>';
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


class DemoState:
    """Loaded resources, graph and optional checkpoint for the demo server."""

    def __init__(self, project_dir: Path, config_path: str) -> None:
        self.project_dir = project_dir
        self.config = load_yaml(resolve_path(project_dir, config_path))
        paths = self.config["paths"]
        self.resources = load_json(resolve_path(project_dir, paths["resources"]))
        self.edges = load_json(resolve_path(project_dir, paths["edges"]))
        self.builder = ResourceGraphBuilder()
        self.data = self.builder.build(self.resources, self.edges)
        self.vectorizer = TaskVectorizer()
        self.device = get_device(self.config["device"])
        self.data = self.data.to(self.device)
        self.checkpoint_path = resolve_path(project_dir, paths["checkpoint"])
        self.model = self._load_model()
        self.generator = CandidateGenerator(self.resources, self.edges, int(self.config["seed"]))
        self.verifier = ResourceVerifier(self.resources, self.edges)

    def _load_model(self) -> TaskConditionedResourceMatcher | None:
        """Load the trained checkpoint if it exists."""

        if not self.checkpoint_path.exists():
            return None
        model = TaskConditionedResourceMatcher(
            self.data.metadata(),
            self.vectorizer.dim,
            self.config["hidden_dim"],
            self.config["num_layers"],
            self.config["num_heads"],
            self.config["dropout"],
        ).to(self.device)
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
        model.load_state_dict(checkpoint["model_state"])
        model.eval()
        return model

    def match(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate candidates, score them with the GNN, and verify Top-K."""

        if self.model is None:
            raise RuntimeError(
                "没有找到 outputs/checkpoints/best_model.pt。请先训练模型：python -m resource_mapping.step_04_candidate_gnn_matching.train --config configs/default.yaml"
            )

        task = {
            "task_id": f"web_task_{int(time.time())}",
            "task_type": payload.get("task_type", "mixed"),
            "dominant_mode": payload.get("dominant_mode", "mixed"),
            "requirements": payload.get("requirements", {}),
        }
        max_candidates = int(payload.get("max_candidates", self.config["max_candidates"]))
        top_k = int(payload.get("top_k", self.config["top_k"]))
        candidates = self.generator.generate(task, max_candidates=max_candidates)
        if not candidates:
            raise RuntimeError("没有生成候选资源子网，请检查资源 available 状态或任务需求。")

        candidate_indices = [self.builder.ids_to_indices(candidate["nodes"]) for candidate in candidates]
        task_vectors = torch.tensor([self.vectorizer.transform_one(task) for _ in candidates], dtype=torch.float, device=self.device)
        start = time.perf_counter()
        with torch.no_grad():
            _, scores = self.model(self.data, task_vectors, candidate_indices)
        gnn_time_ms = (time.perf_counter() - start) * 1000.0

        ranked = sorted(zip(candidates, scores.view(-1).detach().cpu().tolist()), key=lambda item: item[1], reverse=True)
        top_items = []
        for candidate, score in ranked[:top_k]:
            verification = self.verifier.verify(task, candidate)
            top_items.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "score": float(score),
                    "verified": not verification["violations"],
                    "nodes": candidate["nodes"],
                    "verification": verification,
                }
            )

        return {
            "task": task,
            "model_loaded": True,
            "checkpoint": str(self.checkpoint_path),
            "num_candidates": len(candidates),
            "gnn_time_ms": gnn_time_ms,
            "top_1_subnet": top_items[0] if top_items else None,
            "top_n_candidates": top_items,
        }


def make_handler(state: DemoState) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to demo state."""

    class DemoHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send(200, "text/html; charset=utf-8", HTML_PAGE.encode("utf-8"))
            else:
                self._send(404, "application/json; charset=utf-8", b'{"error":"not found"}')

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/match":
                self._send(404, "application/json; charset=utf-8", b'{"error":"not found"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = state.match(payload)
                self._send(200, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode("utf-8"))
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self._send(400, "application/json; charset=utf-8", body)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return DemoHandler


def main() -> None:
    """Run the interactive web demo."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8008)
    args = parser.parse_args()

    state = DemoState(Path.cwd(), args.config)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"demo running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
