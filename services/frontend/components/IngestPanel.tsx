// services/frontend/components/IngestPanel.tsx
import { useState } from "react";

const API = "http://localhost:8080";
async function jget<T>(path: string) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}
async function jpost<T>(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export default function IngestPanel() {
  const [topic, setTopic] = useState("apple supply chain");
  const [rssUrl, setRssUrl] = useState("https://news.google.com/rss/search?q=india%20manufacturing");
  const [url, setUrl] = useState("https://example.com/article.html");
  const [lastMsg, setLastMsg] = useState<string>("");

  async function runAndPoll(kind: "topic" | "rss" | "url") {
    setLastMsg("Queued…");
    try {
      let path = "";
      let body: any = {};
      if (kind === "topic") { path = "/ingest/topic"; body = { topic }; }
      if (kind === "rss")   { path = "/ingest/rss";   body = { rss_url: rssUrl }; }
      if (kind === "url")   { path = "/ingest/url";   body = { url }; }

      const { job_id } = await jpost<{ job_id: string }>(path, body);

      // poll
      let tries = 0;
      while (tries < 300) {
        tries++;
        const j = await jget<{ job_id: string; status: string; result: any }>(`/jobs/${job_id}`);
        if (j.status === "done") {
          setLastMsg(`Done. Ingested ${j.result?.ingested?.length || 0} item(s).`);
          return;
        }
        if (j.status === "error") {
          setLastMsg(`Error: ${JSON.stringify(j.result)}`);
          return;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      setLastMsg("Timeout polling job.");
    } catch (e: any) {
      setLastMsg(`Error: ${e?.message || e}`);
    }
  }

  return (
    <div className="card">
      <h3>Ingest News</h3>

      <div className="row">
        <input value={topic} onChange={(e) => setTopic(e.target.value)} />
        <button onClick={() => runAndPoll("topic")}>Fetch Topic</button>
      </div>

      <div className="row">
        <input value={rssUrl} onChange={(e) => setRssUrl(e.target.value)} />
        <button onClick={() => runAndPoll("rss")}>Fetch RSS</button>
      </div>

      <div className="row">
        <input value={url} onChange={(e) => setUrl(e.target.value)} />
        <button onClick={() => runAndPoll("url")}>Fetch URL</button>
      </div>

      <p style={{ color: lastMsg.startsWith("Error") ? "crimson" : "#333" }}>
        {lastMsg}
      </p>

      <style jsx>{`
        .card { padding: 12px; border: 1px solid #eee; border-radius: 8px; }
        .row { display: grid; grid-template-columns: 1fr 160px; gap: 8px; margin-top: 8px; }
        input { padding: 8px; border: 1px solid #ddd; border-radius: 6px; }
        button { background: #377dff; color: white; border: 0; padding: 8px 12px; border-radius: 6px; }
      `}</style>
    </div>
  );
}
