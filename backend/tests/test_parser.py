import pytest

from app.parser import SQLParseError, parse_sql


def test_insert_select_with_join():
    [r] = parse_sql("INSERT INTO mart.sales SELECT * FROM stg.orders o JOIN stg.items i ON o.id = i.order_id")
    assert r.target == "mart.sales"
    assert r.sources == ["stg.items", "stg.orders"]


def test_cte_names_are_not_sources():
    [r] = parse_sql(
        "CREATE TABLE core.t AS WITH x AS (SELECT * FROM raw.a) SELECT * FROM x JOIN raw.b ON true"
    )
    assert r.target == "core.t"
    assert r.sources == ["raw.a", "raw.b"]


def test_create_view_and_subquery():
    [r] = parse_sql("CREATE VIEW v AS SELECT * FROM (SELECT id FROM s.t1) q WHERE id IN (SELECT id FROM s.t2)")
    assert r.target == "v"
    assert r.sources == ["s.t1", "s.t2"]


def test_plain_select_has_no_target():
    [r] = parse_sql("SELECT * FROM a.b")
    assert r.target is None
    assert r.sources == ["a.b"]


def test_multiple_statements():
    out = parse_sql("INSERT INTO b SELECT * FROM a; INSERT INTO c SELECT * FROM b;")
    assert [(r.target, r.sources) for r in out] == [("b", ["a"]), ("c", ["b"])]


def test_names_are_case_insensitive():
    [r] = parse_sql("INSERT INTO Stg.Orders SELECT * FROM RAW.Orders")
    assert (r.target, r.sources) == ("stg.orders", ["raw.orders"])


def test_invalid_sql_raises():
    with pytest.raises(SQLParseError):
        parse_sql("SELEC FROM WHERE (")
