// pages/index.tsx
import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// Client-only components
const IngestPanel = dynamic(() => import("../components/IngestPanel"), { ssr: false });
const ExpandPanel = dynamic(() => import("../components/ExpandPanel"), { ssr: false });
const GraphVis = dynamic(() => import("../components/GraphVis"), { ssr: false });
const GraphSummary = dynamic(() => import("../components/GraphSummary"), { ssr: false });

type Health = { status: "ok"; search_enabled?: boolean };
type AdminStats = {
  status: "ok";
  documents: number;
  entities: number;
  doc_entities: number;
  flushed_at?: string;
};
type RecentDoc = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string | null;
};

const API =
  process.env.NEXT_PUBLIC_API_BASE ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8080";

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
      const r = await fetch(`${API}/admin/stats`, { cache: "no-store" });
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

function RecentDocsPanel({ limit = 50 }: { limit?: number }) {
  const [items, setItems] = useState<RecentDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const r = await fetch(`${API}/admin/recent_docs?limit=${limit}`, { cache: "no-store" });
        if (!r.ok) throw new Error(`recent_docs error: ${r.status}`);
        const json = await r.json();
        setItems(Array.isArray(json?.items) ? json.items : []);
      } catch (e: any) {
        setErr(e?.message || "Failed to load recent docs");
      } finally {
        setLoading(false);
      }
    })();
  }, [limit]);

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Recent Documents</h2>
      {loading && <div>Loading…</div>}
      {err && <div style={{ color: "#b00020" }}>Error: {err}</div>}
      {!loading && !err && (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {items.map((d) => (
            <li key={d.id} style={{ marginBottom: 8 }}>
              <a href={d.url} target="_blank" rel="noreferrer">
                {d.title || d.url}
              </a>{" "}
              <small style={{ color: "#666" }}>
                — {d.source || "unknown"}
                {d.published_at ? ` · ${new Date(d.published_at).toLocaleString()}` : ""}
              </small>
            </li>
          ))}
          {items.length === 0 && <li>No documents yet.</li>}
        </ul>
      )}
    </div>
  );
}

export default function HomePage() {
  const [health, setHealth] = useState<"ok" | "down" | "loading">("loading");
  const [searchEnabled, setSearchEnabled] = useState<boolean | null>(null);
  const [expandData, setExpandData] = useState<{ nodes?: any[]; edges?: any[] } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/health`, { cache: "no-store" });
        if (!r.ok) throw new Error("health not ok");
        const json = (await r.json()) as Health;
        setHealth(json.status === "ok" ? "ok" : "down");

        // Allow an env override to force-disable search on Vercel:
        const envDisable =
          (process.env.NEXT_PUBLIC_SEARCH_DISABLED || "").toString().trim() === "1" ||
          (process.env.NEXT_PUBLIC_SEARCH_DISABLED || "").toString().toLowerCase() === "true";

        if (envDisable) {
          setSearchEnabled(false);
        } else if (typeof json.search_enabled === "boolean") {
          setSearchEnabled(json.search_enabled);
        } else {
          // default to true locally, false on serverless if you prefer:
          setSearchEnabled(true);
        }
      } catch {
        setHealth("down");
        setSearchEnabled(false);
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
        <b>API:</b>{" "}
        <span style={{ color: health === "ok" ? "#0a7a0a" : "#b00020" }}>
          {health === "loading" ? "checking..." : health}
        </span>
        {" · "}
        <b>Search:</b>{" "}
        <span style={{ color: searchEnabled ? "#0a7a0a" : "#b26a00" }}>
          {searchEnabled === null ? "checking..." : searchEnabled ? "enabled" : "disabled"}
        </span>
      </div>

      {/* Two columns: LEFT = ingest + admin + GRAPH ; RIGHT = expand + summary (or recent docs fallback) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* LEFT column */}
        <div style={{ display: "grid", gridTemplateRows: "auto auto 1fr", gap: 16 }}>
          <IngestPanel apiBase={API} />
          <AdminPanel />
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16, minHeight: 420 }}>
            <GraphVis apiBase={API} data={expandData} />
          </div>
        </div>

        {/* RIGHT column */}
        <div style={{ display: "grid", gridTemplateRows: "auto auto", gap: 16 }}>
          {/* When search is disabled (e.g., OpenSearch missing in prod), show recent docs instead of the expand UI */}
          {searchEnabled === false ? (
            <>
              <RecentDocsPanel limit={50} />
              <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
                <div style={{ color: "#666" }}>
                  Graph (expand/summary) requires search to be enabled. Showing recent docs instead.
                </div>
              </div>
            </>
          ) : (
            <>
              <ExpandPanel apiBase={API} onResult={setExpandData} />
              <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
                <GraphSummary data={expandData} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
