import { useMemo, useState } from "react";

type StepId = 1 | 2 | 3 | 4 | 5;

interface StepDefinition {
  id: StepId;
  title: string;
  subtitle: string;
  bullets: string[];
  accent: "blue" | "violet" | "green" | "teal" | "slate";
}

const steps: StepDefinition[] = [
  {
    id: 1,
    title: "异构资源采集与统一描述",
    subtitle: "采集静态属性、动态状态和统一元数据",
    bullets: ["CPU / GPU / FPGA", "Memory / Storage / NIC / Switch", "利用率、功耗、队列、available"],
    accent: "blue"
  },
  {
    id: 2,
    title: "异构资源 DAG 构建",
    subtitle: "把资源节点和拓扑关系组织为有向无环图",
    bullets: ["节点类型编码", "物理连接 / 拓扑邻接 / 共享关系", "HeteroData 全局资源图"],
    accent: "violet"
  },
  {
    id: 3,
    title: "多模式任务需求表达",
    subtitle: "将任务需求转为固定维度向量 q_t",
    bullets: ["任务类型识别", "算力 / 显存 / 网络 / QoS 约束", "任务向量进入 TaskEncoder"],
    accent: "green"
  },
  {
    id: 4,
    title: "候选资源子网搜索 + GNN 匹配",
    subtitle: "从 DAG 中拎出候选子网，再经 HGT-GNN 打分",
    bullets: ["候选节点筛选", "邻域扩展生成子网", "HGTConv 编码 + 任务条件化评分"],
    accent: "teal"
  },
  {
    id: 5,
    title: "结果排序与验证输出",
    subtitle: "输出 Top-N、Top-1、匹配评分和验证结果",
    bullets: ["Top-N 候选资源子网", "容量 / 性能 / 拓扑 / QoS 验证", "最终映射结果和调度建议"],
    accent: "slate"
  }
];

function ResourceCollectionVisual() {
  const resources = [
    ["CPU", "32 cores", "82% available"],
    ["GPU", "80GB VRAM", "0.94 score"],
    ["FPGA", "DSP blocks", "low power"],
    ["MEMORY", "512GB", "NUMA aware"],
    ["STORAGE", "12Gbps", "NVMe"],
    ["NIC", "200Gbps", "RDMA"],
    ["SWITCH", "800Gbps", "rack fabric"]
  ];

  return (
    <div className="resource-list">
      {resources.map(([name, spec, note]) => (
        <div className="resource-row" key={name}>
          <span className={`resource-icon ${name.toLowerCase()}`}>{name.slice(0, 2)}</span>
          <strong>{name}</strong>
          <span>{spec}</span>
          <small>{note}</small>
        </div>
      ))}
    </div>
  );
}

function ResourceDagVisual() {
  return (
    <svg className="step-svg" viewBox="0 0 620 360" role="img" aria-label="resource dag">
      <defs>
        <marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
        </marker>
      </defs>
      {[
        [120, 90, 310, 180],
        [120, 180, 310, 180],
        [120, 270, 310, 180],
        [310, 180, 500, 130],
        [310, 180, 500, 230],
        [500, 130, 560, 180],
        [500, 230, 560, 180]
      ].map(([x1, y1, x2, y2], index) => (
        <line key={index} x1={x1} y1={y1} x2={x2} y2={y2} className="dag-edge" markerEnd="url(#dag-arrow)" />
      ))}
      <DagNode x={120} y={90} label="CPU" type="cpu" />
      <DagNode x={120} y={180} label="GPU" type="gpu" />
      <DagNode x={120} y={270} label="MEM" type="memory" />
      <DagNode x={310} y={180} label="NIC" type="nic" />
      <DagNode x={500} y={130} label="STO" type="storage" />
      <DagNode x={500} y={230} label="FPGA" type="fpga" />
      <DagNode x={560} y={180} label="SW" type="switch" />
      <text x="310" y="42" textAnchor="middle" className="svg-title">全局异构资源 DAG</text>
      <text x="310" y="324" textAnchor="middle" className="svg-caption">边表示 same_node / pcie_connect / network_connect / storage_connect 等关系</text>
    </svg>
  );
}

function DagNode({ x, y, label, type }: { x: number; y: number; label: string; type: string }) {
  return (
    <g>
      <circle cx={x} cy={y} r="34" className={`dag-node ${type}`} />
      <text x={x} y={y + 5} textAnchor="middle" className="dag-label">{label}</text>
    </g>
  );
}

function TaskVectorVisual() {
  const bars = [0.92, 0.76, 0.48, 0.84, 0.35, 0.66, 0.58, 0.71];

  return (
    <div className="task-vector">
      <div className="task-card">
        <span className="task-mark">T</span>
        <div>
          <strong>Task_t: LLM inference</strong>
          <p>compute_intensive, need_rdma, prefer_same_node</p>
        </div>
      </div>
      <div className="vector-arrow">↓</div>
      <div className="vector-strip">
        {bars.map((value, index) => (
          <div className="vector-cell" key={index} style={{ height: `${42 + value * 42}px` }}>
            <span>q{index + 1}</span>
          </div>
        ))}
      </div>
      <p className="visual-note">任务需求被编码为 q_t，随后进入 TaskEncoder，而不是作为图节点输入。</p>
    </div>
  );
}

function CandidateGnnVisual() {
  return (
    <div className="candidate-gnn">
      <div className="mini-panel">
        <h4>全局资源图</h4>
        <MiniGraph muted />
      </div>
      <div className="extract-arrow">→</div>
      <div className="mini-panel selected">
        <h4>候选资源子网</h4>
        <MiniGraph />
      </div>
      <div className="gnn-panel">
        <h4>HGTConv + Task Fusion</h4>
        <svg viewBox="0 0 300 170" className="gnn-svg" role="img" aria-label="gnn scoring">
          {[30, 60, 90, 120].map((y) => <circle key={`in-${y}`} cx="40" cy={y} r="9" className="gnn-input" />)}
          {[45, 80, 115].map((y) => <circle key={`hid-${y}`} cx="145" cy={y} r="11" className="gnn-hidden" />)}
          {[65, 100].map((y) => <circle key={`out-${y}`} cx="245" cy={y} r="10" className="gnn-output" />)}
          {[30, 60, 90, 120].flatMap((y1) =>
            [45, 80, 115].map((y2) => <line key={`${y1}-${y2}`} x1="49" y1={y1} x2="134" y2={y2} className="gnn-line" />)
          )}
          {[45, 80, 115].flatMap((y1) =>
            [65, 100].map((y2) => <line key={`${y1}-${y2}`} x1="156" y1={y1} x2="235" y2={y2} className="gnn-line" />)
          )}
          <rect x="260" y="42" width="18" height="86" rx="5" className="score-bar-bg" />
          <rect x="260" y="58" width="18" height="70" rx="5" className="score-bar-fill" />
          <text x="150" y="154" textAnchor="middle" className="svg-caption">score = σ(MLP([subgraph, task, product, diff]))</text>
        </svg>
      </div>
    </div>
  );
}

function MiniGraph({ muted = false }: { muted?: boolean }) {
  return (
    <svg viewBox="0 0 220 150" className={muted ? "mini-graph muted-graph" : "mini-graph"} role="img" aria-label="candidate subnet">
      <line x1="42" y1="46" x2="106" y2="75" />
      <line x1="42" y1="106" x2="106" y2="75" />
      <line x1="106" y1="75" x2="178" y2="46" />
      <line x1="106" y1="75" x2="178" y2="106" />
      <circle cx="42" cy="46" r="18" className="cpu" />
      <circle cx="42" cy="106" r="18" className="gpu" />
      <circle cx="106" cy="75" r="18" className="nic" />
      <circle cx="178" cy="46" r="18" className="storage" />
      <circle cx="178" cy="106" r="18" className="switch" />
    </svg>
  );
}

function RankingVisual() {
  const rows: Array<[string, string, string, boolean]> = [
    ["#1", "cand_003", "0.932", true],
    ["#2", "cand_007", "0.881", true],
    ["#3", "cand_012", "0.764", false],
    ["#N", "cand_019", "0.320", false]
  ];
  const checks = ["容量验证", "性能验证", "拓扑验证", "QoS 验证"];

  return (
    <div className="ranking-visual">
      <table className="rank-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>候选子网</th>
            <th>GNN 分数</th>
            <th>验证</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([rank, subnet, score, ok]) => (
            <tr key={String(rank)}>
              <td><strong>{rank}</strong></td>
              <td>{subnet}</td>
              <td>{score}</td>
              <td><span className={ok ? "pill ok" : "pill warn"}>{ok ? "通过" : "待修正"}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="verify-list">
        {checks.map((item) => (
          <div key={item}><span>✓</span>{item}</div>
        ))}
      </div>
    </div>
  );
}

function StepVisual({ stepId }: { stepId: StepId }) {
  switch (stepId) {
    case 1:
      return <ResourceCollectionVisual />;
    case 2:
      return <ResourceDagVisual />;
    case 3:
      return <TaskVectorVisual />;
    case 4:
      return <CandidateGnnVisual />;
    case 5:
      return <RankingVisual />;
  }
}

function App() {
  const [revealedStep, setRevealedStep] = useState(0);
  const [selectedStep, setSelectedStep] = useState<StepId | null>(null);

  const activeStep = useMemo(
    () => steps.find((step) => step.id === selectedStep) ?? null,
    [selectedStep]
  );

  const revealStep = (stepId: StepId) => {
    if (stepId > revealedStep + 1) return;
    setRevealedStep(Math.max(revealedStep, stepId));
    setSelectedStep(stepId);
  };

  const nextStep = () => {
    const next = Math.min(revealedStep + 1, steps.length) as StepId;
    revealStep(next);
  };

  const reset = () => {
    setRevealedStep(0);
    setSelectedStep(null);
  };

  return (
    <main className="roadmap-shell">
      <header className="roadmap-header">
        <div>
          <strong>图 1</strong>
          <h1>研究总体技术路线</h1>
          <p>面向多模式任务的异构资源智能匹配总体流程</p>
        </div>
        <div className="controls">
          <button type="button" onClick={reset}>重置</button>
          <button type="button" className="primary" onClick={nextStep} disabled={revealedStep >= steps.length}>
            显示下一步
          </button>
        </div>
      </header>

      <nav className="step-nav" aria-label="visualization steps">
        {steps.map((step) => {
          const isRevealed = step.id <= revealedStep;
          const isNext = step.id === revealedStep + 1;
          const isSelected = step.id === selectedStep;
          return (
            <button
              type="button"
              key={step.id}
              className={`step-chip ${isRevealed ? "revealed" : ""} ${isNext ? "next" : ""} ${isSelected ? "selected" : ""}`}
              onClick={() => revealStep(step.id)}
              disabled={!isRevealed && !isNext}
            >
              <span>{step.id}</span>
              {step.title}
            </button>
          );
        })}
      </nav>

      <section className="roadmap-grid">
        {steps.map((step) => {
          const visible = step.id <= revealedStep;
          const current = step.id === selectedStep;
          return (
            <article key={step.id} className={`route-card ${step.accent} ${visible ? "visible" : "locked"} ${current ? "current" : ""}`}>
              <div className="card-head">
                <span className="step-number">{step.id}</span>
                <h2>{step.title}</h2>
              </div>
              {visible ? (
                <>
                  <p>{step.subtitle}</p>
                  <div className="card-visual">
                    <StepVisual stepId={step.id} />
                  </div>
                  <ul>
                    {step.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                  </ul>
                </>
              ) : (
                <div className="locked-state">
                  <span>待生成</span>
                  <small>点击“显示下一步”后出现</small>
                </div>
              )}
            </article>
          );
        })}
      </section>

      <section className="detail-panel">
        {activeStep ? (
          <>
            <div className="detail-copy">
              <span className={`detail-badge ${activeStep.accent}`}>STEP {activeStep.id}</span>
              <h2>{activeStep.title}</h2>
              <p>{activeStep.subtitle}</p>
            </div>
            <div className="detail-visual">
              <StepVisual stepId={activeStep.id} />
            </div>
          </>
        ) : (
          <div className="empty-state">
            <h2>从第 1 步开始</h2>
            <p>点击“显示下一步”，系统会按流程逐步展开，不会一次性展示最终结果。</p>
          </div>
        )}
      </section>

      <footer className={`output-strip ${revealedStep === 5 ? "ready" : ""}`}>
        <strong>输出：</strong>
        {revealedStep === 5 ? "候选资源子网、最优映射结果、匹配评分、验证结果" : "等待完成第 5 步后生成最终输出"}
      </footer>
    </main>
  );
}

export default App;
