from pathlib import Path

SAMPLE = (Path(__file__).resolve().parents[2] / "sample_data" / "warehouse_etl.sql").read_text()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_and_lineage(client):
    r = client.post("/api/queries", json={"name": "etl", "sql": SAMPLE})
    assert r.status_code == 201
    assert len(r.json()) == 8

    lineage = client.get("/api/lineage").json()
    ids = {n["id"] for n in lineage["nodes"]}
    assert {"raw.crm_customers", "core.fact_sales", "reporting.exec_dashboard"} <= ids
    assert lineage["has_cycles"] is False


def test_impact_endpoint(client):
    client.post("/api/queries", json={"name": "etl", "sql": SAMPLE})
    report = client.get("/api/impact/raw.shop_orders").json()
    affected = {a["dataset"] for a in report["affected"]}
    assert "reporting.exec_dashboard" in affected
    assert "staging.customers" not in affected
    assert report["terminal_datasets"] == ["reporting.exec_dashboard"]


def test_upstream_endpoint(client):
    client.post("/api/queries", json={"name": "etl", "sql": SAMPLE})
    up = {d["dataset"] for d in client.get("/api/lineage/marts.customer_ltv/upstream").json()}
    assert up == {"core.fact_sales", "staging.orders", "staging.order_items",
                  "raw.shop_orders", "raw.shop_order_items", "raw.product_catalog"}


def test_delete_query_removes_edges(client):
    [q] = client.post("/api/queries", json={"name": "one", "sql": "INSERT INTO b SELECT * FROM a"}).json()
    assert client.delete(f"/api/queries/{q['id']}").status_code == 204
    assert client.get("/api/lineage").json()["edges"] == []


def test_bad_sql_and_unknown_dataset(client):
    assert client.post("/api/queries", json={"name": "bad", "sql": "SELEC FROM ("}).status_code == 422
    assert client.get("/api/impact/missing.table").status_code == 404
