'use client';
import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

export default function Timeline() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption({
      title: { text: 'Activity (demo)' },
      xAxis: { type: 'category', data: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: [5,12,9,20,18,10,7] }]
    });
    return () => { chart.dispose(); };
  }, []);
  return <div ref={ref} style={{width: '100%', height: 360, border: '1px solid #eee'}} />;
}
