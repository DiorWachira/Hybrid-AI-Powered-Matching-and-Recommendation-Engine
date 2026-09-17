# Hybrid AI-Powered Workforce Placement Engine

Initial scaffold for an ICS II project: a web-based matching and recommendation engine for intelligent workforce placement.

## Current Increment

This branch starts the backend and database foundation only:

- FastAPI application shell
- PostgreSQL connection settings
- SQLAlchemy ORM models for the core relational schema
- Alembic migration setup with an initial schema migration
- Docker Compose services for PostgreSQL and Neo4j

## Explicitly Deferred

The following decisions are intentionally not implemented yet:

- Dataset final decision
- Model training
- CV upload behavior aligned to the final dataset
- CV verification and bias handling
- Knowledge base / ontology establishment
- Project webpage theme

## Local Setup

Prerequisites: Docker Desktop (running), Python 3.12+, Node.js 20+, Git.

1. Copy `.env.example` to `.env` and adjust values if needed.
2. Start databases:

```powershell
docker compose up -d postgres neo4j
```

3. Create and activate a Python environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

4. Apply database migrations:

```powershell
Set-Location backend
alembic upgrade head
```

5. Run the API:

```powershell
uvicorn main:app --reload
```

The API health endpoint is available at `http://127.0.0.1:8000/api/health`.

## Service Endpoints

| Service | Host address | Credentials |
| --- | --- | --- |
| PostgreSQL | `localhost:5433` | `workforce` / `workforce` |
| Neo4j Bolt | `bolt://localhost:7687` | `neo4j` / `workforce-password` |
| Neo4j Browser | `http://localhost:7474` | `neo4j` / `workforce-password` |
| FastAPI | `http://127.0.0.1:8000` | - |

PostgreSQL is published on host port **5433** because port 5432 is commonly occupied by a
locally installed PostgreSQL service. Override with `POSTGRES_PORT` in `.env` if needed.

## Verifying the Stack

```powershell
docker compose ps
docker exec workforce-postgres psql -U workforce -d workforce -c "\dt"
docker exec workforce-neo4j cypher-shell -u neo4j -p workforce-password "RETURN 1 AS ok;"
```

## Project Workflow

Branching, commit conventions, and the increment plan are documented in
[docs/WORKFLOW.md](docs/WORKFLOW.md).
