// services/frontend/lib/api.ts
import axios from "axios";

const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace(/\/+$/, "");

export async function health() {
  const { data } = await axios.get(`${API_BASE}/health`);
  return data;
}

export async function graphExpand(params: {
  seed_ids: string[];
  max_hops: number;
  window_days: number;
}) {
  const { data } = await axios.post(`${API_BASE}/graph/expand`, params);
  return data; // {nodes, edges}
}

export async function ingestTopic(topic: string) {
  const { data } = await axios.post(`${API_BASE}/ingest/topic`, { topic });
  return data as { job_id: string };
}

export async function ingestRss(rss_url: string) {
  const { data } = await axios.post(`${API_BASE}/ingest/rss`, { rss_url });
  return data as { job_id: string };
}

export async function ingestUrl(url: string) {
  const { data } = await axios.post(`${API_BASE}/ingest/url`, { url });
  return data as { job_id: string };
}

export async function jobStatus(job_id: string) {
  const { data } = await axios.get(`${API_BASE}/jobs/${job_id}`);
  return data as { job_id: string; status: string; result?: any };
}

// const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";

export async function health(): Promise<{ status: string; search_enabled?: boolean }> {
  const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!r.ok) throw new Error("health failed");
  return r.json();
}

export async function recentDocs(limit = 50): Promise<{ status: string; items: Array<{
  id: string; title: string; url: string; source: string; published_at: string | null;
}>}> {
  const r = await fetch(`${API_BASE}/admin/recent_docs?limit=${limit}`, { cache: "no-store" });
  if (!r.ok) throw new Error("recent_docs failed");
  return r.json();
}
