"""Parse SQL statements into table-level lineage (source tables -> target table)."""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp


@dataclass
class StatementLineage:
    target: str | None
    sources: list[str] = field(default_factory=list)
    statement_type: str = ""
    sql: str = ""


class SQLParseError(ValueError):
    pass


def _table_name(table: exp.Table) -> str:
    parts = [p for p in (table.catalog, table.db, table.name) if p]
    return ".".join(parts).lower()


def _target_table(stmt: exp.Expression) -> exp.Table | None:
    node = stmt.this if isinstance(stmt, (exp.Insert, exp.Create, exp.Merge, exp.Update)) else None
    if isinstance(node, exp.Schema):  # CREATE TABLE t (cols...) AS ...
        node = node.this
    return node if isinstance(node, exp.Table) else None


def _source_tables(stmt: exp.Expression, target: exp.Table | None) -> list[str]:
    cte_names = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    sources: set[str] = set()
    for table in stmt.find_all(exp.Table):
        if table is target:
            continue
        name = _table_name(table)
        if not name or name in cte_names:
            continue
        sources.add(name)
    if target is not None:
        sources.discard(_table_name(target))
    return sorted(sources)


def parse_sql(sql: str, dialect: str = "postgres") -> list[StatementLineage]:
    """Return lineage for every statement in `sql`.

    Statements that write to a table (INSERT, CREATE TABLE/VIEW AS, MERGE, UPDATE)
    produce a target. Plain SELECTs produce sources with target=None.
    """
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as e:
        raise SQLParseError(str(e)) from e

    results: list[StatementLineage] = []
    for stmt in statements:
        if stmt is None:
            continue
        target = _target_table(stmt)
        if isinstance(stmt, exp.Create) and target is None:
            continue  # e.g. CREATE INDEX / FUNCTION
        results.append(
            StatementLineage(
                target=_table_name(target) if target is not None else None,
                sources=_source_tables(stmt, target),
                statement_type=stmt.key.upper(),
                sql=stmt.sql(dialect=dialect),
            )
        )
    return results
