import pytest

from app import graph as lg

EDGES = [("raw", "stg", 1), ("stg", "core", 2), ("core", "mart_a", 3), ("core", "mart_b", 4), ("mart_a", "dash", 5)]


def test_upstream_and_downstream():
    g = lg.build_graph(EDGES)
    assert [d["dataset"] for d in lg.upstream(g, "core")] == ["stg", "raw"]
    assert [(d["dataset"], d["distance"]) for d in lg.downstream(g, "core")] == [
        ("mart_a", 1), ("mart_b", 1), ("dash", 2),
    ]


def test_impact_analysis():
    report = lg.impact_analysis(lg.build_graph(EDGES), "stg")
    assert report["total_affected"] == 4
    assert report["direct_dependents"] == 1
    assert sorted(report["terminal_datasets"]) == ["dash", "mart_b"]
    dash = next(a for a in report["affected"] if a["dataset"] == "dash")
    assert dash["path"] == ["stg", "core", "mart_a", "dash"]
    assert dash["severity"] == "low"
    assert dash["queries_to_review"] == [5]


def test_layers_and_payload():
    payload = lg.to_payload(lg.build_graph(EDGES))
    layer = {n["id"]: n["layer"] for n in payload["nodes"]}
    assert layer == {"raw": 0, "stg": 1, "core": 2, "mart_a": 3, "mart_b": 3, "dash": 4}
    assert payload["has_cycles"] is False


def test_cycle_detected():
    payload = lg.to_payload(lg.build_graph([("a", "b", 1), ("b", "a", 2)]))
    assert payload["has_cycles"] is True


def test_unknown_dataset():
    with pytest.raises(KeyError):
        lg.impact_analysis(lg.build_graph(EDGES), "nope")
