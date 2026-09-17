# Project Workflow

Living document. Update it whenever the process or the increment status changes.

## 1. Environment

| Component | Where it runs | Notes |
| --- | --- | --- |
| PostgreSQL 16 | Docker (`workforce-postgres`) | Host port 5433 |
| Neo4j 5 Community | Docker (`workforce-neo4j`) | Bolt 7687, Browser 7474 |
| FastAPI backend | Local venv (`venv`) | `uvicorn main:app --reload` from `backend/` |
| React frontend | Local (planned) | Vite dev server on 5173 |
| Model training | Google Colab | Notebooks under `notebooks/`, artifacts pulled into the repo |

Google Colab is used only for training and experimentation. The trained artifacts
(embeddings, model configs, evaluation reports) are exported and consumed by the
FastAPI backend running locally; no training code runs in the API request path.

## 2. Daily Loop

```powershell
docker compose up -d                 # start databases
.\venv\Scripts\Activate.ps1          # activate Python env
Set-Location backend; alembic upgrade head
uvicorn main:app --reload
```

Shut down with `docker compose down` (add `-v` only when you intend to wipe data).

## 3. Branching

- `main` holds reviewed, working increments.
- Feature work happens on `feat/<short-topic>`; fixes on `fix/<short-topic>`;
  docs/infra on `chore/<short-topic>`.
- One increment per branch, merged into `main` through a pull request.

## 4. Commit Convention

Conventional Commits:

```
<type>(<scope>): <imperative summary>
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`.
Scopes used so far: `backend`, `db`, `infra`, `frontend`, `ml`, `docs`.

Examples:

- `feat(backend): add JWT auth endpoints`
- `chore(infra): move postgres to host port 5433`

## 5. Database Changes

Schema changes go through Alembic only — never hand-edited SQL against the container.

```powershell
Set-Location backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Neo4j ontology changes are captured as versioned Cypher scripts once the knowledge
base design is finalised.

## 6. Increment Plan

| # | Increment | Status |
| --- | --- | --- |
| 1 | Backend shell, relational schema, Alembic, Docker services | Done |
| 2 | Local environment provisioning and verification | Done |
| 3 | Dataset decision and ingestion pipeline | Pending |
| 4 | Auth and role-based access (FR-01) | Pending |
| 5 | Resume ingestion and parsing (FR-02) | Pending |
| 6 | Job posting and weighting criteria (FR-03) | Pending |
| 7 | Neo4j skill ontology and graph service | Pending |
| 8 | Tier 1 rule filter + Tier 2 semantic scoring (FR-04) | Pending |
| 9 | Results and explainability API + React dashboards (FR-05) | Pending |
| 10 | Evaluation pipeline (precision / recall / F1) | Pending |

## 7. Deferred Decisions

- Final dataset selection
- CV verification and bias handling
- Knowledge base / ontology scope
- Frontend theme and design system
