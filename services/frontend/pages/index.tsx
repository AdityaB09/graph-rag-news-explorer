// pages/index.tsx
import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// Client-only components
const IngestPanel  = dynamic(() => import("../components/IngestPanel"),  { ssr: false });
const ExpandPanel  = dynamic(() => import("../components/ExpandPanel"),  { ssr: false });
const GraphSummary = dynamic(() => import("../components/GraphSummary"), { ssr: false });
const GraphVis     = dynamic(() => import("../components/GraphVis"),     { ssr: false });

type Health = { status: "ok" };
type AdminStats = {
  status: "ok";
  documents: number;
  entities: number;
  doc_entities: number;
  flushed_at?: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

const btn: React.CSSProperties = {
  appearance: "none",
  border: "1px solid #ddd",
  background: "#fff",
  borderRadius: 6,
  padding: "8px 12px",
  cursor: "pointer",
};
const btnPrimary: React.CSSProperties = {
  ...btn,
  background: "#2f6df6",
  color: "#fff",
  borderColor: "#2f6df6",
};

function AdminPanel() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [flushing, setFlushing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    setError(null);
    setLoading(true);
    try {
      const r = await fetch(`${API}/admin/stats`);
      if (!r.ok) throw new Error(`Stats error: ${r.status}`);
      setStats(await r.json());
    } catch (e: any) {
      setError(e?.message || "Failed to fetch stats");
    } finally {
      setLoading(false);
    }
  };

  const flush = async () => {
    setError(null);
    setFlushing(true);
    try {
      const r = await fetch(`${API}/admin/flush`, { method: "POST" });
      if (!r.ok) throw new Error(`Flush error: ${r.status}`);
      await r.json();
      await loadStats();
    } catch (e: any) {
      setError(e?.message || "Failed to flush");
    } finally {
      setFlushing(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16, marginTop: 16 }}>
      <h2 style={{ marginTop: 0 }}>Admin</h2>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button onClick={loadStats} disabled={loading || flushing} style={btn}>
          {loading ? "Refreshing…" : "Refresh Stats"}
        </button>
        <button onClick={flush} disabled={loading || flushing} style={btnPrimary}>
          {flushing ? "Flushing…" : "Flush DB"}
        </button>
        {error && <span style={{ color: "#b00020" }}>Error: {error}</span>}
      </div>

      <div style={{ marginTop: 12, fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
        {stats ? (
          <>
            <div>documents: {stats.documents}</div>
            <div>entities: {stats.entities}</div>
            <div>doc_entities: {stats.doc_entities}</div>
            <div>flushed_at: {stats.flushed_at || "—"}</div>
          </>
        ) : (
          <div>Loading…</div>
        )}
      </div>
    </div>
  );
}

export default function HomePage() {
  const [health, setHealth] = useState<"ok" | "down" | "loading">("loading");
  const [expandData, setExpandData] = useState<{ nodes: any[]; edges: any[] } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/health`);
        if (!r.ok) throw new Error("health not ok");
        const json = (await r.json()) as Health;
        setHealth(json.status === "ok" ? "ok" : "down");
      } catch {
        setHealth("down");
      }
    })();
  }, []);

  return (
    <div
      style={{
        padding: 20,
        fontFamily:
          "Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial",
      }}
    >
      <div style={{ marginBottom: 8 }}>
        <b>API status:</b>{" "}
        <span style={{ color: health === "ok" ? "#0a7a0a" : "#b00020" }}>
          {health === "loading" ? "checking..." : health}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left column */}
        <div>
          <IngestPanel apiBase={API} />
          <AdminPanel />
        </div>

        {/* Right column */}
        <div style={{ display: "grid", gap: 16 }}>
          <ExpandPanel apiBase={API} onResult={setExpandData} />

          {/* Summary card */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
            <GraphSummary data={expandData} />
          </div>

          {/* Graph card – explicit height so it always shows */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 0, minHeight: 540 }}>
            <GraphVis data={expandData} height={540} />
          </div>
        </div>
      </div>
    </div>
  );
}
