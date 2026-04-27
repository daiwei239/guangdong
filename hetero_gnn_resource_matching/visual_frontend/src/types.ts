export type VisualNodeType = "task" | "cpu" | "gpu" | "fpga" | "memory" | "storage" | "nic" | "switch" | "result";

export interface VisualNode {
  id: string;
  label: string;
  type: VisualNodeType;
  x: number;
  y: number;
  score?: number;
}

export interface VisualEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  strength?: number;
}

export interface VisualGraph {
  nodes: VisualNode[];
  edges: VisualEdge[];
}
