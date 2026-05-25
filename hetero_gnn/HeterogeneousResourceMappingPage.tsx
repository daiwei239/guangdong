import React, { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Binary,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircuitBoard,
  Cpu,
  Gauge,
  HardDrive,
  Minus,
  Network,
  Orbit,
  Plus,
  Radio,
  Search,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";

type TaskMode = "计算密集型" | "数据密集型" | "通信密集型" | "混合型";
type NodeType = "CPU" | "GPU" | "FPGA" | "MEMORY" | "STORAGE" | "NIC" | "SWITCH";
type StepId = 1 | 2 | 3 | 4 | 5;
type DetailTab = "概览" | "输入" | "处理" | "输出";
type Rng = () => number;

type Snapshot = {
  avgUtilization: number;
  networkBandwidth: number;
  gpuNodes: number;
  cpuNodes: number;
  fpgaNodes: number;
  memoryNodes: number;
  storageNodes: number;
};

type TaskProfile = {
  taskType: TaskMode;
  dagNodes: number;
  memoryDemand: string;
  qos: string;
  demandBars: number[];
};

type GraphNode = {
  id: string;
  type: NodeType;
  cluster: "A" | "B" | "C" | "G";
  label: string;
  x: number;
  y: number;
  utilization: number;
  capacity: string;
  bandwidth: string;
  latency: string;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

type CandidateSubnet = {
  id: string;
  rank: number;
  score: number;
  nodes: string[];
  metrics: {
    capacity: number;
    performance: number;
    topology: number;
    qos: number;
  };
};

type SimData = {
  seed: number;
  snapshot: Snapshot;
  task: TaskProfile;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  embeddingBars: number[];
  candidates: CandidateSubnet[];
  bestCandidateId: string;
};

type StepMeta = {
  id: StepId;
  shortTitle: string;
  caption: string;
  title: string;
  input: string;
  process: string;
  output: string;
  keywords: string[];
};

const stepMetas: StepMeta[] = [
  {
    id: 1,
    shortTitle: "元数据采集",
    caption: "采集并标准化资源状态",
    title: "异构资源元数据采集与标准化",
    input: "资源原始状态",
    process: "采集静态属性、运行状态、拓扑信息",
    output: "标准化资源元数据与资源属性向量 xr",
    keywords: ["资源采集", "状态感知", "属性向量"],
  },
  {
    id: 2,
    shortTitle: "资源图构建",
    caption: "统一对象与关系建模",
    title: "统一资源描述模型与资源图构建",
    input: "标准化资源元数据",
    process: "资源抽象为节点，关系抽象为边",
    output: "异构资源图 GR",
    keywords: ["统一资源描述", "资源节点", "关系边", "全局资源视图"],
  },
  {
    id: 3,
    shortTitle: "任务需求表达",
    caption: "形成任务需求向量 qt",
    title: "多模式任务需求提取与约束表达",
    input: "任务类型、DAG、Profile、QoS",
    process: "提取计算、内存、存储、网络需求",
    output: "任务需求向量 qt 与搜索约束",
    keywords: ["任务画像", "需求向量", "容量约束", "QoS 约束"],
  },
  {
    id: 4,
    shortTitle: "图表示学习",
    caption: "编码节点与子图表示",
    title: "资源图表示学习",
    input: "异构资源图 GR",
    process: "HeteroGNN / GAT / R-GCN 消息传递",
    output: "节点嵌入与子图嵌入",
    keywords: ["图神经网络", "节点嵌入", "子图表示", "结构感知"],
  },
  {
    id: 5,
    shortTitle: "子网搜索验证",
    caption: "生成候选并完成匹配评分",
    title: "候选资源子网搜索与匹配验证",
    input: "任务需求向量、资源图、子图表示",
    process: "候选筛选、邻域扩展、评分排序、约束验证",
    output: "Top-N 候选子网、Top-1 最优子网、匹配评分",
    keywords: ["子网搜索", "Top-N", "匹配评分", "QoS 验证"],
  },
];

const clusterZones: Record<"A" | "B" | "C", { xMin: number; xMax: number; yMin: number; yMax: number; cols: number }> = {
  A: { xMin: 9, xMax: 29, yMin: 18, yMax: 67, cols: 3 },
  B: { xMin: 33, xMax: 56, yMin: 18, yMax: 67, cols: 4 },
  C: { xMin: 63, xMax: 92, yMin: 18, yMax: 67, cols: 4 },
};

const typeColors: Record<NodeType, string> = {
  CPU: "from-sky-500/20 to-sky-100/80",
  GPU: "from-cyan-500/22 to-blue-100/80",
  FPGA: "from-violet-500/22 to-fuchsia-100/75",
  MEMORY: "from-indigo-500/20 to-sky-100/80",
  STORAGE: "from-teal-500/20 to-cyan-100/80",
  NIC: "from-emerald-500/20 to-cyan-100/80",
  SWITCH: "from-blue-500/20 to-violet-100/80",
};

const taskHighlightMap: Record<TaskMode, NodeType[]> = {
  计算密集型: ["GPU", "FPGA", "CPU"],
  数据密集型: ["STORAGE", "MEMORY"],
  通信密集型: ["NIC", "SWITCH"],
  混合型: ["CPU", "GPU", "MEMORY", "NIC"],
};

const initialTabs: Record<StepId, DetailTab> = {
  1: "概览",
  2: "概览",
  3: "概览",
  4: "概览",
  5: "概览",
};

function mulberry32(seed: number): Rng {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

function randomInt(rng: Rng, min: number, max: number) {
  return Math.floor(rng() * (max - min + 1)) + min;
}

function randomFloat(rng: Rng, min: number, max: number, digits = 1) {
  return Number((rng() * (max - min) + min).toFixed(digits));
}

function randomItem<T>(rng: Rng, items: T[]): T {
  return items[Math.floor(rng() * items.length)];
}

function sampleUnique<T>(rng: Rng, items: T[], count: number) {
  const pool = [...items];
  const result: T[] = [];
  while (pool.length && result.length < count) {
    const index = randomInt(rng, 0, pool.length - 1);
    result.push(pool.splice(index, 1)[0]);
  }
  return result;
}

function getNodeIcon(type: NodeType) {
  switch (type) {
    case "CPU":
      return Cpu;
    case "GPU":
      return CircuitBoard;
    case "FPGA":
      return Binary;
    case "MEMORY":
      return Orbit;
    case "STORAGE":
      return HardDrive;
    case "NIC":
      return Radio;
    default:
      return Network;
  }
}

function buildClusterPoints(
  rng: Rng,
  zone: { xMin: number; xMax: number; yMin: number; yMax: number; cols: number },
  count: number,
) {
  const points: { x: number; y: number }[] = [];
  const rows = Math.max(1, Math.ceil(count / zone.cols));
  const xStep = (zone.xMax - zone.xMin) / Math.max(zone.cols - 1, 1);
  const yStep = (zone.yMax - zone.yMin) / Math.max(rows - 1, 1);

  for (let index = 0; index < count; index += 1) {
    const col = index % zone.cols;
    const row = Math.floor(index / zone.cols);
    const xBase = zone.xMin + col * xStep;
    const yBase = zone.yMin + row * yStep;
    const xJitter = randomFloat(rng, -2.6, 2.6, 2);
    const yJitter = randomFloat(rng, -2.2, 2.2, 2);
    points.push({
      x: Math.max(zone.xMin - 1, Math.min(zone.xMax + 1, xBase + xJitter)),
      y: Math.max(zone.yMin - 1, Math.min(zone.yMax + 1, yBase + yJitter)),
    });
  }

  return points;
}

function createNodes(rng: Rng) {
  const typeCounts: Record<NodeType, number> = {
    CPU: 6,
    GPU: 10,
    FPGA: 4,
    MEMORY: 6,
    STORAGE: 4,
    NIC: 4,
    SWITCH: 2,
  };

  const targetNodes = randomInt(rng, 45, 60);
  const expandableTypes: NodeType[] = ["CPU", "GPU", "FPGA", "MEMORY", "STORAGE", "NIC"];
  let remaining = targetNodes - 36;
  while (remaining > 0) {
    const type = randomItem(rng, expandableTypes);
    typeCounts[type] += 1;
    remaining -= 1;
  }

  const clusterCounts = {
    A: {
      CPU: 2,
      GPU: 3,
      FPGA: 0,
      MEMORY: 2,
      STORAGE: 1,
      NIC: 1,
    },
    B: {
      CPU: 2,
      GPU: 3,
      FPGA: 2,
      MEMORY: 2,
      STORAGE: 1,
      NIC: 1,
    },
    C: {
      CPU: 2,
      GPU: 4,
      FPGA: 2,
      MEMORY: 2,
      STORAGE: 2,
      NIC: 2,
    },
  };

  (["CPU", "GPU", "FPGA", "MEMORY", "STORAGE", "NIC"] as NodeType[]).forEach((type) => {
    let extra =
      typeCounts[type] -
      (clusterCounts.A[type as keyof typeof clusterCounts.A] +
        clusterCounts.B[type as keyof typeof clusterCounts.B] +
        clusterCounts.C[type as keyof typeof clusterCounts.C]);
    while (extra > 0) {
      const cluster = randomItem(rng, ["A", "B", "C"] as const);
      clusterCounts[cluster][type as keyof typeof clusterCounts.A] += 1;
      extra -= 1;
    }
  });

  const groups: Array<{ cluster: "A" | "B" | "C" | "G"; items: Array<{ type: NodeType; count: number }> }> = [
    {
      cluster: "A",
      items: [
        { type: "CPU", count: clusterCounts.A.CPU },
        { type: "GPU", count: clusterCounts.A.GPU },
        { type: "MEMORY", count: clusterCounts.A.MEMORY },
        { type: "NIC", count: clusterCounts.A.NIC },
        { type: "STORAGE", count: clusterCounts.A.STORAGE },
        ...(clusterCounts.A.FPGA > 0 ? [{ type: "FPGA" as NodeType, count: clusterCounts.A.FPGA }] : []),
      ],
    },
    {
      cluster: "B",
      items: [
        { type: "CPU", count: clusterCounts.B.CPU },
        { type: "GPU", count: clusterCounts.B.GPU },
        { type: "FPGA", count: clusterCounts.B.FPGA },
        { type: "MEMORY", count: clusterCounts.B.MEMORY },
        { type: "NIC", count: clusterCounts.B.NIC },
        { type: "STORAGE", count: clusterCounts.B.STORAGE },
      ],
    },
    {
      cluster: "C",
      items: [
        { type: "CPU", count: clusterCounts.C.CPU },
        { type: "GPU", count: clusterCounts.C.GPU },
        { type: "FPGA", count: clusterCounts.C.FPGA },
        { type: "MEMORY", count: clusterCounts.C.MEMORY },
        { type: "NIC", count: clusterCounts.C.NIC },
        { type: "STORAGE", count: clusterCounts.C.STORAGE },
      ],
    },
    {
      cluster: "G",
      items: [{ type: "SWITCH", count: 2 }],
    },
  ];

  const counts: Record<NodeType, number> = {
    CPU: 0,
    GPU: 0,
    FPGA: 0,
    MEMORY: 0,
    STORAGE: 0,
    NIC: 0,
    SWITCH: 0,
  };

  const nodes: GraphNode[] = [];
  groups.forEach((group) => {
    const nonGlobalCount = group.items.reduce((sum, item) => sum + item.count, 0);
    const points =
      group.cluster === "G"
        ? [
            { x: 40, y: 8 },
            { x: 78, y: 8 },
          ]
        : buildClusterPoints(rng, clusterZones[group.cluster], nonGlobalCount);
    let index = 0;
    group.items.forEach((item) => {
      for (let i = 0; i < item.count; i += 1) {
        counts[item.type] += 1;
        const point = points[index];
        index += 1;
        const shortType = item.type === "MEMORY" ? "MEM" : item.type;
        nodes.push({
          id: `${item.type}-${counts[item.type]}`,
          type: item.type,
          cluster: group.cluster,
          label: `${shortType}-${counts[item.type]}`,
          x: point.x,
          y: point.y,
          utilization: randomInt(rng, 18, 88),
          capacity:
            item.type === "GPU"
              ? `${randomItem(rng, [40, 48, 80])}GB`
              : item.type === "MEMORY"
                ? `${randomItem(rng, [64, 96, 128])}GB`
                : item.type === "NIC" || item.type === "SWITCH"
                  ? `${randomItem(rng, [100, 200, 400])}Gbps`
                  : `${randomItem(rng, [16, 24, 32, 64])}`,
          bandwidth: `${randomItem(rng, [40, 100, 200, 400])}Gbps`,
          latency: `${randomFloat(rng, 0.6, 5.2)}ms`,
        });
      }
    });
  });
  return nodes;
}

function createEdges(rng: Rng, nodes: GraphNode[]) {
  const edges: GraphEdge[] = [];
  const edgeSet = new Set<string>();

  function addEdge(source: string, target: string) {
    const key = [source, target].sort().join("|");
    if (source === target || edgeSet.has(key)) return;
    edgeSet.add(key);
    edges.push({ id: `edge-${edges.length + 1}`, source, target });
  }

  const clusters = ["A", "B", "C"] as const;
  clusters.forEach((cluster) => {
    const clusterNodes = nodes.filter((node) => node.cluster === cluster);
    const localSwitch = cluster === "C" ? "SWITCH-2" : "SWITCH-1";
    clusterNodes.forEach((node) => {
      const peers = clusterNodes.filter((peer) => peer.id !== node.id);
      addEdge(node.id, randomItem(rng, peers).id);
    });
    clusterNodes
      .filter((node) => node.type === "NIC")
      .forEach((node) => addEdge(node.id, localSwitch));
  });
  addEdge("SWITCH-1", "SWITCH-2");

  const targetEdgeCount = randomInt(rng, Math.max(56, nodes.length + 8), Math.max(72, nodes.length + 18));
  while (edges.length < targetEdgeCount) {
    const source = randomItem(rng, nodes);
    const target = randomItem(
      rng,
      nodes.filter((node) => node.id !== source.id && (node.cluster === source.cluster || node.cluster === "G" || source.cluster === "G")),
    );
    addEdge(source.id, target.id);
  }
  return edges;
}

function createTask(rng: Rng) {
  const taskType = randomItem<TaskMode>(rng, ["计算密集型", "数据密集型", "通信密集型", "混合型"]);
  return {
    taskType,
    dagNodes: randomInt(rng, 14, 24),
    memoryDemand: `${randomItem(rng, [64, 80, 96, 128, 160])}GB`,
    qos: `${randomInt(rng, 16, 30)}min`,
    demandBars:
      taskType === "计算密集型"
        ? [92, 84, 54, 48, 76]
        : taskType === "数据密集型"
          ? [62, 88, 94, 58, 68]
          : taskType === "通信密集型"
            ? [66, 78, 52, 96, 82]
            : [82, 80, 76, 78, 72],
  };
}

function createCandidates(rng: Rng, taskType: TaskMode, nodes: GraphNode[]) {
  const byType = (type: NodeType) => nodes.filter((node) => node.type === type).map((node) => node.id);
  const poolMap: Record<TaskMode, string[]> = {
    计算密集型: [...byType("GPU"), ...byType("FPGA"), ...byType("CPU"), ...byType("MEMORY"), ...byType("NIC")],
    数据密集型: [...byType("STORAGE"), ...byType("MEMORY"), ...byType("NIC"), ...byType("CPU"), ...byType("GPU")],
    通信密集型: [...byType("NIC"), ...byType("SWITCH"), ...byType("GPU"), ...byType("MEMORY")],
    混合型: [...byType("CPU"), ...byType("GPU"), ...byType("MEMORY"), ...byType("STORAGE"), ...byType("NIC"), ...byType("SWITCH")],
  };

  return [1, 2, 3, 4, 5]
    .map((rank) => {
      const score = randomInt(rng, 76, 97);
      return {
        id: `candidate-${rank}`,
        rank,
        score,
        nodes: sampleUnique(rng, poolMap[taskType], randomInt(rng, 6, 10)),
        metrics: {
          capacity: randomInt(rng, 84, 97),
          performance: randomInt(rng, 80, 96),
          topology: randomInt(rng, 78, 95),
          qos: randomInt(rng, 82, 97),
        },
      };
    })
    .sort((a, b) => b.score - a.score)
    .map((candidate, index) => ({ ...candidate, rank: index + 1 }));
}

function generateData(seed: number): SimData {
  const rng = mulberry32(seed);
  const task = createTask(rng);
  const nodes = createNodes(rng);
  const edges = createEdges(rng, nodes);
  const candidates = createCandidates(rng, task.taskType, nodes);
  return {
    seed,
    snapshot: {
      avgUtilization: randomInt(rng, 32, 58),
      networkBandwidth: randomItem(rng, [100, 200, 400]),
      gpuNodes: nodes.filter((node) => node.type === "GPU").length,
      cpuNodes: nodes.filter((node) => node.type === "CPU").length,
      fpgaNodes: nodes.filter((node) => node.type === "FPGA").length,
      memoryNodes: nodes.filter((node) => node.type === "MEMORY").length,
      storageNodes: nodes.filter((node) => node.type === "STORAGE").length,
    },
    task,
    graph: { nodes, edges },
    embeddingBars: Array.from({ length: 3 }, () => randomInt(rng, 60, 96)),
    candidates,
    bestCandidateId: candidates[0].id,
  };
}

const API_BASE = "http://localhost:8000";

function normalizeNodeType(type: string): NodeType {
  const upper = String(type || "").toUpperCase();

  if (
    upper === "CPU" ||
    upper === "GPU" ||
    upper === "FPGA" ||
    upper === "MEMORY" ||
    upper === "STORAGE" ||
    upper === "NIC" ||
    upper === "SWITCH"
  ) {
    return upper as NodeType;
  }

  return "CPU";
}

function scaleToPercent(
  value: number,
  min: number,
  max: number,
  low = 6,
  high = 94,
) {
  if (!Number.isFinite(value)) return 50;
  if (max <= min) return 50;

  return low + ((value - min) / (max - min)) * (high - low);
}

function mapBackendGraphToSimData(graph: any, seed: number): SimData {
  const rng = mulberry32(seed);

  const rawNodes = graph.nodes ?? [];
  const rawEdges = graph.edges ?? graph.links ?? [];

  const rawXs = rawNodes
    .map((node: any) => Number(node.x))
    .filter((value: number) => Number.isFinite(value));

  const rawYs = rawNodes
    .map((node: any) => Number(node.y))
    .filter((value: number) => Number.isFinite(value));

  const minX = rawXs.length ? Math.min(...rawXs) : 0;
  const maxX = rawXs.length ? Math.max(...rawXs) : 100;
  const minY = rawYs.length ? Math.min(...rawYs) : 0;
  const maxY = rawYs.length ? Math.max(...rawYs) : 100;

  const nodes: GraphNode[] = rawNodes.map((node: any, index: number) => {
    const type = normalizeNodeType(node.type);

    const cluster: "A" | "B" | "C" | "G" =
      type === "SWITCH"
        ? "G"
        : index % 3 === 0
          ? "A"
          : index % 3 === 1
            ? "B"
            : "C";

    const rawX = Number(node.x);
    const rawY = Number(node.y);

    const utilization = Number.isFinite(Number(node.utilization))
      ? Number(node.utilization)
      : Number(node.dynamic_state?.utilization ?? 0);

    return {
      id: String(node.id),
      type,
      cluster,
      label: String(node.label ?? node.name ?? node.id),

      // 关键：把后端坐标缩放到百分比
      x: Number.isFinite(rawX)
        ? scaleToPercent(rawX, minX, maxX, 6, 94)
        : 10 + (index % 10) * 8,

      y: Number.isFinite(rawY)
        ? scaleToPercent(rawY, minY, maxY, 8, 88)
        : 15 + Math.floor(index / 10) * 8,

      utilization,
      capacity:
        type === "GPU"
          ? `${node.static_attrs?.memory_total ?? 0}GB`
          : type === "MEMORY"
            ? `${node.static_attrs?.capacity_gb ?? 0}GB`
            : type === "NIC" || type === "SWITCH"
              ? `${node.static_attrs?.bandwidth_gbps ?? 0}Gbps`
              : `${node.static_attrs?.cores ?? node.static_attrs?.logic_units ?? "-"}`,
      bandwidth: `${node.static_attrs?.bandwidth_gbps ?? node.bandwidth_gbps ?? "-"}Gbps`,
      latency: `${node.static_attrs?.latency_ms ?? node.latency_ms ?? "-"}ms`,
    };
  });

  const nodeIds = new Set(nodes.map((node) => node.id));

  const edges: GraphEdge[] = rawEdges
    .map((edge: any, index: number) => ({
      id: String(edge.id ?? `edge-${index + 1}`),
      source: String(edge.source ?? edge.source_id ?? edge.from ?? ""),
      target: String(edge.target ?? edge.target_id ?? edge.to ?? ""),
    }))
    .filter((edge: GraphEdge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

  const task = createTask(rng);
  const candidates = createCandidates(rng, task.taskType, nodes);

  return {
    seed,
    snapshot: {
      avgUtilization: nodes.length
        ? Math.round(nodes.reduce((sum, node) => sum + node.utilization, 0) / nodes.length)
        : 0,
      networkBandwidth: 400,
      gpuNodes: nodes.filter((node) => node.type === "GPU").length,
      cpuNodes: nodes.filter((node) => node.type === "CPU").length,
      fpgaNodes: nodes.filter((node) => node.type === "FPGA").length,
      memoryNodes: nodes.filter((node) => node.type === "MEMORY").length,
      storageNodes: nodes.filter((node) => node.type === "STORAGE").length,
    },
    task,
    graph: {
      nodes,
      edges,
    },
    embeddingBars: Array.from({ length: 3 }, () => randomInt(rng, 60, 96)),
    candidates,
    bestCandidateId: candidates[0]?.id ?? "",
  };
}

function renderStepTabContent(
  meta: StepMeta,
  tab: DetailTab,
  data: SimData,
  activeStep: StepId,
  selectedCandidate: CandidateSubnet | null,
  setSelectedCandidateId: (id: string) => void,
) {
  if (tab === "概览") {
    return (
      <div className="space-y-2 text-xs text-slate-600">
        <div className="font-medium text-slate-800">{meta.title}</div>
        <div>{meta.caption}</div>
        <div className="flex flex-wrap gap-1.5">
          {meta.keywords.map((keyword) => (
            <span key={keyword} className="rounded-full bg-slate-50 px-2 py-1 text-[10px] text-slate-600">
              {keyword}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (tab === "输入") {
    return <div className="text-xs leading-5 text-slate-600">{meta.input}</div>;
  }

  if (tab === "处理") {
    return <div className="text-xs leading-5 text-slate-600">{meta.process}</div>;
  }

  if (activeStep === 3) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">{meta.output}</div>
        <div className="space-y-2">
          {data.task.demandBars.map((value, index) => (
            <div key={`qt-${index}`} className="h-2 rounded-full bg-slate-100">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${value}%` }}
                className="h-2 rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-violet-500"
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (activeStep === 4) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">{meta.output}</div>
        <div className="space-y-2">
          {["节点嵌入", "拓扑感知", "子图嵌入"].map((label, index) => (
            <div key={label} className="space-y-1">
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span>{label}</span>
                <span>{data.embeddingBars[index]}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${data.embeddingBars[index]}%` }}
                  className="h-2 rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-violet-500"
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (activeStep === 5) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">{meta.output}</div>
        <div className="grid gap-2">
          {data.candidates.map((candidate) => {
            const selected = selectedCandidate?.id === candidate.id;
            const topOne = candidate.id === data.bestCandidateId;
            return (
              <button
                key={candidate.id}
                type="button"
                onClick={() => setSelectedCandidateId(candidate.id)}
                className={`rounded-[12px] border p-2 text-left transition ${
                  selected
                    ? "border-indigo-300 bg-gradient-to-r from-sky-50 via-white to-violet-50 shadow-[0_8px_18px_rgba(129,140,248,0.12)]"
                    : "border-slate-200/80 bg-white/80 hover:border-sky-200"
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-medium text-slate-800">
                  <span>候选子网 {candidate.rank}</span>
                  {topOne && <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] text-indigo-700">Top-1</span>}
                </div>
                <div className="mt-2 h-2 rounded-full bg-slate-100">
                  <div
                    className={`h-2 rounded-full ${
                      topOne ? "bg-gradient-to-r from-sky-500 to-violet-500" : "bg-gradient-to-r from-sky-400 to-cyan-400"
                    }`}
                    style={{ width: `${candidate.score}%` }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return <div className="text-xs leading-5 text-slate-600">{meta.output}</div>;
}

export default function HeterogeneousResourceMappingPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SimData | null>(null);
  const [activeStep, setActiveStep] = useState<StepId>(1);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [graphScale, setGraphScale] = useState(1);
  const [expandedStepId, setExpandedStepId] = useState<StepId | null>(1);
  const [detailTabs, setDetailTabs] = useState<Record<StepId, DetailTab>>(initialTabs);
  const timerRef = useRef<number | null>(null);

  const bestCandidate = useMemo(() => {
    if (!data) return null;
    return data.candidates.find((candidate) => candidate.id === data.bestCandidateId) ?? data.candidates[0];
  }, [data]);

  const selectedCandidate = useMemo(() => {
    if (!data) return null;
    return data.candidates.find((candidate) => candidate.id === selectedCandidateId) ?? bestCandidate;
  }, [bestCandidate, data, selectedCandidateId]);

  const displayedCandidate = selectedCandidate ?? bestCandidate;

  async function handleGenerate() {
    if (timerRef.current) window.clearTimeout(timerRef.current);

    const seed = Date.now();

    setLoading(true);
    setData(null);
    setActiveStep(1);
    setSelectedCandidateId(null);
    setGraphScale(1);
    setExpandedStepId(1);
    setDetailTabs(initialTabs);

    try {
      const response = await fetch(`${API_BASE}/api/resource-graph?limit=250`);

      if (!response.ok) {
        throw new Error(`加载资源图失败：HTTP ${response.status}`);
      }

      const graph = await response.json();
      const next = mapBackendGraphToSimData(graph, seed);

      setData(next);
      setSelectedCandidateId(next.bestCandidateId);
      setActiveStep(1);

      console.log("Loaded backend resource graph:", {
        nodes: next.graph.nodes.length,
        edges: next.graph.edges.length,
      });
    } catch (error) {
      console.error("加载后端资源图失败，回退到本地模拟数据：", error);

      const fallback = generateData(seed);
      setData(fallback);
      setSelectedCandidateId(fallback.bestCandidateId);
      setActiveStep(1);
    } finally {
      setLoading(false);
    }
  }
  function clampScale(next: number) {
    return Math.max(0.8, Math.min(1.28, Number(next.toFixed(2))));
  }

  function handleWheelZoom(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    const direction = event.deltaY > 0 ? -0.04 : 0.04;
    setGraphScale((prev) => clampScale(prev + direction));
  }

  const graphStatsLabel = data ? `${data.graph.nodes.length} 节点 / ${data.graph.edges.length} 边 / 异构资源图 GR` : "等待生成";

  function nodeActiveForStep(node: GraphNode) {
    if (!data) return false;
    if (activeStep === 1) return true;
    if (activeStep === 3) return taskHighlightMap[data.task.taskType].includes(node.type);
    if (activeStep === 4) return true;
    if (activeStep === 5 && selectedCandidate) return selectedCandidate.nodes.includes(node.id);
    return false;
  }

  function edgeActiveForStep(edge: GraphEdge) {
    if (!data) return false;
    if (activeStep === 2 || activeStep === 4) return true;
    if (activeStep === 5 && selectedCandidate) {
      return selectedCandidate.nodes.includes(edge.source) && selectedCandidate.nodes.includes(edge.target);
    }
    return false;
  }

  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.18),_transparent_24%),radial-gradient(circle_at_top_right,_rgba(34,211,238,0.16),_transparent_24%),linear-gradient(180deg,_#f8fbff_0%,_#f2f7ff_46%,_#edf4ff_100%)] text-slate-800">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.06)_1px,transparent_1px)] bg-[size:26px_26px]" />

      <div className="relative mx-auto flex h-screen max-w-[1920px] flex-col gap-2 px-3 py-3">
        <header className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-[18px] border border-sky-100/80 bg-white/72 px-4 py-2.5 shadow-[0_14px_40px_rgba(148,163,184,0.1)] backdrop-blur-xl">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-50 text-sky-600 ring-1 ring-sky-100">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0">
                <h1 className="truncate text-base font-semibold tracking-tight text-slate-900">异构算力资源描述与多模式任务映射</h1>
                <p className="truncate text-[11px] text-slate-500">从资源状态感知到最优资源子网映射的可视化演示。</p>
              </div>
            </div>
          </div>

          <motion.button
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleGenerate}
            className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-cyan-500 to-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-[0_12px_28px_rgba(59,130,246,0.24)]"
          >
            {loading ? <Gauge className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {loading ? "生成中..." : data ? "重新生成模拟数据" : "模拟生成资源与任务数据"}
          </motion.button>
        </header>

        <main className="grid min-h-0 flex-1 grid-cols-[20%_80%] gap-2">
          <section className="flex min-h-0 flex-col rounded-[18px] border border-sky-100/80 bg-white/70 p-3 shadow-[0_14px_36px_rgba(148,163,184,0.08)] backdrop-blur-xl">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Steps</div>
                <div className="mt-1 text-xs font-medium text-slate-700">当前步骤：第 {data ? activeStep : "--"} 步</div>
              </div>
              <Workflow className="h-3.5 w-3.5 text-sky-500" />
            </div>

            <div className="min-h-0 space-y-2 overflow-auto pr-1">
              {stepMetas.map((step) => {
                const active = activeStep === step.id && !!data;
                const expanded = expandedStepId === step.id && !!data;
                const currentTab = detailTabs[step.id];
                return (
                  <div
                    key={step.id}
                    className={`rounded-[16px] border transition ${
                      !data
                        ? "border-slate-200 bg-slate-50/90"
                        : active
                          ? "border-transparent bg-gradient-to-r from-sky-50 via-white to-violet-50 shadow-[0_0_0_1px_rgba(125,211,252,0.28),0_10px_22px_rgba(96,165,250,0.12)]"
                          : "border-slate-200/80 bg-white/76"
                    }`}
                  >
                    <div className="flex items-start gap-2 px-3 py-2.5">
                      <button
                        type="button"
                        disabled={!data}
                        onClick={() => setActiveStep(step.id)}
                        className="min-w-0 flex-1 text-left"
                      >
                        <div className={`text-sm font-medium ${active ? "text-slate-900" : data ? "text-slate-700" : "text-slate-400"}`}>
                          {step.id}. {step.shortTitle}
                        </div>
                        <div className="mt-0.5 truncate text-[11px] text-slate-500">{data ? step.caption : "请先生成数据"}</div>
                      </button>
                      <button
                        type="button"
                        disabled={!data}
                        onClick={() => {
                          setActiveStep(step.id);
                          setExpandedStepId((prev) => (prev === step.id ? null : step.id));
                        }}
                        className={`rounded-full p-1.5 transition ${
                          !data ? "text-slate-300" : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        }`}
                      >
                        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                    </div>

                    <AnimatePresence>
                      {expanded && data && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden border-t border-slate-100 px-3 pb-3 pt-2"
                        >
                          <div className="mb-2 flex flex-wrap gap-1.5">
                            {(["概览", "输入", "处理", "输出"] as DetailTab[]).map((tab) => (
                              <button
                                key={`${step.id}-${tab}`}
                                type="button"
                                onClick={() => setDetailTabs((prev) => ({ ...prev, [step.id]: tab }))}
                                className={`rounded-full px-2.5 py-1 text-[10px] transition ${
                                  currentTab === tab ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                                }`}
                              >
                                {tab}
                              </button>
                            ))}
                          </div>
                          <div className="rounded-[12px] border border-slate-200/80 bg-white/85 p-2.5 shadow-sm">
                            {renderStepTabContent(step, currentTab, data, step.id, selectedCandidate, setSelectedCandidateId)}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)_auto] gap-2 rounded-[18px] border border-sky-100/80 bg-white/72 p-3 shadow-[0_14px_36px_rgba(148,163,184,0.08)] backdrop-blur-xl">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Resource Graph</div>
                <div className="mt-0.5 text-sm font-medium text-slate-800">{data ? `${data.graph.nodes.length} 节点 / ${data.graph.edges.length} 边 / 异构资源图 GR` : "等待生成"}</div>
              </div>
              <div className="flex items-center gap-2">
                <div className="rounded-full border border-sky-100 bg-sky-50/80 px-2.5 py-1 text-[11px] text-sky-700">{stepMetas[activeStep - 1].shortTitle}</div>
                <div className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white/80 px-1.5 py-1 shadow-sm">
                  <button
                    type="button"
                    onClick={() => setGraphScale((prev) => clampScale(prev - 0.06))}
                    className="rounded-full p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <div className="min-w-[42px] text-center text-[11px] text-slate-500">{Math.round(graphScale * 100)}%</div>
                  <button
                    type="button"
                    onClick={() => setGraphScale((prev) => clampScale(prev + 0.06))}
                    className="rounded-full p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div
              className="relative min-h-0 flex-1 overflow-hidden rounded-[22px] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(240,247,255,0.92))]"
              onWheel={handleWheelZoom}
            >
              <div className="absolute left-[5%] top-[8%] h-[28%] w-[24%] rounded-[28px] border border-sky-100/70 bg-sky-50/30" />
              <div className="absolute left-[33%] top-[8%] h-[30%] w-[29%] rounded-[28px] border border-cyan-100/70 bg-cyan-50/25" />
              <div className="absolute left-[64%] top-[8%] h-[33%] w-[29%] rounded-[28px] border border-violet-100/70 bg-violet-50/25" />

              {!data && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="rounded-[20px] border border-slate-200 bg-white/86 px-4 py-3 text-sm text-slate-500 shadow-sm">
                    点击按钮生成模拟资源与任务数据。
                  </div>
                </div>
              )}

              {data && (
                <div className="absolute inset-0 origin-center transition-transform duration-200" style={{ transform: `scale(${graphScale})` }}>
                  <svg className="absolute inset-0 h-full w-full">
                    <defs>
                      <linearGradient id="edgeBaseLight" x1="0%" x2="100%">
                        <stop offset="0%" stopColor="rgba(148,163,184,0.22)" />
                        <stop offset="100%" stopColor="rgba(96,165,250,0.28)" />
                      </linearGradient>
                      <linearGradient id="edgeHotLight" x1="0%" x2="100%">
                        <stop offset="0%" stopColor="rgba(34,211,238,0.9)" />
                        <stop offset="100%" stopColor="rgba(129,140,248,0.95)" />
                      </linearGradient>
                    </defs>
                    {data.graph.edges.map((edge) => {
                      const source = data.graph.nodes.find((node) => node.id === edge.source);
                      const target = data.graph.nodes.find((node) => node.id === edge.target);
                      if (!source || !target) return null;
                      const highlighted = edgeActiveForStep(edge);
                      return (
                        <g key={edge.id}>
                          <line
                            x1={`${source.x}%`}
                            y1={`${source.y}%`}
                            x2={`${target.x}%`}
                            y2={`${target.y}%`}
                            stroke={highlighted ? "url(#edgeHotLight)" : "url(#edgeBaseLight)"}
                            strokeWidth={highlighted ? 2.2 : 1.4}
                            opacity={activeStep === 5 ? (highlighted ? 1 : 0.28) : activeStep === 2 || activeStep === 4 ? 0.72 : 0.38}
                          />
                          {(activeStep === 2 || activeStep === 4) && (
                            <motion.circle
                              r="1.8"
                              fill={activeStep === 4 ? "#6366f1" : "#38bdf8"}
                              animate={{
                                opacity: [0.15, 1, 0.15],
                                cx: [`${source.x}%`, `${target.x}%`],
                                cy: [`${source.y}%`, `${target.y}%`],
                              }}
                              transition={{ duration: activeStep === 4 ? 1.5 : 2.2, repeat: Infinity, ease: "linear" }}
                            />
                          )}
                        </g>
                      );
                    })}
                  </svg>

                  {activeStep === 5 &&
                    data.candidates.map((candidate) => {
                      const points = candidate.nodes
                        .map((id) => data.graph.nodes.find((node) => node.id === id))
                        .filter(Boolean) as GraphNode[];
                      if (!points.length) return null;
                      const left = Math.max(Math.min(...points.map((point) => point.x)) - 2.6, 1);
                      const top = Math.max(Math.min(...points.map((point) => point.y)) - 3.5, 1);
                      const right = Math.min(Math.max(...points.map((point) => point.x)) + 3.2, 98);
                      const bottom = Math.min(Math.max(...points.map((point) => point.y)) + 4.4, 98);
                      const topOne = candidate.id === data.bestCandidateId;
                      const selected = selectedCandidate?.id === candidate.id;
                      return (
                        <motion.div
                          key={`candidate-outline-${candidate.id}`}
                          animate={
                            topOne || selected
                              ? {
                                  opacity: [0.3, 0.72, 0.3],
                                  boxShadow: [
                                    "0 0 0 rgba(99,102,241,0.1)",
                                    "0 0 24px rgba(99,102,241,0.22)",
                                    "0 0 0 rgba(99,102,241,0.1)",
                                  ],
                                }
                              : { opacity: 0.12 }
                          }
                          transition={{ duration: 2, repeat: Infinity }}
                          className={`pointer-events-none absolute rounded-[22px] border ${
                            topOne || selected ? "border-indigo-300/70" : "border-slate-300/35"
                          }`}
                          style={{
                            left: `${left}%`,
                            top: `${top}%`,
                            width: `${right - left}%`,
                            height: `${bottom - top}%`,
                          }}
                        />
                      );
                    })}

                  {data.graph.nodes.map((node, index) => {
                    const Icon = getNodeIcon(node.type);
                    const active = nodeActiveForStep(node);
                    const highlightedByCandidate = activeStep === 5 && selectedCandidate ? selectedCandidate.nodes.includes(node.id) : false;
                    const dimmed = activeStep === 5 && selectedCandidate ? !selectedCandidate.nodes.includes(node.id) : false;

                    return (
                      <motion.div
                        key={node.id}
                        className="absolute -translate-x-1/2 -translate-y-1/2"
                        style={{ left: `${node.x}%`, top: `${node.y}%` }}
                        animate={{
                          y: [0, index % 2 === 0 ? -1.8 : 1.8, 0],
                          opacity: dimmed ? 0.2 : 1,
                          scale:
                            activeStep === 1
                              ? [1, index % 3 === 0 ? 1.08 : 1.04, 1]
                              : highlightedByCandidate
                                ? [1, 1.1, 1]
                                : hoveredNode === node.id
                                  ? 1.05
                                  : 1,
                        }}
                        transition={{
                          y: { duration: 3 + (index % 4) * 0.25, repeat: Infinity },
                          scale: { duration: 1.6, repeat: activeStep === 1 || highlightedByCandidate ? Infinity : 0 },
                        }}
                        onMouseEnter={() => setHoveredNode(node.id)}
                        onMouseLeave={() => setHoveredNode(null)}
                      >
                        <div
                          className={`relative flex items-center gap-1 rounded-2xl border bg-gradient-to-br px-2 py-1.5 text-[10px] shadow-[0_8px_22px_rgba(148,163,184,0.14)] backdrop-blur ${
                            highlightedByCandidate
                              ? "border-indigo-300 bg-gradient-to-br from-white via-sky-50 to-violet-50"
                              : active
                                ? "border-cyan-200 bg-white/96"
                                : "border-slate-200/80 bg-white/86"
                          } ${typeColors[node.type]}`}
                        >
                          <Icon className="h-3.5 w-3.5 text-slate-700" />
                          <span className="font-medium text-slate-700">{node.label}</span>
                        </div>
                      </motion.div>
                    );
                  })}

                  <AnimatePresence>
                    {hoveredNode && (
                      <motion.div
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 6 }}
                        className="absolute right-3 top-3 z-10 w-44 rounded-[16px] border border-sky-100 bg-white/92 p-3 text-xs text-slate-600 shadow-[0_18px_40px_rgba(148,163,184,0.18)]"
                      >
                        {(() => {
                          const node = data.graph.nodes.find((item) => item.id === hoveredNode);
                          if (!node) return null;
                          return (
                            <div className="space-y-1">
                              <div className="font-semibold text-slate-900">{node.id}</div>
                              <div>利用率 {node.utilization}%</div>
                              <div>容量 {node.capacity}</div>
                              <div>带宽 {node.bandwidth}</div>
                              <div>时延 {node.latency}</div>
                              <div>Cluster-{node.cluster}</div>
                            </div>
                          );
                        })()}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {activeStep === 1 && (
                    <div className="absolute bottom-3 left-3 grid gap-2 text-xs text-cyan-700">
                      {["采集 CPU/GPU/FPGA/网络/存储状态", "标准化资源属性", "生成资源属性向量"].map((item) => (
                        <div key={item} className="inline-flex items-center gap-2 rounded-full bg-white/92 px-3 py-1.5 shadow-sm">
                          <span className="h-2 w-2 rounded-full bg-cyan-400" />
                          {item}
                        </div>
                      ))}
                    </div>
                  )}

                </div>
              )}
            </div>
            <div className="grid h-[72px] grid-cols-[1.15fr_0.9fr_0.7fr_0.7fr_0.7fr_0.7fr] gap-2 rounded-[18px] border border-sky-100/80 bg-white/72 p-2.5 shadow-[0_12px_28px_rgba(148,163,184,0.08)] backdrop-blur-xl">
              {activeStep === 5 && displayedCandidate ? (
                <>
                  <div className="rounded-[14px] border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">当前子网</div>
                      <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] text-indigo-700">Top-{displayedCandidate.rank}</span>
                    </div>
                    <div className="mt-1 truncate text-xs font-medium text-slate-800">{displayedCandidate.nodes.join("、")}</div>
                  </div>
                  <div className="rounded-[14px] border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">综合评分</div>
                    <div className="mt-1 text-base font-semibold text-slate-900">{displayedCandidate.score} / 100</div>
                  </div>
                  {[
                    ["容量 OK", displayedCandidate.metrics.capacity],
                    ["性能 OK", displayedCandidate.metrics.performance],
                    ["拓扑 OK", displayedCandidate.metrics.topology],
                    ["QoS OK", displayedCandidate.metrics.qos],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-[14px] border border-emerald-100 bg-emerald-50/65 px-3 py-2">
                      <div className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700">
                        <CheckCircle2 className="h-3 w-3" />
                        {label}
                      </div>
                      <div className="mt-1 text-xs text-emerald-800">{value}%</div>
                    </div>
                  ))}
                </>
              ) : (
                <div className="col-span-full flex items-center justify-center rounded-[14px] border border-dashed border-slate-200 bg-slate-50/70 text-sm text-slate-500">
                  等待子网搜索验证
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
