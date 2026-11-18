# Enterprise Data Lineage Explorer

A metadata service that builds table-level data lineage by parsing SQL, then answers the question every data team asks before a schema change: *what breaks downstream?*

![screenshot](docs/screenshot.png)

## What it does

- **SQL parsing**: `INSERT ... SELECT`, `CREATE TABLE/VIEW AS`, `MERGE`, and `UPDATE` statements are parsed with [sqlglot](https://github.com/tobymao/sqlglot). Source tables are pulled from joins, subqueries, and CTEs (CTE names are excluded so only real datasets show up).
- **Lineage graph**: Dependencies are stored in PostgreSQL and loaded into a NetworkX `DiGraph` for traversal. Cycles are detected and flagged.
- **Impact analysis**: For any dataset, it returns every downstream dependent with hop distance, the exact path, a severity level (direct = high), and the queries that need review.
- **REST API + React UI**: Browse the graph interactively. Click a dataset to highlight its upstream sources and downstream impact.
- **Docker + CI**: `docker compose up` runs Postgres, the API, and the UI. GitHub Actions runs lint and tests against both SQLite and Postgres, builds the frontend, and builds the images.

## Architecture

```
React (Vite) ──► FastAPI ──► sqlglot parser ──► PostgreSQL (queries, lineage_edges)
                    │
                    └──► NetworkX graph ──► upstream / downstream / impact analysis
```

| Path | Purpose |
|---|---|
| `backend/app/parser.py` | SQL → (target, sources) per statement |
| `backend/app/graph.py` | Graph building, layering, upstream/downstream, impact analysis |
| `backend/app/db.py` | SQLAlchemy models |
| `backend/app/main.py` | FastAPI routes |
| `frontend/src/` | React UI (SVG lineage graph, impact table, SQL input) |
| `sample_data/warehouse_etl.sql` | Sample raw → staging → core → marts pipeline |

## Running it

**Docker (recommended)**

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

The sample warehouse ETL is loaded on first start (`SEED_SAMPLE=true`).

**Local dev**

```bash
# backend
cd backend
pip install -r requirements-dev.txt
SEED_SAMPLE=true uvicorn app.main:app --reload    # uses SQLite by default

# frontend (new terminal)
cd frontend
npm install
npm run dev    # http://localhost:5173, proxies /api to :8000
```

Set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db` to use Postgres.

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/queries` | Parse SQL (one or many statements) and store its lineage |
| GET | `/api/queries` | List ingested queries |
| DELETE | `/api/queries/{id}` | Remove a query and its edges |
| GET | `/api/lineage` | Full graph (nodes with layer + kind, edges) |
| GET | `/api/datasets` | All known datasets |
| GET | `/api/lineage/{dataset}/upstream` | Everything the dataset depends on |
| GET | `/api/lineage/{dataset}/downstream` | Everything that depends on the dataset |
| GET | `/api/impact/{dataset}` | Schema-change impact report |

Example:

```bash
curl -X POST localhost:8000/api/queries -H 'Content-Type: application/json' \
  -d '{"name": "daily_orders", "sql": "INSERT INTO marts.daily_orders SELECT * FROM staging.orders"}'

curl localhost:8000/api/impact/staging.orders
```

## Tests

```bash
cd backend && pytest -q
```

Covers the parser (joins, CTEs, subqueries, multi-statement, bad SQL), graph logic (traversal, impact, layering, cycles), and API endpoints.

## Limitations / next steps

- Lineage is table-level. Column-level lineage (sqlglot has `sqlglot.lineage`) would be the natural next step.
- Dynamic SQL and stored procedures aren't parsed.
