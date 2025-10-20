// components/ExpandPanel.tsx
import React, { useState } from "react";

type Props = { apiBase: string };

export default function ExpandPanel({ apiBase }: Props) {
  const [seeds, setSeeds] = useState("ent:TATA,ent:FOX,ent:APPLE,ent:INDIA");
  const [days, setDays] = useState(365);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ nodes: any[]; edges: any[] } | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = {
        seed_ids: seeds
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        window_days: Number(days) || 30,
      };
      const r = await fetch(`${apiBase}/graph/expand`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json = await r.json();
      setResult(json);
    } catch (e: any) {
      setError(e?.message || "Failed to expand");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Expand Graph</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
        <input
          value={seeds}
          onChange={(e) => setSeeds(e.target.value)}
          placeholder="Comma-separated: ent:APPLE,doc:<uuid>,..."
        />
        <button onClick={run} disabled={loading} style={btnPrimary}>
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <label style={{ fontSize: 12, color: "#666" }}>
          Window days:{" "}
          <input
            type="number"
            min={1}
            max={3650}
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value || "30", 10))}
            style={{ width: 90 }}
          />
        </label>
      </div>

      {error && <div style={{ marginTop: 12, color: "#b00020" }}>Error: {error}</div>}

      {result && (
        <div style={{ marginTop: 12 }}>
          <div style={{ marginBottom: 8, fontFamily: "monospace" }}>
            nodes: {result.nodes?.length ?? 0} • edges: {result.edges?.length ?? 0}
          </div>
          <div
            style={{
              border: "1px solid #f2f2f2",
              background: "#fafafa",
              borderRadius: 6,
              padding: 8,
              maxHeight: 360,
              overflow: "auto",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
              fontSize: 12,
              whiteSpace: "pre",
            }}
          >
            {JSON.stringify(result, null, 2)}
          </div>
        </div>
      )}
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
