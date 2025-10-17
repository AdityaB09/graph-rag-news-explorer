'use client';
import React, { useEffect, useRef } from 'react';
import { DataSet, Network } from 'vis-network/standalone';

export default function StoryGraph() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const nodes = new DataSet([
      { id: 'ent:TATA', label: 'TATA', shape: 'dot' },
      { id: 'ent:FOX', label: 'Foxconn', shape: 'dot' },
      { id: 'doc:1', label: 'Doc 1', shape: 'box' }
    ]);
    const edges = new DataSet([
      { from: 'doc:1', to: 'ent:TATA' },
      { from: 'doc:1', to: 'ent:FOX' },
      { from: 'ent:TATA', to: 'ent:FOX' }
    ]);
    new Network(ref.current, { nodes, edges }, { physics: { stabilization: true } });
  }, []);
  return <div ref={ref} style={{width: '100%', height: 360, border: '1px solid #eee'}} />;
}
