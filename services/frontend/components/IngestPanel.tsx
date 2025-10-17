// services/frontend/components/IngestPanel.tsx
"use client";

import { useState } from "react";
import axios from "axios";

const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace(/\/+$/, "");

async function enqueue(endpoint: string, payload: any) {
  const { data } = await axios.post(`${API_BASE}${endpoint}`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  return data as { job_id: string };
}

async function check(job_id: string) {
  const { data } = await axios.get(`${API_BASE}/jobs/${job_id}`);
  return data as { id: string; status: string; result_count?: number; error?: string };
}

export default function IngestPanel() {
  const [topic, setTopic] = useState("apple supply chain");
  const [rss, setRss] = useState("https://news.google.com/rss/search?q=india%20manufacturing");
  const [url, setUrl] = useState("https://example.com/article.html");
  const [log, setLog] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  async function run(kind: "search" | "rss" | "url") {
    setLoading(true);
    setLog([]);
    try {
      let body: any, ep: string;
      if (kind === "search") {
        ep = "/ingest/search";
        body = { query: topic, limit: 20 };
      } else if (kind === "rss") {
        ep = "/ingest/rss";
        body = { rss_url: rss, limit: 30 };
      } else {
        ep = "/ingest/url";
        body = { url };
      }
      const { job_id } = await enqueue(ep, body);
      setLog((l) => [...l, `Enqueued: ${job_id}`]);

      // simple poll loop
      let status = "queued";
      let tries = 0;
      while (["queued", "started", "deferred"].includes(status) && tries < 90) {
        await new Promise((r) => setTimeout(r, 2000));
        const s = await check(job_id);
        status = s.status;
        setLog((l) => [...l, `Status: ${status}${s.result_count ? ` (${s.result_count})` : ""}`]);
        if (status === "failed") {
          setLog((l) => [...l, `Error: ${s.error || "unknown"}`]);
          break;
        }
        tries++;
      }

      if (status === "finished") {
        setLog((l) => [...l, "Done! Refresh your graph (Run)."]);
      }
    } catch (e: any) {
      setLog((l) => [...l, `Error: ${e?.message || e}`]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12, marginBottom: 16 }}>
      <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Ingest News</h3>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: 8, alignItems: "center" }}>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="topic (uses Google News RSS)"
          style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db" }}
        />
        <button
          onClick={() => run("search")}
          disabled={loading}
          style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #2563eb", background: "#3b82f6", color: "white", fontWeight: 600 }}
        >
          {loading ? "Working..." : "Fetch Topic"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: 8, alignItems: "center", marginTop: 8 }}>
        <input
          value={rss}
          onChange={(e) => setRss(e.target.value)}
          placeholder="RSS feed URL"
          style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db" }}
        />
        <button
          onClick={() => run("rss")}
          disabled={loading}
          style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #2563eb", background: "#3b82f6", color: "white", fontWeight: 600 }}
        >
          {loading ? "Working..." : "Fetch RSS"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: 8, alignItems: "center", marginTop: 8 }}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Single article URL"
          style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db" }}
        />
        <button
          onClick={() => run("url")}
          disabled={loading}
          style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #2563eb", background: "#3b82f6", color: "white", fontWeight: 600 }}
        >
          {loading ? "Working..." : "Fetch URL"}
        </button>
      </div>

      <pre style={{ marginTop: 12, padding: 12, background: "#f9fafb", borderRadius: 8, maxHeight: 200, overflow: "auto" }}>
        {log.join("\n")}
      </pre>
    </div>
  );
}
