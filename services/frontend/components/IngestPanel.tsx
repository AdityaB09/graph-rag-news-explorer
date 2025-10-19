// services/frontend/components/IngestPanel.tsx
import { useState } from "react";
import { ingestTopic, ingestRss, ingestUrl, jobStatus } from "../lib/api";

export default function IngestPanel() {
  const [topic, setTopic] = useState("apple supply chain");
  const [rssUrl, setRssUrl] = useState("https://news.google.com/rss/search?q=india%20manufacturing");
  const [url, setUrl] = useState("https://example.com/article.html");
  const [lastMsg, setLastMsg] = useState<string>("");

  async function runAndPoll(promise: Promise<{ job_id: string }>) {
    setLastMsg("Queued…");
    try {
      const { job_id } = await promise;
      // simple short poll for demo (usually you’d poll until done)
      const s1 = await jobStatus(job_id);
      if (s1.status === "done") {
        setLastMsg(`Done. Ingested ${s1.result?.ingested?.length || 0} item(s).`);
      } else {
        setLastMsg(`Status: ${s1.status} (try again)`);
      }
    } catch (e: any) {
      setLastMsg(`Error: ${e?.response?.status || ""} ${e?.message || e}`);
    }
  }

  return (
    <div className="card">
      <h3>Ingest News</h3>

      <div className="row">
        <input value={topic} onChange={(e) => setTopic(e.target.value)} />
        <button onClick={() => runAndPoll(ingestTopic(topic))}>Fetch Topic</button>
      </div>

      <div className="row">
        <input value={rssUrl} onChange={(e) => setRssUrl(e.target.value)} />
        <button onClick={() => runAndPoll(ingestRss(rssUrl))}>Fetch RSS</button>
      </div>

      <div className="row">
        <input value={url} onChange={(e) => setUrl(e.target.value)} />
        <button onClick={() => runAndPoll(ingestUrl(url))}>Fetch URL</button>
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
