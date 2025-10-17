// services/frontend/lib/api.ts
import axios from "axios";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8080";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

export type ExpandRequest = {
  seed_ids: string[];
  start_ms?: number;
  end_ms?: number;
  max_hops?: number;
};

export type GraphNode = {
  id: string;
  type?: string;
  ts?: number;
  attrs?: Record<string, any>;
};

export type GraphEdge = {
  src: string;
  dst: string;
  type?: string;
  weight?: number;
  ts?: number;
};

export async function getHealth(): Promise<{ ok: boolean }> {
  const { data } = await api.get("/health");
  return data;
}

export async function expandGraph(payload: ExpandRequest): Promise<{
  nodes: GraphNode[];
  edges: GraphEdge[];
}> {
  // Your FastAPI handler should return { nodes, edges }
  const { data } = await api.post("/graph/expand", payload);
  return data;
}
