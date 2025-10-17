"use client";

import { useEffect, useRef } from "react";

type Node = { id: string; label: string; group?: string };
type Edge = { from: string; to: string; label?: string };

export default function GraphVis({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    let network: any;
    let resizeHandler: any;

    (async () => {
      // Dynamically import the ESM file export (bypasses the problematic directory import)
      const vis = await import("vis-network/standalone/esm/vis-network");

      const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges),
      };

      const options = {
        physics: { stabilization: true },
        nodes: { shape: "dot", size: 18, font: { size: 14 } },
        edges: { arrows: { to: { enabled: false } }, smooth: true },
        interaction: { hover: true },
      };

      network = new vis.Network(ref.current as HTMLDivElement, data, options);

      resizeHandler = () => network?.redraw();
      window.addEventListener("resize", resizeHandler);
    })();

    return () => {
      window.removeEventListener("resize", resizeHandler);
      // @ts-ignore
      network?.destroy?.();
    };
  }, [nodes, edges]);

  return <div ref={ref} style={{ width: "100%", height: 420 }} />;
}
