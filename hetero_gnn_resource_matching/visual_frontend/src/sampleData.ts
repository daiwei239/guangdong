import type { VisualGraph } from "./types";

export const sampleGraph: VisualGraph = {
  nodes: [
    { id: "task", label: "Task", type: "task", x: 90, y: 210 },
    { id: "cpu_001", label: "CPU", type: "cpu", x: 280, y: 90, score: 0.82 },
    { id: "gpu_003", label: "GPU", type: "gpu", x: 280, y: 200, score: 0.94 },
    { id: "memory_001", label: "MEM", type: "memory", x: 280, y: 310, score: 0.78 },
    { id: "nic_001", label: "NIC", type: "nic", x: 500, y: 200, score: 0.88 },
    { id: "switch_001", label: "SW", type: "switch", x: 710, y: 200, score: 0.74 },
    { id: "result", label: "Top-1", type: "result", x: 900, y: 200, score: 0.93 }
  ],
  edges: [
    { id: "e1", source: "task", target: "cpu_001", label: "requires" },
    { id: "e2", source: "task", target: "gpu_003", label: "requires" },
    { id: "e3", source: "task", target: "memory_001", label: "requires" },
    { id: "e4", source: "cpu_001", target: "gpu_003", label: "same_node", strength: 0.8 },
    { id: "e5", source: "gpu_003", target: "nic_001", label: "pcie", strength: 0.9 },
    { id: "e6", source: "memory_001", target: "cpu_001", label: "local", strength: 0.7 },
    { id: "e7", source: "nic_001", target: "switch_001", label: "network", strength: 0.7 },
    { id: "e8", source: "switch_001", target: "result", label: "score", strength: 0.93 }
  ]
};
