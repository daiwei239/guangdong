import { Fragment, useEffect } from "react";
import {
  ArrowDown,
  ArrowRight,
  CheckCircle2,
  CircuitBoard,
  Cpu,
  Database,
  FileText,
  Globe2,
  Medal,
  Server,
  ShieldCheck,
  Sparkles,
  Trophy
} from "lucide-react";
import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform
} from "framer-motion";
import resourcesJson from "../../data/raw/resources.json";
import edgesJson from "../../data/raw/edges.json";

type StepTheme = "blue" | "teal";
type StepKind = "resources" | "graph" | "task" | "gnn" | "ranking";
type BackendResourceType = "cpu" | "gpu" | "fpga" | "memory" | "storage" | "nic" | "switch";

interface BackendResource {
  id: string;
  type: BackendResourceType;
  node_id?: string;
  rack_id?: string;
  switch_id?: string;
  features: Record<string, number | undefined>;
}

interface BackendEdge {
  source: string;
  target: string;
  source_type: BackendResourceType;
  target_type: BackendResourceType;
  relation: string;
}

interface StepConfig {
  id: number;
  title: string;
  tag: string;
  theme: StepTheme;
  kind: StepKind;
  description: string;
  bullets: string[];
}

const ease = [0.22, 1, 0.36, 1] as const;
const backendResources = resourcesJson as unknown as BackendResource[];
const backendEdges = edgesJson as unknown as BackendEdge[];

const steps: StepConfig[] = [
  {
    id: 1,
    title: "异构资源采集与统一描述",
    tag: "Metadata",
    theme: "blue",
    kind: "resources",
    description: "采集 CPU、GPU、FPGA、存储和网络等异构资源的静态属性、动态状态与统一元数据。",
    bullets: ["静态属性采集", "动态状态感知", "统一元数据规范"]
  },
  {
    id: 2,
    title: "异构资源图构建",
    tag: "Resource Graph",
    theme: "blue",
    kind: "graph",
    description: "将资源节点与物理连接、拓扑邻接、共享关系组织为可计算的异构资源图。",
    bullets: ["节点类型：CPU / GPU / FPGA / MEMORY / STORAGE / NIC / SWITCH", "边类型：物理连接 / 拓扑邻接 / 共享关系"]
  },
  {
    id: 3,
    title: "多模式任务需求表达",
    tag: "Task Vector",
    theme: "blue",
    kind: "task",
    description: "把训练、推理、科学计算、流处理和图计算等任务需求编码为向量 q_t。",
    bullets: ["任务类型识别", "需求向量 q_t", "容量 / 性能 / 拓扑 / QoS 约束"]
  },
  {
    id: 4,
    title: "候选资源子网搜索 + GNN 匹配",
    tag: "GNN Matching",
    theme: "teal",
    kind: "gnn",
    description: "从全局资源图搜索候选资源子网，并通过 HGTConv 进行任务条件化评分。",
    bullets: ["候选节点筛选", "邻域扩展生成子网", "HGTConv 编码", "任务条件化评分"]
  },
  {
    id: 5,
    title: "结果排序与验证输出",
    tag: "Validation",
    theme: "teal",
    kind: "ranking",
    description: "对候选资源子网进行 Top-N 排序，完成容量、性能、拓扑和 QoS 验证并输出调度建议。",
    bullets: ["Top-N 候选资源子网", "Top-1 最优资源子网", "容量 / 性能 / 拓扑 / QoS 验证", "输出调度建议"]
  }
];

const pageVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.72, ease } }
};

function App() {
  return <TechRoutePage />;
}

export function TechRoutePage() {
  const reduceMotion = useReducedMotion();

  return (
    <main className="bg-tech-grid h-screen snap-y snap-mandatory overflow-y-auto scroll-smooth text-textDeep">
      <StepProgress />

      {steps.map((step, index) => (
        <StepPage key={step.id} step={step} index={index} reduceMotion={Boolean(reduceMotion)} />
      ))}
    </main>
  );
}

function StepProgress() {
  return (
    <nav className="fixed right-5 top-1/2 z-30 hidden -translate-y-1/2 rounded-full border border-sky-200/80 bg-white/75 p-2 shadow-glass backdrop-blur-xl lg:block">
      <div className="flex flex-col gap-2">
        {steps.map((step) => (
          <a
            key={step.id}
            href={`#step-${step.id}`}
            className="grid h-9 w-9 place-items-center rounded-full border border-sky-100 bg-sky-50 text-xs font-black text-tech transition hover:border-cyanTech hover:bg-cyan-50 hover:text-cyanTech"
            aria-label={`跳转到第 ${step.id} 步`}
          >
            {step.id}
          </a>
        ))}
      </div>
    </nav>
  );
}

function StepPage({ step, index, reduceMotion }: { step: StepConfig; index: number; reduceMotion: boolean }) {
  return (
    <section
      id={`step-${step.id}`}
      className="relative flex min-h-screen snap-start items-center justify-center px-4 py-8 sm:px-6 lg:px-10"
    >
      <div className="pointer-events-none absolute left-[8%] top-20 h-2 w-2 rounded-full bg-glowBlue/35 shadow-[0_0_22px_rgba(47,140,255,0.35)]" />
      <div className="pointer-events-none absolute bottom-24 right-[13%] h-1.5 w-1.5 rounded-full bg-cyanTech/35 shadow-[0_0_18px_rgba(15,163,177,0.32)]" />

      <motion.div
        variants={pageVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: false, amount: 0.45 }}
        className="mx-auto w-full max-w-[1440px]"
      >
        {index === 0 ? (
          <motion.header
            initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.72, ease }}
            className="mx-auto mb-5 max-w-4xl text-center"
          >
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-sky-200/80 bg-white/70 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-cyanTech shadow-sm backdrop-blur-xl">
              <Sparkles className="h-3.5 w-3.5" />
              AI Infrastructure Route
            </div>
            <h1 className="text-3xl font-black tracking-tight text-navy sm:text-4xl lg:text-5xl">
              图 1 研究总体技术路线
            </h1>
            <p className="mt-3 text-base font-medium text-textSoft sm:text-lg">
              面向多模式任务的异构资源智能匹配总体流程
            </p>
            <div className="mx-auto mt-5 h-px w-72 bg-gradient-to-r from-transparent via-glowBlue to-cyanTech opacity-80" />
          </motion.header>
        ) : null}

        <ExpandedStepCard step={step} isFirst={index === 0} />

        {index < steps.length - 1 ? (
          <div className="mt-4 flex justify-center">
            <a
              href={`#step-${step.id + 1}`}
              className="group inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white/75 px-4 py-2 text-sm font-bold text-tech shadow-sm backdrop-blur-xl transition hover:border-cyanTech hover:text-cyanTech"
            >
              下一步
              <ArrowDown className="h-4 w-4 transition group-hover:translate-y-0.5" />
            </a>
          </div>
        ) : null}
      </motion.div>
    </section>
  );
}

export function ExpandedStepCard({ step, isFirst = false }: { step: StepConfig; isFirst?: boolean }) {
  const isTeal = step.theme === "teal";
  const headerClass = isTeal
    ? "from-cyanTech via-[#13B6C3] to-[#1DD1A1]"
    : "from-navy via-tech to-glowBlue";

  return (
    <motion.article
      whileHover={{
        y: -6,
        scale: 1.006,
        transition: { duration: 0.22, ease }
      }}
      className={`group hairline-highlight glass-card relative overflow-hidden rounded-2xl transition-all duration-300 hover:border-sky-300/90 hover:shadow-glassHover ${
        step.id === 4 ? "ring-1 ring-cyanTech/25 shadow-[0_22px_70px_rgba(15,163,177,0.13)]" : ""
      } ${isFirst ? "min-h-[640px]" : "min-h-[calc(100vh-120px)]"}`}
    >
      <div className={`relative overflow-hidden bg-gradient-to-br ${headerClass} px-6 py-5 text-white sm:px-8`}>
        <div className="absolute inset-0 translate-x-[-120%] bg-gradient-to-r from-transparent via-white/24 to-transparent opacity-0 transition-opacity duration-300 group-hover:animate-[arrow-shine_1.4s_ease-in-out] group-hover:opacity-100" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <motion.div
              whileHover={{ scale: 1.08 }}
              className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-white text-2xl font-black shadow-[0_8px_20px_rgba(0,0,0,0.14)]"
              style={{ color: isTeal ? "#0FA3B1" : "#0F73D9" }}
            >
              {step.id}
            </motion.div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.22em] text-white/70">
                Step {String(step.id).padStart(2, "0")} · {step.tag}
              </p>
              <h2 className="mt-1 text-2xl font-black leading-tight tracking-tight sm:text-3xl">
                {step.title}
              </h2>
            </div>
          </div>
          <span className="w-fit rounded-full bg-white/18 px-4 py-2 text-sm font-bold text-white shadow-sm backdrop-blur-xl">
            {step.id === 4 ? "核心匹配阶段" : "流程步骤"}
          </span>
        </div>
      </div>

      <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[0.86fr_1.5fr] lg:p-8">
        <aside className="flex flex-col gap-5">
          <div className="rounded-2xl border border-sky-100 bg-white/68 p-5 shadow-sm">
            <h3 className="mb-3 text-lg font-black text-navy">阶段说明</h3>
            <p className="text-base leading-8 text-textSoft">{step.description}</p>
          </div>

          <div className="rounded-2xl border border-sky-100 bg-gradient-to-br from-white/80 to-sky-50/70 p-5 shadow-sm">
            <h3 className="mb-4 text-lg font-black text-navy">关键要点</h3>
            <ul className="space-y-3 text-base leading-relaxed text-textSoft">
              {step.bullets.map((bullet) => (
                <li key={bullet} className="flex gap-3">
                  <span className={`mt-2.5 h-2 w-2 shrink-0 rounded-full ${isTeal ? "bg-cyanTech" : "bg-glowBlue"}`} />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>

          {step.id === 5 ? <OutputBar compact /> : <StepCue current={step.id} />}
        </aside>

        <div className="min-h-[430px] rounded-2xl border border-sky-100/80 bg-gradient-to-br from-white/86 to-sky-50/70 p-5 shadow-inner lg:min-h-[560px]">
          <StepVisual kind={step.kind} expanded />
        </div>
      </div>
    </motion.article>
  );
}

function StepCue({ current }: { current: number }) {
  return (
    <div className="rounded-2xl border border-sky-100 bg-white/60 p-4 text-sm font-bold text-textSoft shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <span>流程进度</span>
        <span className="font-mono text-tech">{current}/5</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-sky-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-tech to-cyanTech"
          style={{ width: `${(current / 5) * 100}%` }}
        />
      </div>
    </div>
  );
}

function StepVisual({ kind, expanded = false }: { kind: StepKind; expanded?: boolean }) {
  if (kind === "resources") return <ResourceList expanded={expanded} />;
  if (kind === "graph") return <ResourceGraph expanded={expanded} />;
  if (kind === "task") return <TaskVector expanded={expanded} />;
  if (kind === "gnn") return <GNNMatching expanded={expanded} />;
  return <RankingPanel expanded={expanded} />;
}

export function ResourceList({ expanded = false }: { expanded?: boolean }) {
  const items = [
    { label: "CPU", note: "cores / freq / queue", icon: Cpu, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "GPU", note: "tensor / vram / util", icon: CircuitBoard, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "FPGA", note: "logic / dsp / power", icon: Server, color: "text-violet-600", bg: "bg-violet-50" },
    { label: "存储", note: "bandwidth / latency", icon: Database, color: "text-sky-600", bg: "bg-sky-50" },
    { label: "网络", note: "rdma / fabric / qos", icon: Globe2, color: "text-cyan-600", bg: "bg-cyan-50" }
  ];

  return (
    <div className={`flex h-full flex-col justify-center gap-3 ${expanded ? "mx-auto max-w-2xl" : ""}`}>
      {items.map((item, index) => {
        const Icon = item.icon;
        return (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, amount: 0.4 }}
            transition={{ delay: index * 0.08, duration: 0.42, ease }}
            className={`group/row flex items-center gap-4 rounded-2xl border border-sky-100 bg-sky-50/55 px-4 transition-colors hover:bg-white ${
              expanded ? "py-5" : "py-3"
            }`}
          >
            <span className={`grid ${expanded ? "h-14 w-14" : "h-10 w-10"} place-items-center rounded-xl ${item.bg} ${item.color} transition-all group-hover/row:shadow-[0_0_18px_rgba(47,140,255,0.18)]`}>
              <Icon className={expanded ? "h-7 w-7" : "h-5 w-5"} />
            </span>
            <div>
              <strong className={`${expanded ? "text-lg" : "text-sm"} block font-black text-textDeep`}>{item.label}</strong>
              <span className={`${expanded ? "text-sm" : "text-xs"} font-medium text-textSoft`}>{item.note}</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

const graphTypeOrder: BackendResourceType[] = ["cpu", "gpu", "fpga", "memory", "storage", "nic", "switch"];
const graphTypeColors: Record<BackendResourceType, string> = {
  cpu: "#2F8CFF",
  gpu: "#22C55E",
  fpga: "#8B5CF6",
  memory: "#38BDF8",
  storage: "#F59E0B",
  nic: "#0FA3B1",
  switch: "#EAB308"
};
const graphTypeLabels: Record<BackendResourceType, string> = {
  cpu: "CPU",
  gpu: "GPU",
  fpga: "FPGA",
  memory: "MEM",
  storage: "STO",
  nic: "NIC",
  switch: "SW"
};

function uniqueBackendEdges(edgeList: BackendEdge[]) {
  const seen = new Set<string>();
  return edgeList.filter((edge) => {
    const key = [edge.source, edge.target].sort().join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildBackendResourceGraph(expanded: boolean) {
  const degree = new Map<string, number>();
  backendEdges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });

  const limits: Record<BackendResourceType, number> = expanded
    ? { cpu: 7, gpu: 7, fpga: 5, memory: 7, storage: 6, nic: 6, switch: 4 }
    : { cpu: 4, gpu: 4, fpga: 3, memory: 4, storage: 4, nic: 4, switch: 3 };

  const selectedResources = graphTypeOrder.flatMap((type) =>
    backendResources
      .filter((resource) => resource.type === type)
      .sort((a, b) => {
        const byDegree = (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0);
        if (byDegree !== 0) return byDegree;
        return a.id.localeCompare(b.id);
      })
      .slice(0, limits[type])
  );

  const selectedIds = new Set(selectedResources.map((resource) => resource.id));
  const grouped = new Map<BackendResourceType, BackendResource[]>();
  graphTypeOrder.forEach((type) => grouped.set(type, []));
  selectedResources.forEach((resource) => grouped.get(resource.type)?.push(resource));

  const columnX = [76, 216, 356, 496, 636, 776, 916];
  const nodes = graphTypeOrder.flatMap((type, columnIndex) => {
    const group = grouped.get(type) ?? [];
    const availableHeight = 410;
    const startY = 78;
    const gap = group.length > 1 ? availableHeight / (group.length - 1) : 0;
    return group.map((resource, rowIndex) => {
      const utilization = resource.features.utilization ?? 0.35;
      const available = resource.features.available ?? 1;
      return {
        ...resource,
        label: graphTypeLabels[type],
        color: graphTypeColors[type],
        radius: 16 + Math.max(0, 1 - utilization) * 5 + available * 2,
        x: columnX[columnIndex],
        y: startY + rowIndex * gap + (columnIndex % 2 ? 12 : 0)
      };
    });
  });

  const edges = uniqueBackendEdges(
    backendEdges.filter((edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target))
  )
    .sort((a, b) => {
      if (a.relation === b.relation) return a.source.localeCompare(b.source);
      if (a.relation === "same_node") return -1;
      if (b.relation === "same_node") return 1;
      return a.relation.localeCompare(b.relation);
    })
    .slice(0, expanded ? 90 : 45);

  return {
    nodes,
    edges,
    typeStats: graphTypeOrder.map((type) => ({
      type,
      label: graphTypeLabels[type],
      color: graphTypeColors[type],
      count: grouped.get(type)?.length ?? 0
    }))
  };
}

export function ResourceGraph({ expanded = false }: { expanded?: boolean }) {
  const graph = buildBackendResourceGraph(expanded);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="grid grid-cols-4 gap-2 text-xs font-bold text-textSoft sm:grid-cols-7">
        {graph.typeStats.map((item) => (
          <div key={item.type} className="rounded-xl border border-sky-100 bg-white/70 px-2 py-2 text-center shadow-sm">
            <span className="block font-black" style={{ color: item.color }}>{item.label}</span>
            <span>{item.count} 节点</span>
          </div>
        ))}
      </div>

      <svg viewBox="0 0 1000 560" className="min-h-0 flex-1 rounded-2xl border border-sky-100 bg-white/45" role="img" aria-label="backend heterogeneous resource graph">
      <defs>
        <filter id="nodeGlow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="backendEdge" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#0F73D9" stopOpacity="0.25" />
          <stop offset="55%" stopColor="#2F8CFF" stopOpacity="0.88" />
          <stop offset="100%" stopColor="#0FA3B1" stopOpacity="0.28" />
        </linearGradient>
      </defs>
      <rect x="20" y="22" width="960" height="516" rx="22" fill="none" stroke="#D8EAFB" strokeDasharray="8 12" />
      {graph.edges.map((edge, index) => {
        const source = byId.get(edge.source);
        const target = byId.get(edge.target);
        if (!source || !target) return null;
        const dashed = edge.relation !== "same_node";
        return (
          <line
            key={`${edge.source}-${edge.target}-${edge.relation}`}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            className="flow-line"
            stroke={dashed ? "#8FBDEB" : "url(#backendEdge)"}
            strokeWidth={expanded ? (edge.relation === "same_node" ? "2.8" : "1.7") : "1.4"}
            strokeLinecap="round"
            strokeDasharray={dashed ? "5 7" : "9 7"}
            opacity={edge.relation === "same_node" ? "0.78" : "0.48"}
            style={{ animationDelay: `${(index % 7) * 0.12}s` }}
          />
        );
      })}
      {graph.nodes.map((node, index) => (
        <motion.g
          key={node.id}
          initial={{ opacity: 0, scale: 0.78 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: false, amount: 0.4 }}
          transition={{ delay: index * 0.08, duration: 0.45, ease }}
          whileHover={{ scale: 1.13 }}
          className={index % 2 === 0 ? "soft-float cursor-pointer" : "cursor-pointer"}
          style={{ transformOrigin: `${node.x}px ${node.y}px` }}
        >
          <circle cx={node.x} cy={node.y} r={node.radius + 8} fill={node.color} opacity="0.14" filter="url(#nodeGlow)" />
          <circle cx={node.x} cy={node.y} r={node.radius} fill={node.color} stroke="#fff" strokeWidth="3" />
          <text x={node.x} y={node.y + 3} textAnchor="middle" fill="#fff" fontSize={expanded ? "9" : "8"} fontWeight="900">
            {node.label}
          </text>
          <text x={node.x} y={node.y + node.radius + 14} textAnchor="middle" fill="#5D6B82" fontSize="9" fontWeight="800">
            {node.id.replace("_", " ")}
          </text>
          <title>{`${node.id} · ${node.type} · ${node.rack_id ?? "no rack"}`}</title>
        </motion.g>
      ))}
      </svg>
      <div className="flex flex-wrap gap-2 text-xs font-semibold text-textSoft">
        <span className="rounded-full bg-sky-50 px-3 py-1">数据源：data/raw/resources.json</span>
        <span className="rounded-full bg-cyan-50 px-3 py-1">真实边：data/raw/edges.json</span>
        <span className="rounded-full bg-white px-3 py-1">当前渲染：{graph.nodes.length} 节点 / {graph.edges.length} 边</span>
      </div>
    </div>
  );
}

export function TaskVector({ expanded = false }: { expanded?: boolean }) {
  const features = ["容量", "性能", "拓扑", "QoS", "时延", "能耗", "优先级", "亲和性"];

  return (
    <div className="flex h-full flex-col justify-center gap-6">
      <div className="rounded-2xl border border-sky-100 bg-white/80 p-5 shadow-sm">
        <div className="flex items-center gap-4">
          <div className={`${expanded ? "h-16 w-16" : "h-12 w-12"} grid shrink-0 grid-cols-2 gap-1 rounded-xl bg-gradient-to-br from-tech to-cyanTech p-2`}>
            {[0, 1, 2, 3].map((item) => (
              <span key={item} className="rounded bg-white/80" />
            ))}
          </div>
          <div>
            <strong className={`${expanded ? "text-xl" : "text-sm"} block font-black text-navy`}>任务 Task_t</strong>
            <span className={`${expanded ? "text-base" : "text-xs"} font-medium text-textSoft`}>训练 / 推理 / 科学计算 / 流处理 / 图计算</span>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-sky-100 bg-sky-50/70 p-5">
        <div className={`${expanded ? "text-xl" : "text-sm"} mb-4 font-mono font-black text-navy`}>q_t = [q1, q2, ..., qd]</div>
        <div className="grid grid-cols-8 gap-2">
          {features.map((feature, index) => (
            <motion.div
              key={feature}
              initial={{ opacity: 0, scaleY: 0.2 }}
              whileInView={{ opacity: 1, scaleY: 1 }}
              viewport={{ once: false, amount: 0.4 }}
              transition={{ delay: index * 0.07, duration: 0.42, ease }}
              className={`${expanded ? "h-28" : "h-16"} group/vector relative origin-bottom rounded-xl border border-white bg-gradient-to-t from-cyanTech via-glowBlue to-sky-100 shadow-sm`}
            >
              <span className="absolute -top-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-navy px-2 py-1 text-[10px] font-bold text-white shadow-lg group-hover/vector:block">
                {feature}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function GNNMatching({ expanded = false }: { expanded?: boolean }) {
  return (
    <div className="flex h-full flex-col justify-center gap-5">
      <div className="grid flex-1 grid-cols-[1fr_52px_1fr] items-center gap-4">
        <MiniNetwork muted expanded={expanded} />
        <div className="relative h-12 overflow-hidden rounded-full bg-gradient-to-r from-tech to-cyanTech text-white shadow-sm">
          <ArrowRight className="absolute left-1/2 top-1/2 h-6 w-6 -translate-x-1/2 -translate-y-1/2" />
          <span className="arrow-shine absolute inset-y-0 w-12 bg-gradient-to-r from-transparent via-white/55 to-transparent" />
        </div>
        <div className="rounded-2xl border border-dashed border-cyanTech/70 bg-cyan-50/70 p-3">
          <MiniNetwork compact expanded={expanded} />
        </div>
      </div>

      <div className="grid grid-cols-[1fr_64px] gap-4 rounded-2xl border border-sky-100 bg-white/70 p-5">
        <svg viewBox="0 0 210 112" className={`${expanded ? "h-48" : "h-28"} w-full`} role="img" aria-label="gnn encoder">
          {[24, 48, 72, 96].map((y) => (
            <circle key={`in-${y}`} cx="24" cy={y} r="7" fill="#2F8CFF" />
          ))}
          {[34, 56, 78].map((y) => (
            <circle key={`hid1-${y}`} cx="88" cy={y} r="8" fill="#fff" stroke="#0F73D9" strokeWidth="2" />
          ))}
          {[44, 68].map((y) => (
            <circle key={`hid2-${y}`} cx="145" cy={y} r="8" fill="#E8FAFC" stroke="#0FA3B1" strokeWidth="2" />
          ))}
          <circle cx="190" cy="56" r="10" fill="#0FA3B1" />
          {[24, 48, 72, 96].flatMap((a) => [34, 56, 78].map((b) => (
            <line key={`${a}-${b}`} x1="31" y1={a} x2="80" y2={b} stroke="#B7D7F7" strokeWidth="1" />
          )))}
          {[34, 56, 78].flatMap((a) => [44, 68].map((b) => (
            <line key={`${a}-${b}`} x1="96" y1={a} x2="137" y2={b} stroke="#B7D7F7" strokeWidth="1" />
          )))}
          {[44, 68].map((y) => (
            <line key={y} x1="153" y1={y} x2="180" y2="56" stroke="#0FA3B1" strokeWidth="1.6" />
          ))}
          <text x="105" y="108" textAnchor="middle" fill="#5D6B82" fontSize="10" fontWeight="700">HGTConv + q_t</text>
        </svg>
        <div className="flex flex-col items-center justify-center gap-2">
          <span className="text-[10px] font-black text-textSoft">score</span>
          <div className={`${expanded ? "h-36" : "h-24"} relative w-6 overflow-hidden rounded-full bg-sky-100`}>
            <div className="score-fill absolute bottom-0 h-[82%] w-full rounded-full bg-gradient-to-t from-cyanTech to-sky-200" />
          </div>
          <span className="font-mono text-sm font-black text-cyanTech">0.92</span>
        </div>
      </div>
    </div>
  );
}

function MiniNetwork({ compact = false, muted = false, expanded = false }: { compact?: boolean; muted?: boolean; expanded?: boolean }) {
  const nodes = compact
    ? [
        { x: 28, y: 36, c: "#2F8CFF" },
        { x: 72, y: 28, c: "#22C55E" },
        { x: 76, y: 74, c: "#0FA3B1" },
        { x: 124, y: 52, c: "#F59E0B" }
      ]
    : [
        { x: 18, y: 24, c: "#2F8CFF" },
        { x: 56, y: 18, c: "#22C55E" },
        { x: 98, y: 34, c: "#8B5CF6" },
        { x: 40, y: 70, c: "#38BDF8" },
        { x: 114, y: 82, c: "#0FA3B1" },
        { x: 150, y: 45, c: "#F59E0B" }
      ];

  return (
    <svg viewBox="0 0 168 100" className={`${expanded ? "h-40" : "h-24"} w-full ${muted ? "opacity-60" : ""}`}>
      {nodes.slice(1).map((node, index) => (
        <line key={index} x1={nodes[0].x} y1={nodes[0].y} x2={node.x} y2={node.y} stroke="#8FBDEB" strokeWidth="1.5" strokeDasharray={index % 2 ? "5 5" : undefined} />
      ))}
      {nodes.map((node, index) => (
        <circle key={index} cx={node.x} cy={node.y} r={compact ? 8 : 7} fill={node.c} stroke="#fff" strokeWidth="2" />
      ))}
    </svg>
  );
}

export function RankingPanel({ expanded = false }: { expanded?: boolean }) {
  const rows = [
    { rank: 1, score: 0.92, color: "text-amber-500" },
    { rank: 2, score: 0.85, color: "text-slate-400" },
    { rank: 3, score: 0.76, color: "text-orange-500" },
    { rank: "N", score: 0.32, color: "text-sky-500" }
  ];
  const checks = ["容量验证", "性能验证", "拓扑验证", "QoS 验证"];

  return (
    <div className="flex h-full flex-col justify-center gap-5">
      <div className="space-y-3">
        {rows.map((row, index) => (
          <motion.div
            key={row.rank}
            initial={{ opacity: 0, x: 14 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, amount: 0.4 }}
            transition={{ delay: index * 0.1, duration: 0.45, ease }}
            className={`grid grid-cols-[48px_1fr_72px] items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 px-4 shadow-sm ${
              expanded ? "py-4" : "py-2"
            } ${index === 0 ? "shadow-[0_0_22px_rgba(245,158,11,0.14)]" : ""}`}
          >
            <span className="grid h-10 w-10 place-items-center rounded-full bg-sky-50">
              {index < 3 ? <Medal className={`h-5 w-5 ${row.color}`} /> : <Trophy className="h-5 w-5 text-sky-500" />}
            </span>
            <span className={`${expanded ? "text-base" : "text-xs"} flex items-center gap-2 font-black text-textDeep`}>
              第 {row.rank} 名
              <MiniSubnetIcon />
            </span>
            <AnimatedScore value={row.score} />
          </motion.div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {checks.map((check, index) => (
          <motion.div
            key={check}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, amount: 0.4 }}
            transition={{ delay: 0.42 + index * 0.09, duration: 0.38, ease }}
            className={`${expanded ? "py-4 text-base" : "py-2 text-xs"} flex items-center gap-2 rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 font-bold text-emerald-700`}
          >
            <motion.span initial={{ scale: 0.8 }} whileInView={{ scale: 1 }} transition={{ delay: 0.5 + index * 0.09 }}>
              <CheckCircle2 className="h-5 w-5" />
            </motion.span>
            {check}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function MiniSubnetIcon() {
  return (
    <svg viewBox="0 0 42 18" className="h-5 w-11">
      <line x1="8" y1="9" x2="21" y2="5" stroke="#B7D7F7" strokeWidth="1.3" />
      <line x1="21" y1="5" x2="34" y2="11" stroke="#0FA3B1" strokeWidth="1.3" />
      <circle cx="8" cy="9" r="4" fill="#2F8CFF" />
      <circle cx="21" cy="5" r="4" fill="#22C55E" />
      <circle cx="34" cy="11" r="4" fill="#0FA3B1" />
    </svg>
  );
}

function AnimatedScore({ value }: { value: number }) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (latest) => latest.toFixed(2));

  useEffect(() => {
    const controls = animate(count, value, { duration: 1, ease });
    return controls.stop;
  }, [count, value]);

  return <motion.span className="font-mono text-sm font-black text-cyanTech">{rounded}</motion.span>;
}

export function OutputBar({ compact = false }: { compact?: boolean }) {
  return (
    <motion.footer
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: false, amount: 0.4 }}
      transition={{ delay: 0.2, duration: 0.62, ease }}
      className={`glass-card hairline-highlight flex items-center gap-4 rounded-2xl px-5 py-4 transition-all duration-300 hover:border-sky-300 hover:shadow-glassHover ${
        compact ? "" : "mt-8"
      }`}
    >
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-sky-50 to-cyan-50 text-tech">
        <FileText className="h-6 w-6" />
      </span>
      <div className="text-sm leading-relaxed text-textSoft sm:text-base">
        <strong className="font-black text-tech">输出：</strong>
        候选资源子网、最优映射结果、匹配评分、验证结果
      </div>
      <ShieldCheck className="ml-auto hidden h-6 w-6 text-cyanTech sm:block" />
    </motion.footer>
  );
}

export default App;
