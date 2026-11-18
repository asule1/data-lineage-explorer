const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  lineage: () => request("/api/lineage"),
  queries: () => request("/api/queries"),
  addQuery: (name, sql) => request("/api/queries", { method: "POST", body: JSON.stringify({ name, sql }) }),
  deleteQuery: (id) => request(`/api/queries/${id}`, { method: "DELETE" }),
  impact: (dataset) => request(`/api/impact/${encodeURIComponent(dataset)}`),
  upstream: (dataset) => request(`/api/lineage/${encodeURIComponent(dataset)}/upstream`),
};
