# Hybrid AI-Powered Workforce Placement Engine

JobBridge is an ICS II prototype combining rule-based eligibility, local ML scoring,
and graph-based skill explanations for workforce placement.

## Current Increment

Public entry (2026-10-04): `/` now opens the JobBridge landing page with candidate
and recruiter signup paths, About, approach, FAQs and project feedback links.
`/privacy` and `/terms` describe prototype data handling and use limits. Existing
workspaces remain authenticated; public pages do not depend on API availability.

Matching increment (2026-10-04): saved evaluations load without rerunning inference;
matched/missing skills and model provenance are displayed, with a separate current
Neo4j skill graph. Evaluation is an explicit button action. No epoch training ran.

Database increment (2026-10-02): application workflow tables, eligibility fields,
owner-protected management APIs, persistent match details and a transactional
Neo4j sync queue are implemented. Migration `20261002_0007` is applied locally.
See [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) for the ER/graph design,
pgAdmin connection details, verification and required graph-worker command.

Implemented on the feature branch, with verification gaps documented in
[docs/IMPLEMENTATION_AUDIT.md](docs/IMPLEMENTATION_AUDIT.md):

- FastAPI authentication, candidate profiles/resume parsing, jobs and match APIs
- React candidate/recruiter workspaces and admin monitoring/moderation/ontology controls
- Admin-assisted single-use password recovery, session revocation and request throttling
- PostgreSQL/Alembic persistence and Neo4j projection/ontology tooling
- Synthetic data preparation and historical model artifacts
- Rule, data-tool and API-boundary tests plus backend CI configuration

Automatic graph sync is disabled at the user's request to stop repeated terminals.
Run the one-shot worker manually. See [docs/WORKFLOW.md](docs/WORKFLOW.md) for
status checks and operational limits. `data_pipeline/validate_model_contract.py`
currently fails feature parity; no retraining or public deployment has occurred.

## Explicitly Deferred

Not yet signed off:

- Current live stack/clean-machine verification and public deployment
- Training/serving feature parity and independently measured model quality
- Real Colab epoch training and Drive checkpoint recovery (training is on hold)
- Privacy/fairness evaluation, abuse controls and robust graph consistency
- Complete real-backend UI workflow and performance tests

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

6. In another terminal at the repository root, start the frontend:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the backend. Both databases
must be reachable; a build or loaded auth page does not prove live matching works.
The root `.env` is loaded regardless of the backend launch directory.
For tests and data tools, install `pip install -r backend/requirements-dev.txt`.
CI uses that manifest and runs a separate frontend build with `npm ci`.
The training notebook is intentionally local/ignored and not present in a fresh
checkout. Notebook-dependent model-contract checks require that local file.

Public hosting is not active. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the
Always Free-only proposal and required deployment gates. Do not expose the Vite
server, database viewers, default credentials or seed accounts publicly.

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
