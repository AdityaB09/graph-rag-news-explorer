// /services/ui/src/IngestPanel.tsx
import React, { useState } from "react";

type Props = { apiBase: string };

async function submitJob(apiBase: string, path: string, body: any) {
  const r = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as { job_id: string };
}

async function pollJob(apiBase: string, jobId: string) {
  while (true) {
    const r = await fetch(`${apiBase}/jobs/${jobId}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    if (j.status === "done" || j.status === "error") return j;
    await new Promise((res) => setTimeout(res, 1000));
  }
}

export default function IngestPanel({ apiBase }: Props) {
  const [topic, setTopic] = useState<string>("apple supply chain");
  const [rss, setRss] = useState<string>("https://news.google.com/rss/search?q=india%20manufacturing");
  const [url, setUrl] = useState<string>("https://example.com/article.html");
  const [status, setStatus] = useState<string>("");

  const run = async (kind: "topic" | "rss" | "url") => {
    try {
      setStatus("queued (try again)");
      const payload =
        kind === "topic"
          ? { topic }
          : kind === "rss"
          ? { rss_url: rss }
          : { url };
      const path =
        kind === "topic" ? "/ingest/topic" : kind === "rss" ? "/ingest/rss" : "/ingest/url";

      const { job_id } = await submitJob(apiBase, path, payload);
      const result = await pollJob(apiBase, job_id);
      if (result.status === "done") {
        setStatus(`done (ingested ${result?.result?.ingested?.length ?? 0})`);
      } else {
        setStatus(`error: ${result?.result?.error ?? "unknown"}`);
      }
    } catch (e: any) {
      setStatus(`error: ${e?.message || "request failed"}`);
    } finally {
      // Auto-clear after a bit so the panel doesn't look "stuck"
      setTimeout(() => setStatus(""), 4000);
    }
  };

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Ingest News</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} />
        <button onClick={() => run("topic")} style={btnPrimary}>Fetch Topic</button>

        <input value={rss} onChange={(e) => setRss(e.target.value)} />
        <button onClick={() => run("rss")} style={btnPrimary}>Fetch RSS</button>

        <input value={url} onChange={(e) => setUrl(e.target.value)} />
        <button onClick={() => run("url")} style={btnPrimary}>Fetch URL</button>
      </div>

      <div style={{ marginTop: 12, color: status.startsWith("error") ? "#b00020" : "#555" }}>
        {status ? `Status: ${status}` : null}
      </div>
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  appearance: "none",
  border: "1px solid #2f6df6",
  background: "#2f6df6",
  color: "#fff",
  borderRadius: 6,
  padding: "8px 12px",
  cursor: "pointer",
};
