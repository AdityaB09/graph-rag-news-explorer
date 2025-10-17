// services/frontend/components/TimelineChart.tsx
"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import dayjs from "dayjs";

export type Point = { t: number; v: number };

type Props = {
  title?: string;
  points: Point[]; // epoch millis + value
  height?: string;
};

export default function TimelineChart({ title = "Activity", points, height = "360px" }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    chartRef.current = echarts.init(ref.current);
    return () => chartRef.current?.dispose();
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;

    const sorted = [...points].sort((a, b) => a.t - b.t);
    const x = sorted.map((p) => dayjs(p.t).format("MMM D"));
    const y = sorted.map((p) => p.v);

    chartRef.current.setOption({
      title: { text: title, left: "left" },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: x },
      yAxis: { type: "value" },
      series: [
        {
          type: "line",
          data: y,
          symbol: "circle",
          symbolSize: 6,
          smooth: true,
          areaStyle: {},
        },
      ],
      grid: { left: 40, right: 20, top: 60, bottom: 40 },
    });
  }, [title, points]);

  return <div ref={ref} style={{ width: "100%", height }} />;
}
