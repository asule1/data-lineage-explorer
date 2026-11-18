const NODE_W = 175;
const NODE_H = 34;
const COL_GAP = 55;
const ROW_GAP = 18;

function layout(nodes) {
  const cols = {};
  nodes.forEach((n) => (cols[n.layer] ||= []).push(n));
  const pos = {};
  Object.entries(cols).forEach(([layer, list]) => {
    list.forEach((n, i) => {
      pos[n.id] = { x: 20 + Number(layer) * (NODE_W + COL_GAP), y: 20 + i * (NODE_H + ROW_GAP) };
    });
  });
  const maxRows = Math.max(1, ...Object.values(cols).map((l) => l.length));
  const maxLayer = Math.max(0, ...nodes.map((n) => n.layer));
  return {
    pos,
    width: 40 + (maxLayer + 1) * (NODE_W + COL_GAP) - COL_GAP,
    height: 40 + maxRows * (NODE_H + ROW_GAP) - ROW_GAP,
  };
}

export default function LineageGraph({ graph, selected, impacted, upstream, onSelect }) {
  if (!graph.nodes.length) return <p className="muted">No lineage yet. Add a SQL query to get started.</p>;
  const { pos, width, height } = layout(graph.nodes);

  const nodeClass = (id) => {
    if (id === selected) return "node selected";
    if (impacted.has(id)) return "node impacted";
    if (upstream.has(id)) return "node upstream";
    return selected ? "node dim" : "node";
  };
  const edgeActive = (s, t) =>
    (s === selected || impacted.has(s)) && impacted.has(t) ? "edge impacted" :
    (t === selected || upstream.has(t)) && upstream.has(s) ? "edge upstream" : "edge";

  return (
    <div className="graph-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxWidth: width, minWidth: 900 }}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
          </marker>
        </defs>
        {graph.edges.map((e) => {
          const a = pos[e.source], b = pos[e.target];
          const x1 = a.x + NODE_W, y1 = a.y + NODE_H / 2, x2 = b.x, y2 = b.y + NODE_H / 2;
          const mx = (x1 + x2) / 2;
          return (
            <path key={`${e.source}->${e.target}`} className={edgeActive(e.source, e.target)}
              d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} markerEnd="url(#arrow)" />
          );
        })}
        {graph.nodes.map((n) => (
          <g key={n.id} className={nodeClass(n.id)} transform={`translate(${pos[n.id].x},${pos[n.id].y})`}
            onClick={() => onSelect(n.id)}>
            <rect width={NODE_W} height={NODE_H} rx="6" />
            <text x={NODE_W / 2} y={NODE_H / 2 + 4} textAnchor="middle">{n.id}</text>
            <title>{`${n.id} (${n.kind})`}</title>
          </g>
        ))}
      </svg>
    </div>
  );
}
