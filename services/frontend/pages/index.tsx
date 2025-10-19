// services/frontend/pages/index.tsx
import { useEffect, useState } from "react";
import IngestPanel from "../components/IngestPanel";
import { graphExpand, health } from "../lib/api";

type Node = { id: string; label: string; type: "ent" | "doc" };
type Edge = { source: string; target: string; label: string };

export default function Home() {
  const [apiStatus, setApiStatus] = useState<"ok" | "down">("down");
  const [seed, setSeed] = useState("ent:TATA,ent:FOX,doc:1");
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    health()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("down"));
  }, []);

  async function runExpand() {
    const seed_ids = seed
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const data = await graphExpand({ seed_ids, max_hops: 2, window_days: 14 });
    setNodes(data.nodes || []);
    setEdges(data.edges || []);
  }

  return (
    <main style={{ padding: 16 }}>
      <p>API status: <b>{apiStatus}</b></p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <IngestPanel />

        <div className="card">
          <h3>Expand Graph</h3>
          <div className="row">
            <input value={seed} onChange={(e) => setSeed(e.target.value)} />
            <button onClick={runExpand}>Run</button>
          </div>

          <h4 style={{ marginTop: 16 }}>Nodes</h4>
          <pre>{JSON.stringify(nodes, null, 2)}</pre>

          <h4>Edges</h4>
          <pre>{JSON.stringify(edges, null, 2)}</pre>
        </div>
      </div>

      <style jsx>{`
        .card { padding: 12px; border: 1px solid #eee; border-radius: 8px; }
        .row { display: grid; grid-template-columns: 1fr 100px; gap: 8px; margin-top: 8px; }
        input { padding: 8px; border: 1px solid #ddd; border-radius: 6px; }
        button { background: #377dff; color: white; border: 0; padding: 8px 12px; border-radius: 6px; }
      `}</style>
    </main>
  );
}
