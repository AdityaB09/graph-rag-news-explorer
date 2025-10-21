// components/GraphSummary.tsx
import React, { useMemo } from "react";

type Node = { id: string; label?: string; type?: "doc" | "entity" };
type Edge = { source: string; target: string; label?: string };
type Props = { data?: { nodes?: unknown; edges?: unknown } | null };

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

function hostnameFromLabel(label?: string) {
  if (!label) return "";
  try {
    const u = new URL(label);
    return u.hostname.replace(/^www\./, "");
  } catch {
    const m = label.match(/\b([a-z0-9-]+\.[a-z.]{2,})\b/i);
    return m ? m[1].toLowerCase().replace(/^www\./, "") : "";
  }
}

function connectedComponents(ids: string[], edges: Edge[]): { count: number; sizes: number[] } {
  const adj = new Map<string, string[]>();
  for (const id of ids) adj.set(id, []);
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    if (!adj.has(e.target)) adj.set(e.target, []);
    adj.get(e.source)!.push(e.target);
    adj.get(e.target)!.push(e.source);
  }
  const seen = new Set<string>();
  const sizes: number[] = [];
  for (const id of ids) {
    if (seen.has(id)) continue;
    let size = 0;
    const q = [id];
    seen.add(id);
    while (q.length) {
      const v = q.pop()!;
      size++;
      for (const w of adj.get(v) || []) {
        if (!seen.has(w)) {
          seen.add(w);
          q.push(w);
        }
      }
    }
    sizes.push(size);
  }
  sizes.sort((a, b) => b - a);
  return { count: sizes.length, sizes };
}

function computeSummary(nodesIn: Node[], edgesIn: Edge[]) {
  const nodes = nodesIn;
  const edges = edgesIn;

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const entities = nodes.filter((n) => n.type === "entity");
  const docs = nodes.filter((n) => n.type === "doc");

  // Degree
  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, 0);
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1);
    degree.set(e.target, (degree.get(e.target) || 0) + 1);
  }

  const topEntities = entities
    .map((n) => ({ id: n.id, name: n.label || n.id, d: degree.get(n.id) || 0 }))
    .sort((a, b) => b.d - a.d)
    .slice(0, 6);

  const topDocs = docs
    .map((n) => ({ id: n.id, title: n.label || n.id, mentions: degree.get(n.id) || 0 }))
    .sort((a, b) => b.mentions - a.mentions)
    .slice(0, 6);

  // doc -> entity list
  const docToEnts = new Map<string, string[]>();
  for (const e of edges) {
    const a = nodeById.get(e.source)?.type;
    const b = nodeById.get(e.target)?.type;
    if (a === "doc" && b === "entity") {
      (docToEnts.get(e.source) ?? docToEnts.set(e.source, []).get(e.source)!).push(e.target);
    } else if (a === "entity" && b === "doc") {
      (docToEnts.get(e.target) ?? docToEnts.set(e.target, []).get(e.target)!).push(e.source);
    }
  }

  // co-mentions
  const pairCount = new Map<string, number>();
  for (const entList of docToEnts.values()) {
    const ents = Array.from(new Set(entList));
    for (let i = 0; i < ents.length; i++) {
      for (let j = i + 1; j < ents.length; j++) {
        const a = ents[i];
        const b = ents[j];
        const key = a < b ? `${a}||${b}` : `${b}||${a}`;
        pairCount.set(key, (pairCount.get(key) || 0) + 1);
      }
    }
  }
  const topPairs = [...pairCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([key, c]) => {
      const [a, b] = key.split("||");
      const A = nodeById.get(a)?.label || a;
      const B = nodeById.get(b)?.label || b;
      return { a: A, b: B, count: c };
    });

  const domainCount = new Map<string, number>();
  for (const d of docs) {
    const host = hostnameFromLabel(d.label);
    if (!host) continue;
    domainCount.set(host, (domainCount.get(host) || 0) + 1);
  }
  const topDomains = [...domainCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  const comps = connectedComponents(nodes.map((n) => n.id), edges);
  const N = nodes.length;
  const E = edges.length;
  const density = N > 1 ? (2 * E) / (N * (N - 1)) : 0;

  return {
    counts: { entities: entities.length, docs: docs.length, nodes: N, edges: E },
    density,
    components: comps,
    topEntities,
    topDocs,
    topPairs,
    topDomains,
  };
}

function makeNarrative(s: ReturnType<typeof computeSummary>): string {
  const parts: string[] = [];

  // Opening
  parts.push(
    `The graph links ${s.counts.entities} entities across ${s.counts.docs} documents ` +
      `(${s.counts.nodes} nodes, ${s.counts.edges} edges; density ≈ ${s.density.toFixed(3)}).`
  );

  // Components
  if (s.components.count > 1) {
    const largest = s.components.sizes[0];
    const rest = s.components.sizes.slice(1, 4).join(", ");
    parts.push(
      `It splits into ${s.components.count} clusters (largest ${largest}${
        rest ? `; others ${rest}` : ""
      }), suggesting multiple sub-stories rather than a single thread.`
    );
  } else {
    parts.push(`It forms one main cluster, suggesting a cohesive narrative.`);
  }

  // Hubs
  if (s.topEntities.length) {
    const top = s.topEntities.slice(0, 3).map((e) => `${e.name} (deg ${e.d})`);
    parts.push(`Most connected entities are ${top.join(", ")}.`);
  }

  // Co-mentions
  if (s.topPairs.length) {
    const pairs = s.topPairs
      .slice(0, 2)
      .map((p) => `${p.a} ↔ ${p.b} (${p.count} docs)`)
      .join("; ");
    parts.push(`Strong co-mentions include ${pairs}, hinting at shared coverage.`);
  }

  // Sources
  if (s.topDomains.length) {
    const lead = s.topDomains[0];
    const others = s.topDomains.slice(1).map(([h]) => h);
    parts.push(
      `Coverage is led by ${lead[0]} (${lead[1]} docs)${others.length ? `, with ${others.join(", ")} also active` : ""}.`
    );
  }

  return parts.join(" ");
}

export default function GraphSummary({ data }: Props) {
  const nodes = asNodes(data?.nodes);
  const edges = asEdges(data?.edges);
  const s = useMemo(() => computeSummary(nodes, edges), [nodes, edges]);
  const narrative = useMemo(() => (nodes.length ? makeNarrative(s) : ""), [nodes.length, s]);

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>Graph summary</h3>

      {nodes.length === 0 ? (
        <div style={{ color: "#777" }}>Run “Expand Graph” to populate the graph.</div>
      ) : (
        <>
          {/* Short paragraph you asked for */}
          <div style={{ marginBottom: 10, lineHeight: 1.5 }}>{narrative}</div>

          {/* Quick counters */}
          <div style={{ marginBottom: 8 }}>
            <b>{s.counts.entities}</b> entities • <b>{s.counts.docs}</b> documents • <b>{s.counts.nodes}</b> nodes •{" "}
            <b>{s.counts.edges}</b> edges
          </div>

          {/* Useful ranked lists */}
          {s.topEntities.length > 0 && (
            <>
              <div style={{ fontWeight: 600, margin: "10px 0 4px" }}>Top entities (by degree)</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {s.topEntities.map((t) => (
                  <li key={t.id}>
                    {t.name} <span style={{ color: "#666" }}>({t.d})</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {s.topPairs.length > 0 && (
            <>
              <div style={{ fontWeight: 600, margin: "12px 0 4px" }}>Strong co-mention pairs</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {s.topPairs.map((p, i) => (
                  <li key={i}>
                    {p.a} – {p.b} <span style={{ color: "#666" }}>({p.count} shared docs)</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {s.topDomains.length > 0 && (
            <>
              <div style={{ fontWeight: 600, margin: "12px 0 4px" }}>Top sources</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {s.topDomains.map(([host, c]) => (
                  <li key={host}>
                    {host} <span style={{ color: "#666" }}>({c} docs)</span>
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
