// services/frontend/pages/index.tsx
import { useEffect, useState, useRef } from "react";
import IngestPanel from "../components/IngestPanel";

// Simple API helper
const API = "http://localhost:8080";
async function jget<T>(path: string) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}
async function jpost<T>(path: string, body?: unknown) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

// Types
type Node = { id: string; label: string; type: "ent" | "doc" };
type Edge = { source: string; target: string; label: string };
type Job = { job_id: string; status: "queued" | "done" | "error"; result: any };
type Stats = { status: "ok"; documents: number; entities: number; doc_entities: number };

export default function Home() {
  const [apiStatus, setApiStatus] = useState<"ok" | "down">("down");
  const [seed, setSeed] = useState("ent:TATA,ent:FOX,doc:1");
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  const logLine = (m: string) =>
    setLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${m}`].slice(-400));

  useEffect(() => {
    // Health
    jget("/health")
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("down"));
    // Initial stats
    refreshStats();
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [log]);

  async function refreshStats() {
    try {
      const s = await jget<Stats>("/admin/stats");
      setStats(s);
    } catch (e: any) {
      logLine(`stats error: ${e.message}`);
    }
  }

  async function graphExpand() {
    const seed_ids = seed.split(",").map((s) => s.trim()).filter(Boolean);
    const data = await jpost<{ nodes: Node[]; edges: Edge[] }>("/graph/expand", {
      seed_ids,
      window_days: 14,
    });
    setNodes(data.nodes || []);
    setEdges(data.edges || []);
    logLine(`expand → nodes=${data.nodes?.length || 0} edges=${data.edges?.length || 0}`);
  }

  // job helpers
  async function enqueue(path: string, body: any) {
    const r = await jpost<{ job_id: string }>(path, body);
    return r.job_id;
  }
  async function poll(job_id: string) {
    let tries = 0;
    while (tries < 300) {
      tries++;
      const j = await jget<Job>(`/jobs/${job_id}`);
      logLine(`job ${job_id} → ${j.status}`);
      if (j.status === "done" || j.status === "error") return j;
      await new Promise((r) => setTimeout(r, 1000));
    }
    throw new Error("poll timeout");
  }

  async function flushAll() {
    setBusy(true);
    try {
      logLine("POST /admin/flush");
      const r = await jpost<{ status: string; flushed_at: string }>("/admin/flush");
      logLine(`flushed at ${r.flushed_at}`);
      await refreshStats();
    } catch (e: any) {
      logLine(`flush error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function ingestUrl() {
    setBusy(true);
    try {
      const job_id = await enqueue("/ingest/url", {
        url: "https://www.bbc.com/news/world-asia-india-68462269",
      });
      const job = await poll(job_id);
      logLine(`URL result: ${JSON.stringify(job.result).slice(0, 300)}…`);
      await refreshStats();
    } catch (e: any) {
      logLine(`url ingest error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function ingestTopic() {
    setBusy(true);
    try {
      const job_id = await enqueue("/ingest/topic", {
        topic: "Tata Foxconn India semiconductor",
      });
      const job = await poll(job_id);
      logLine(`Topic result: ${JSON.stringify(job.result).slice(0, 300)}…`);
      await refreshStats();
    } catch (e: any) {
      logLine(`topic ingest error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function ingestRss() {
    setBusy(true);
    try {
      const job_id = await enqueue("/ingest/rss", {
        rss_url: "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
      });
      const job = await poll(job_id);
      logLine(`RSS result: ${JSON.stringify(job.result).slice(0, 300)}…`);
      await refreshStats();
    } catch (e: any) {
      logLine(`rss ingest error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ padding: 16 }}>
      <p>API status: <b>{apiStatus}</b></p>

      <div className="grid">
        {/* Left: Admin actions */}
        <div className="card">
          <h3>Admin • Flush & Rebuild</h3>

          <div className="row">
            <button onClick={flushAll} disabled={busy}>Flush</button>
            <div className="counts">
              docs: <b>{stats?.documents ?? "…"}</b> • ents: <b>{stats?.entities ?? "…"}</b> • links: <b>{stats?.doc_entities ?? "…"}</b>
            </div>
          </div>

          <div className="row">
            <button onClick={ingestUrl} disabled={busy}>Ingest URL</button>
            <button onClick={ingestTopic} disabled={busy}>Ingest Topic</button>
            <button onClick={ingestRss} disabled={busy}>Ingest RSS</button>
          </div>

          <div className="row">
            <input value={seed} onChange={(e) => setSeed(e.target.value)} />
            <button onClick={graphExpand} disabled={busy}>Expand</button>
          </div>

          <div ref={logRef} className="log">
            {log.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </div>

        {/* Right: Raw Ingest Panel (kept for convenience) */}
        <IngestPanel />
      </div>

      <h4 style={{ marginTop: 16 }}>Nodes</h4>
      <pre>{JSON.stringify(nodes, null, 2)}</pre>

      <h4>Edges</h4>
      <pre>{JSON.stringify(edges, null, 2)}</pre>

      <style jsx>{`
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .card { padding: 12px; border: 1px solid #eee; border-radius: 8px; }
        .row { display: grid; grid-template-columns: repeat(3, max-content) 1fr; gap: 8px; align-items: center; margin: 8px 0; }
        input { padding: 8px; border: 1px solid #ddd; border-radius: 6px; width: 100%; }
        button { background: #377dff; color: white; border: 0; padding: 8px 12px; border-radius: 6px; }
        .counts { margin-left: 8px; font-family: monospace; }
        .log { height: 220px; overflow: auto; background: #0b1020; color: #cfe3ff; padding: 8px; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
      `}</style>
    </main>
  );
}
