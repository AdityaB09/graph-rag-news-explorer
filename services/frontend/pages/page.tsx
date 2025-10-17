"use client";

import { useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import GraphVis from "../components/GraphVis";
import TimelineChart, { Point } from "../components/TimelineChart";
import IngestPanel from "../components/IngestPanel";
import { expandGraph, getHealth, GraphEdge, GraphNode } from "../lib/api";

const seedPresets = ["ent:TATA", "ent:FOX", "doc:1"];

function toPointsFromEdges(edges: GraphEdge[], start?: number, end?: number): Point[] {
  const buckets = new Map<string, number>();
  edges.forEach((e) => {
    if (!e.ts) return;
    const d = dayjs(e.ts).startOf("day").toISOString();
    buckets.set(d, (buckets.get(d) ?? 0) + 1);
  });
  const times = [...buckets.keys()].sort();
  const pts = times.map((iso) => ({ t: +new Date(iso), v: buckets.get(iso)! }));
  if (pts.length === 0) {
    const base = dayjs().subtract(6, "day");
    return Array.from({ length: 7 }, (_, i) => ({ t: base.add(i, "day").valueOf(), v: 0 }));
  }
  return pts;
}

export default function Page() {
  const [apiOk, setApiOk] = useState(false);
  const [seed, setSeed] = useState("ent:TATA");
  const [maxHops, setMaxHops] = useState(2);
  const [days, setDays] = useState(14);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then((x) => setApiOk(!!x.ok)).catch(() => setApiOk(false));
  }, []);

  const endMs = useMemo(() => dayjs().endOf("day").valueOf(), []);
  const startMs = useMemo(() => dayjs().subtract(days, "day").startOf("day").valueOf(), [days]);

  const graphData = useMemo(() => {
    const graphNodes = nodes.map((n) => ({
      id: n.id,
      label: n.attrs?.name ?? n.attrs?.title ?? n.id,
      group: n.type,
    }));
    const graphEdges = edges.map((e) => ({ from: e.src, to: e.dst, label: e.type }));
    return { nodes: graphNodes, edges: graphEdges };
  }, [nodes, edges]);

  const timelinePoints = useMemo(() => toPointsFromEdges(edges, startMs, endMs), [edges, startMs, endMs]);

  async function runExpand() {
    setLoading(true);
    setErr(null);
    try {
      const { nodes, edges } = await expandGraph({
        seed_ids: seed.split(",").map((s) => s.trim()).filter(Boolean),
        start_ms: startMs,
        end_ms: endMs,
        max_hops: maxHops,
      });
      setNodes(nodes);
      setEdges(edges);
    } catch (e: any) {
      setErr(e?.message ?? "Expand failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runExpand();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ padding: "24px", maxWidth: 1280, margin: "0 auto" }}>
      <h1 style={{ fontSize: 36, fontWeight: 800 }}>Graph-RAG News Explorer</h1>
      <p style={{ margin: "6px 0 22px" }}>
        API status: <strong>{apiOk ? "ok" : "down"}</strong>
      </p>

      <IngestPanel />

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 24, alignItems: "start" }}>
        <div>
          <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12, marginBottom: 16 }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Expand Graph</h3>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <div style={{ gridColumn: "span 3" }}>
                <label style={{ display: "block", fontSize: 12, color: "#555" }}>Seed IDs (comma-separated)</label>
                <input
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="ent:TATA,doc:1"
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #d1d5db" }}
                />
                <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {["ent:TATA", "ent:FOX", "doc:1"].map((s) => (
                    <button
                      key={s}
                      onClick={() => setSeed(s)}
                      style={{
                        padding: "6px 10px",
                        borderRadius: 8,
                        border: "1px solid #d1d5db",
                        background: "#f9fafb",
                        cursor: "pointer",
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "#555" }}>Max hops</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={maxHops}
                  onChange={(e) => setMaxHops(parseInt(e.target.value || "2", 10))}
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #d1d5db" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "#555" }}>Window (days)</label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={14}
                  onChange={(e) => {}}
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #d1d5db", opacity: 0.6 }}
                  disabled
                />
              </div>

              <div style={{ display: "flex", alignItems: "flex-end" }}>
                <button
                  onClick={runExpand}
                  disabled={loading}
                  style={{
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: "1px solid #2563eb",
                    background: loading ? "#93c5fd" : "#3b82f6",
                    color: "white",
                    fontWeight: 600,
                    cursor: "pointer",
                    width: "100%",
                  }}
                >
                  {loading ? "Expanding..." : "Run"}
                </button>
              </div>
            </div>

            {err && <div style={{ marginTop: 12, color: "#b91c1c", fontSize: 14 }}>{err}</div>}
          </div>

          <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12 }}>
            <TimelineChart title="Activity (edges/day)" points={[]} />
          </div>
        </div>

        <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Story Graph</h3>
          <GraphVis nodes={graphData.nodes} edges={graphData.edges} />
        </div>
      </div>
    </div>
  );
}
