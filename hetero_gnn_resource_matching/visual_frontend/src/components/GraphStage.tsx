import type { VisualGraph, VisualNode, VisualNodeType } from "../types";

const typeColors: Record<VisualNodeType, string> = {
  task: "#111827",
  cpu: "#2563eb",
  gpu: "#7c3aed",
  fpga: "#0891b2",
  memory: "#16a34a",
  storage: "#d97706",
  nic: "#db2777",
  switch: "#475569",
  result: "#0f766e"
};

interface GraphStageProps {
  graph: VisualGraph;
  selectedId: string | null;
  onSelectNode: (node: VisualNode) => void;
}

export function GraphStage({ graph, selectedId, onSelectNode }: GraphStageProps) {
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));

  return (
    <svg className="graph-stage" viewBox="0 0 1000 420" role="img" aria-label="resource mapping graph">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
        </marker>
      </defs>

      {graph.edges.map((edge) => {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        if (!source || !target) return null;

        const active = selectedId === source.id || selectedId === target.id;
        return (
          <g key={edge.id} opacity={active || !selectedId ? 1 : 0.35}>
            <line
              x1={source.x + 42}
              y1={source.y}
              x2={target.x - 42}
              y2={target.y}
              stroke={active ? "#2563eb" : "#cbd5e1"}
              strokeWidth={active ? 2.5 : 1.4}
              markerEnd="url(#arrow)"
            />
            {edge.label ? (
              <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 8} textAnchor="middle" className="edge-label">
                {edge.label}
              </text>
            ) : null}
          </g>
        );
      })}

      {graph.nodes.map((node) => {
        const active = selectedId === node.id;
        return (
          <g key={node.id} className="graph-node" opacity={selectedId && !active ? 0.62 : 1} onClick={() => onSelectNode(node)}>
            <rect
              x={node.x - 48}
              y={node.y - 24}
              width="96"
              height="48"
              rx="8"
              fill={typeColors[node.type]}
              stroke={active ? "#111827" : "#ffffff"}
              strokeWidth={active ? 4 : 2}
            />
            <text x={node.x} y={node.y - 3} textAnchor="middle" className="node-label">
              {node.label}
            </text>
            <text x={node.x} y={node.y + 14} textAnchor="middle" className="node-id">
              {node.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
