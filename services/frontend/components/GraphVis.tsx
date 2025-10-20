// components/GraphVis.tsx
import React, { useMemo } from "react";

type GraphData = {
  nodes: Array<{ id: string; label?: string; type?: string }>;
  edges: Array<{ source: string; target: string; label?: string }>;
};

type Props = {
  apiBase?: string;               // not used here, but harmless if passed
  data: GraphData | null;
};

export default function GraphVis({ data }: Props) {
  const graph = data && Array.isArray(data.nodes) && Array.isArray(data.edges) ? data : { nodes: [], edges: [] };

  const layout = useMemo(() => {
    const W = 900, H = 360, R = Math.min(W, H) / 2 - 40;
    const n = Math.max(graph.nodes.length, 1);
    const angle = (i: number) => (i / n) * 2 * Math.PI;

    const positions: Record<string, { x: number; y: number; node: any }> = {};
    graph.nodes.forEach((node, i) => {
      const a = angle(i);
      const x = W / 2 + R * Math.cos(a);
      const y = H / 2 + R * Math.sin(a);
      positions[node.id] = { x, y, node };
    });
    return { W, H, positions };
  }, [graph]);

  const hasData = graph.nodes.length > 0;

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>Graph</h3>
      {!hasData && <div style={{ color: "#666" }}>No graph data yet. Run “Expand Graph” to see results.</div>}

      <svg width="100%" viewBox={`0 0 ${layout.W} ${layout.H}`} style={{ background: "#fafafa", borderRadius: 8 }}>
        {/* Edges */}
        {graph.edges.map((e, idx) => {
          const s = layout.positions[e.source];
          const t = layout.positions[e.target];
          if (!s || !t) return null;
          return <line key={`e-${idx}`} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#9BB5FF" strokeWidth={2} />;
        })}

        {/* Nodes */}
        {Object.values(layout.positions).map(({ x, y, node }, idx) => (
          <g key={`n-${node.id}-${idx}`} transform={`translate(${x}, ${y})`}>
            <circle r={20} fill="#7DA2FF" opacity={0.9} />
            <text textAnchor="middle" dy="0.35em" fontSize="10" fill="#fff">
              {node.type === "entity" ? (node.label || node.id).slice(0, 14) : (node.label || "Doc").slice(0, 14)}
            </text>
          </g>
        ))}
      </svg>

      {hasData && (
        <div style={{ marginTop: 8, fontFamily: "monospace" }}>
          nodes: {graph.nodes.length} • edges: {graph.edges.length}
        </div>
      )}
    </div>
  );
}
