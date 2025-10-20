// components/GraphVis.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";

export type VisNode = {
  id: string;
  label: string;
  type: "doc" | "entity";
};

export type VisEdge = {
  source: string; // id of source node
  target: string; // id of target node
  label?: string;
};

type Props = {
  apiBase?: string; // not used here, but kept for API parity
  data: { nodes: VisNode[]; edges: VisEdge[] } | null;
  height?: number;
};

function asNode(obj: any): VisNode | undefined {
  // If it's already a node object, return it; if it's an id (string), return undefined (caller can map by id)
  if (obj && typeof obj === "object" && "id" in obj) return obj as VisNode;
  return undefined;
}

export default function GraphVis({ data, height = 520 }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dims, setDims] = useState<{ w: number; h: number }>({ w: 900, h: height });

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const rect = el.getBoundingClientRect();
      setDims({ w: Math.max(320, rect.width), h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [height]);

  const { nodes, edges, nodeById } = useMemo(() => {
    const nodes = data?.nodes ?? [];
    const edges = data?.edges ?? [];
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    return { nodes, edges, nodeById };
  }, [data]);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    if (!nodes.length) return;

    const { w, h } = dims;

    // Root group for pan/zoom
    const gRoot = svg.append("g");
    const gLinks = gRoot.append("g").attr("class", "links");
    const gNodes = gRoot.append("g").attr("class", "nodes");
    const gLabels = gRoot.append("g").attr("class", "labels");

    // Pan & zoom
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (ev) => {
          gRoot.attr("transform", ev.transform.toString());
        })
    );

    // D3 sim copies of nodes/links
    const simNodes: any[] = nodes.map((n) => ({ ...n }));
    const simLinks: any[] = edges.map((e) => ({ ...e })); // source/target are IDs; forceLink will resolve via id()

    // Helpers that work whether link endpoints are objects or ids
    const getSrcNode = (l: any): VisNode | undefined => asNode(l.source) ?? (l.source ? (nodeById.get(l.source) as any) : undefined);
    const getTgtNode = (l: any): VisNode | undefined => asNode(l.target) ?? (l.target ? (nodeById.get(l.target) as any) : undefined);

    // Link distance: longer from docs, shorter between entities
    const linkDistance = (l: any) => {
      const srcType = getSrcNode(l)?.type ?? "entity";
      const tgtType = getTgtNode(l)?.type ?? "entity";
      const isDocEdge = srcType === "doc" || tgtType === "doc";
      return isDocEdge ? 120 : 80;
    };

    // Link strength a touch lower to spread things out
    const linkStrength = (l: any) => {
      const srcType = getSrcNode(l)?.type ?? "entity";
      const tgtType = getTgtNode(l)?.type ?? "entity";
      return srcType === "doc" || tgtType === "doc" ? 0.08 : 0.12;
    };

    const sim = d3
      .forceSimulation(simNodes)
      .force(
        "link",
        d3
          .forceLink(simLinks)
          .id((d: any) => d.id) // <- critical: resolve by string id
          .distance(linkDistance as any)
          .strength(linkStrength as any)
      )
      .force("charge", d3.forceManyBody().strength(-160))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide().radius((d: any) => (d.type === "doc" ? 26 : 18)));

    // Visual density: fade things a bit when graphs are busy
    const manyNodes = nodes.length > 60;
    const nodeOpacity = manyNodes ? 0.6 : 0.9;
    const linkOpacity = manyNodes ? 0.35 : 0.55;
    const labelOpacity = manyNodes ? 0.7 : 1;

    // Draw links
    const link = gLinks
      .selectAll("line")
      .data(simLinks)
      .enter()
      .append("line")
      .attr("stroke", "#9aa4b2")
      .attr("stroke-width", 1.2)
      .attr("stroke-opacity", linkOpacity);

    // Draw nodes
    const node = gNodes
      .selectAll("circle")
      .data(simNodes)
      .enter()
      .append("circle")
      .attr("r", (d: any) => (d.type === "doc" ? 10 : 7))
      .attr("fill", (d: any) => (d.type === "doc" ? "#2f6df6" : "#06b6d4"))
      .attr("fill-opacity", nodeOpacity)
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .call(
        d3
          .drag<SVGCircleElement, any>()
          .on("start", (event, d: any) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d: any) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d: any) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .append("title")
      .text((d: any) => d.label || d.id);

    // Labels
    const label = gLabels
      .selectAll("text")
      .data(simNodes)
      .enter()
      .append("text")
      .attr("font-family", "Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial")
      .attr("font-size", (d: any) => (d.type === "doc" ? 12 : 11))
      .attr("stroke", "white")
      .attr("stroke-width", 3)
      .attr("paint-order", "stroke")
      .attr("fill", "#111827")
      .attr("fill-opacity", labelOpacity)
      .attr("pointer-events", "none")
      .text((d: any) => (d.label?.length > 60 ? d.label.slice(0, 57) + "…" : d.label || d.id));

    sim.on("tick", () => {
      link
        .attr("x1", (d: any) => (asNode(d.source)?.x ?? (d.source?.x ?? 0)))
        .attr("y1", (d: any) => (asNode(d.source)?.y ?? (d.source?.y ?? 0)))
        .attr("x2", (d: any) => (asNode(d.target)?.x ?? (d.target?.x ?? 0)))
        .attr("y2", (d: any) => (asNode(d.target)?.y ?? (d.target?.y ?? 0)));

      gNodes
        .selectAll<SVGCircleElement, any>("circle")
        .attr("cx", (d: any) => d.x)
        .attr("cy", (d: any) => d.y);

      label.attr("x", (d: any) => d.x + 12).attr("y", (d: any) => d.y + 4);
    });

    return () => {
      sim.stop();
    };
  }, [nodes, edges, nodeById, dims]);

  return (
    <div ref={containerRef} style={{ width: "100%", height, borderRadius: 8, overflow: "hidden", background: "#fafafa" }}>
      <svg ref={svgRef} width={"100%"} height={height} style={{ display: "block" }} />
    </div>
  );
}
