"""Lineage graph built with NetworkX, plus upstream/downstream and impact analysis."""
from __future__ import annotations

from collections.abc import Iterable

import networkx as nx


def build_graph(edges: Iterable[tuple[str, str, int]]) -> nx.DiGraph:
    """edges: (source, target, query_id). Edge direction = data flow."""
    g = nx.DiGraph()
    for source, target, query_id in edges:
        if g.has_edge(source, target):
            g[source][target]["query_ids"].add(query_id)
        else:
            g.add_edge(source, target, query_ids={query_id})
    return g


def layers(g: nx.DiGraph) -> dict[str, int]:
    """Assign each node a column (longest path from a root) for left-to-right layout."""
    if not nx.is_directed_acyclic_graph(g):
        # Fall back to BFS depth from roots when cycles exist.
        roots = [n for n in g if g.in_degree(n) == 0] or list(g)[:1]
        depth: dict[str, int] = {}
        for r in roots:
            for node, d in nx.single_source_shortest_path_length(g, r).items():
                depth[node] = max(depth.get(node, 0), d)
        return depth
    depth = {}
    for node in nx.topological_sort(g):
        preds = list(g.predecessors(node))
        depth[node] = 0 if not preds else max(depth[p] for p in preds) + 1
    return depth


def to_payload(g: nx.DiGraph) -> dict:
    layer = layers(g)
    return {
        "nodes": [
            {
                "id": n,
                "layer": layer.get(n, 0),
                "kind": "source" if g.in_degree(n) == 0 else ("sink" if g.out_degree(n) == 0 else "intermediate"),
            }
            for n in sorted(g)
        ],
        "edges": [
            {"source": s, "target": t, "query_ids": sorted(d["query_ids"])}
            for s, t, d in g.edges(data=True)
        ],
        "has_cycles": not nx.is_directed_acyclic_graph(g),
    }


def _require(g: nx.DiGraph, dataset: str) -> None:
    if dataset not in g:
        raise KeyError(dataset)


def upstream(g: nx.DiGraph, dataset: str) -> list[dict]:
    _require(g, dataset)
    dist = nx.single_source_shortest_path_length(g.reverse(copy=False), dataset)
    return sorted(
        ({"dataset": n, "distance": d} for n, d in dist.items() if n != dataset),
        key=lambda x: (x["distance"], x["dataset"]),
    )


def downstream(g: nx.DiGraph, dataset: str) -> list[dict]:
    _require(g, dataset)
    dist = nx.single_source_shortest_path_length(g, dataset)
    return sorted(
        ({"dataset": n, "distance": d} for n, d in dist.items() if n != dataset),
        key=lambda x: (x["distance"], x["dataset"]),
    )


def impact_analysis(g: nx.DiGraph, dataset: str) -> dict:
    """Which downstream datasets break if `dataset`'s schema changes, and how."""
    _require(g, dataset)
    paths = nx.single_source_shortest_path(g, dataset)
    affected = []
    for node, path in paths.items():
        if node == dataset:
            continue
        distance = len(path) - 1
        affected.append(
            {
                "dataset": node,
                "distance": distance,
                "path": path,
                "severity": "high" if distance == 1 else ("medium" if distance == 2 else "low"),
                "is_terminal": g.out_degree(node) == 0,
                "queries_to_review": sorted(g[path[-2]][node]["query_ids"]),
            }
        )
    affected.sort(key=lambda x: (x["distance"], x["dataset"]))
    return {
        "dataset": dataset,
        "total_affected": len(affected),
        "direct_dependents": sum(1 for a in affected if a["distance"] == 1),
        "terminal_datasets": [a["dataset"] for a in affected if a["is_terminal"]],
        "affected": affected,
    }
