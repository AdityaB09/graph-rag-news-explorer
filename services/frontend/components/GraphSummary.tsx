// components/GraphSummary.tsx
import React, { useMemo } from "react";

type Node = { id: string; label?: string; type?: "doc" | "entity" };
type Edge = { source: string; target: string; label?: string };

type Props = {
  data?: { nodes?: unknown; edges?: unknown } | null;
};

function asNodes(x: unknown): Node[] {
  if (!Array.isArray(x)) return [];
  return x
    .map((n: any) => ({
      id: String(n?.id ?? ""),
      label: typeof n?.label === "string" ? n.label : undefined,
      type: n?.type === "doc" || n?.type === "entity" ? n.type : undefined,
    }))
    .filter((n) => n.id);
}

function asEdges(x: unknown): Edge[] {
  if (!Array.isArray(x)) return [];
  return x
    .map((e: any) => ({
      source: String(e?.source ?? ""),
      target: String(e?.target ?? ""),
      label: typeof e?.label === "string" ? e.label : undefined,
    }))
    .filter((e) => e.source && e.target);
}

function computeSummary(nodes: Node[], edges: Edge[]) {
  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, 0);
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1);
    degree.set(e.target, (degree.get(e.target) || 0) + 1);
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const comps = connectedComponents(nodes.map((n) => n.id), edges);

  // rank top by degree, prefer entities first when degrees tie
  const top = [...degree.entries()]
    .sort((a, b) => {
      const da = b[1] - a[1];
      if (da !== 0) return da;
      const ta = nodeById.get(a[0])?.type === "entity" ? 0 : 1;
      const tb = nodeById.get(b[0])?.type === "entity" ? 0 : 1;
      return ta - tb;
    })
    .slice(0, 10)
    .map(([id, d]) => {
      const n = nodeById.get(id);
      const name = (n?.label || id || "").toString().trim().replace(/\s+/g, " ");
      return { id, name, degree: d, type: n?.type };
    });

  // density = 2E / (N(N-1)) for simple undirected view
  const N = nodes.length;
  const E = edges.length;
  const density = N > 1 ? (2 * E) / (N * (N - 1)) : 0;

  // count entities/docs
  let ent = 0,
    doc = 0;
  for (const n of nodes) {
    if (n.type === "entity") ent++;
    else if (n.type === "doc") doc++;
  }

  return { ent, doc, nodesN: N, edgesN: E, density, components: comps, top };
}

function connectedComponents(ids: string[], edges: Edge[]): number {
  const adj = new Map<string, string[]>();
  for (const id of ids) adj.set(id, []);
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    if (!adj.has(e.target)) adj.set(e.target, []);
    adj.get(e.source)!.push(e.target);
    adj.get(e.target)!.push(e.source);
  }
  const seen = new Set<string>();
  let comps = 0;
  for (const id of ids) {
    if (seen.has(id)) continue;
    comps++;
    const q = [id];
    seen.add(id);
    while (q.length) {
      const v = q.pop()!;
      for (const w of adj.get(v) || []) {
        if (!seen.has(w)) {
          seen.add(w);
          q.push(w);
        }
      }
    }
  }
  return comps;
}

export default function GraphSummary({ data }: Props) {
  const nodes = asNodes(data?.nodes);
  const edges = asEdges(data?.edges);

  const s = useMemo(() => computeSummary(nodes, edges), [nodes, edges]);

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>Graph summary</h3>
      {nodes.length === 0 ? (
        <div style={{ color: "#777" }}>Run “Expand Graph” to populate the graph.</div>
      ) : (
        <>
          <div style={{ marginBottom: 8 }}>
            <b>{s.ent}</b> entities connected to <b>{s.doc}</b> documents, totaling{" "}
            <b>{s.nodesN}</b> nodes and <b>{s.edgesN}</b> edges.
          </div>
          <div style={{ marginBottom: 8 }}>
            Density ≈ <b>{s.density.toFixed(3)}</b> • Connected components: <b>{s.components}</b>
          </div>
          {s.top.length > 0 && (
            <>
              <div style={{ fontWeight: 600, margin: "8px 0 4px" }}>Top entities (by degree)</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {s.top.map((t) => (
                  <li key={t.id}>
                    {t.name || t.id} <span style={{ color: "#666" }}>({t.degree})</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
