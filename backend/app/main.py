import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import graph as lg
from .db import LineageEdge, Query, SessionLocal, get_session, init_db
from .parser import SQLParseError, parse_sql

SAMPLE_SQL = Path(os.getenv("SAMPLE_SQL_PATH", Path(__file__).resolve().parents[2] / "sample_data" / "warehouse_etl.sql"))


class QueryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sql: str = Field(min_length=1)
    dialect: str = "postgres"


class QueryOut(BaseModel):
    id: int
    name: str
    statement_type: str
    target: str | None
    sources: list[str]


def ingest(session: Session, name: str, sql: str, dialect: str = "postgres") -> list[Query]:
    try:
        parsed = parse_sql(sql, dialect)
    except SQLParseError as e:
        raise HTTPException(status_code=422, detail=f"Could not parse SQL: {e}") from e
    if not parsed:
        raise HTTPException(status_code=422, detail="No SQL statements found")

    created = []
    for i, stmt in enumerate(parsed, start=1):
        q = Query(
            name=name if len(parsed) == 1 else f"{name} #{i}",
            sql_text=stmt.sql,
            statement_type=stmt.statement_type,
            target=stmt.target,
        )
        if stmt.target:
            q.edges = [LineageEdge(source=s, target=stmt.target) for s in stmt.sources]
        session.add(q)
        created.append(q)
    session.commit()
    return created


def to_out(q: Query) -> QueryOut:
    return QueryOut(
        id=q.id, name=q.name, statement_type=q.statement_type, target=q.target,
        sources=sorted(e.source for e in q.edges),
    )


def current_graph(session: Session):
    rows = session.execute(select(LineageEdge.source, LineageEdge.target, LineageEdge.query_id)).all()
    return lg.build_graph(rows)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.getenv("SEED_SAMPLE", "false").lower() == "true" and SAMPLE_SQL.exists():
        with SessionLocal() as s:
            if s.scalar(select(Query.id).limit(1)) is None:
                ingest(s, "warehouse_etl", SAMPLE_SQL.read_text())
    yield


app = FastAPI(title="Enterprise Data Lineage Explorer", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/queries", response_model=list[QueryOut], status_code=201)
def add_query(body: QueryIn, session: Session = Depends(get_session)):
    return [to_out(q) for q in ingest(session, body.name, body.sql, body.dialect)]


@app.get("/api/queries", response_model=list[QueryOut])
def list_queries(session: Session = Depends(get_session)):
    return [to_out(q) for q in session.scalars(select(Query).order_by(Query.id))]


@app.delete("/api/queries/{query_id}", status_code=204)
def delete_query(query_id: int, session: Session = Depends(get_session)):
    q = session.get(Query, query_id)
    if q is None:
        raise HTTPException(404, "Query not found")
    session.delete(q)
    session.commit()


@app.get("/api/lineage")
def full_lineage(session: Session = Depends(get_session)):
    return lg.to_payload(current_graph(session))


@app.get("/api/datasets")
def datasets(session: Session = Depends(get_session)):
    return sorted(current_graph(session).nodes)


def _with_dataset(fn, dataset: str, session: Session):
    try:
        return fn(current_graph(session), dataset.lower())
    except KeyError:
        raise HTTPException(404, f"Dataset '{dataset}' not found in lineage graph") from None


@app.get("/api/lineage/{dataset}/upstream")
def get_upstream(dataset: str, session: Session = Depends(get_session)):
    return _with_dataset(lg.upstream, dataset, session)


@app.get("/api/lineage/{dataset}/downstream")
def get_downstream(dataset: str, session: Session = Depends(get_session)):
    return _with_dataset(lg.downstream, dataset, session)


@app.get("/api/impact/{dataset}")
def get_impact(dataset: str, session: Session = Depends(get_session)):
    return _with_dataset(lg.impact_analysis, dataset, session)
