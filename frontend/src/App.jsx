import { useEffect, useState } from "react";
import { api } from "./api.js";
import LineageGraph from "./LineageGraph.jsx";

const EXAMPLE = `INSERT INTO marts.daily_orders
SELECT DATE(order_ts) AS day, COUNT(*) AS orders
FROM staging.orders
GROUP BY 1;`;

export default function App() {
  const [graph, setGraph] = useState({ nodes: [], edges: [], has_cycles: false });
  const [queries, setQueries] = useState([]);
  const [selected, setSelected] = useState(null);
  const [impact, setImpact] = useState(null);
  const [upstream, setUpstream] = useState([]);
  const [name, setName] = useState("");
  const [sql, setSql] = useState(EXAMPLE);
  const [error, setError] = useState("");

  const refresh = async () => {
    const [g, q] = await Promise.all([api.lineage(), api.queries()]);
    setGraph(g);
    setQueries(q);
  };

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  const select = async (id) => {
    if (id === selected) {
      setSelected(null);
      setImpact(null);
      setUpstream([]);
      return;
    }
    setSelected(id);
    try {
      const [imp, up] = await Promise.all([api.impact(id), api.upstream(id)]);
      setImpact(imp);
      setUpstream(up);
    } catch (e) {
      setError(e.message);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.addQuery(name || "ad-hoc query", sql);
      setName("");
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    await api.deleteQuery(id);
    setSelected(null);
    setImpact(null);
    setUpstream([]);
    await refresh();
  };

  const impactedSet = new Set(impact?.affected.map((a) => a.dataset) ?? []);
  const upstreamSet = new Set(upstream.map((u) => u.dataset));

  return (
    <div className="app">
      <header>
        <h1>Data Lineage Explorer</h1>
        <span className="muted">
          {graph.nodes.length} datasets · {graph.edges.length} dependencies · {queries.length} queries
          {graph.has_cycles && <strong className="warn"> · cycle detected</strong>}
        </span>
      </header>

      {error && <div className="error" onClick={() => setError("")}>{error}</div>}

      <section className="card">
        <div className="legend">
          Click a dataset to see impact analysis.
          <span className="chip upstream">upstream</span>
          <span className="chip selected">selected</span>
          <span className="chip impacted">impacted downstream</span>
        </div>
        <LineageGraph graph={graph} selected={selected} impacted={impactedSet} upstream={upstreamSet} onSelect={select} />
      </section>

      <div className="grid">
        <section className="card">
          <h2>Impact analysis</h2>
          {!impact ? (
            <p className="muted">Select a dataset in the graph.</p>
          ) : (
            <>
              <p>
                A schema change to <code>{impact.dataset}</code> affects <strong>{impact.total_affected}</strong>{" "}
                downstream dataset(s), {impact.direct_dependents} directly.
              </p>
              {impact.affected.length > 0 && (
                <table>
                  <thead>
                    <tr><th>Dataset</th><th>Hops</th><th>Severity</th><th>Path</th></tr>
                  </thead>
                  <tbody>
                    {impact.affected.map((a) => (
                      <tr key={a.dataset}>
                        <td><code>{a.dataset}</code></td>
                        <td>{a.distance}</td>
                        <td><span className={`sev ${a.severity}`}>{a.severity}</span></td>
                        <td className="path">{a.path.join(" → ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>

        <section className="card">
          <h2>Add SQL</h2>
          <form onSubmit={submit}>
            <input placeholder="Query name" value={name} onChange={(e) => setName(e.target.value)} />
            <textarea rows={8} value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false} />
            <button type="submit">Parse &amp; add lineage</button>
          </form>
          <h2>Queries</h2>
          <ul className="queries">
            {queries.map((q) => (
              <li key={q.id}>
                <span>
                  <strong>{q.name}</strong>{" "}
                  <span className="muted">{q.sources.join(", ") || "—"} → {q.target || "(select)"}</span>
                </span>
                <button className="link" onClick={() => remove(q.id)}>delete</button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
