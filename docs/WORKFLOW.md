# Project Workflow

Living document. Update it whenever the process or the increment status changes.

Audited 2026-10-01. Status is evidence-based, not a count of existing files.
See [IMPLEMENTATION_AUDIT.md](IMPLEMENTATION_AUDIT.md) for findings and verification.

Related documents:

- [ROADMAP.txt](ROADMAP.txt) - the 8-week milestone plan, with current status.
- [DATASET_STRATEGY.md](DATASET_STRATEGY.md) - the decided dataset sourcing approach.
- [extras/marketplace_features.txt](extras/marketplace_features.txt) - client-requested
  marketplace features (apply/accept/contract/project/milestone/payment) deferred
  outside the core matching engine scope.

## 1. Environment

| Component | Where it runs | Notes |
| --- | --- | --- |
| PostgreSQL 16 | Docker (`workforce-postgres`) | Host port 5433 |
| Neo4j 5 Community | Docker (`workforce-neo4j`) | Bolt 7687, Browser 7474 |
| FastAPI backend | Local venv (`venv`) | `uvicorn main:app --reload` from `backend/` |
| React frontend | Local, implemented | Vite 5173 proxies `/api` to FastAPI 8000 |
| Historical model run | Local Python runtime | Saved notebook metrics; not a certified Colab run |
| Next training workflow | Colab planned, execution on hold | GitHub -> Colab -> Drive -> local review; no epoch trainer yet |
| Public demo | Oracle Always Free proposed | No VM, domain or public endpoint provisioned; see [DEPLOYMENT.md](DEPLOYMENT.md) |

Colab is reserved for training and experimentation, not API hosting. The API loads
historical coefficients locally, but its skill/growth formulas currently differ
from training. Passing artifact-loading tests would not prove model parity.
Do not run training or promote weights until explicitly authorized.

## 2. Daily Loop

```powershell
docker compose up -d                 # start databases
.\venv\Scripts\Activate.ps1          # activate Python env
Set-Location backend; alembic upgrade head
uvicorn main:app --reload
```

In a second terminal at the repository root:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The browser calls same-origin `/api`; Vite forwards
those requests locally. This is real HTTP communication, not public hosting.
The Vite development proxy is NOT included in production static builds.
Settings load the repository-root `.env` regardless of launch directory; process
environment variables override it. Keep secrets out of Git and browser variables.

Shut down with `docker compose down` (add `-v` only when you intend to wipe data).

## 3. Branching

- `main` holds reviewed, working increments.
- Feature work happens on `feat/<short-topic>`; fixes on `fix/<short-topic>`;
  docs/infra on `chore/<short-topic>`.
- Keep work on `feat/bootstrap-migration-ready-backend` for this stage.
- Do not merge or push `main` without explicit user permission.
- Review scoped changes before any commit; preserve unrelated notebook/ignore
  edits. Chapter 5 notes and the local epoch workflow plan must not be published.

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
| 1 | Backend shell, relational schema, Alembic, Docker services | Implemented; current DB migration/health verification blocked |
| 2 | Local environment provisioning and verification | Partial; build/tests pass, Docker unavailable; Sprint 1 not signed off |
| 3 | Dataset decision and ingestion pipeline | Partial; synthetic tools tested, real source provenance/official mappings pending |
| 4 | Auth and role-based access (FR-01) | Partial; JWT/roles and job-owner boundary implemented; abuse/session tests pending |
| 5 | Resume ingestion and parsing (FR-02) | Partial; PDF/DOCX extraction exists; adversarial files and live storage/graph tests pending |
| 6 | Job posting and weighting criteria (FR-03) | Partial; create/open-list only, not CRUD; no custom weighting workflow |
| 7 | Neo4j skill ontology and graph service | Partial; seed/query/projection code; stale-edge consistency and live tests pending |
| 8 | Tier 1 rule filter + Tier 2 semantic scoring (FR-04) | Partial; rules-first tested, trained feature parity blocked |
| 9 | Results and explainability API + React dashboards (FR-05) | Partial; built UI, selected fixture checks; live E2E/cached GET/graph UI pending |
| 10 | Evaluation pipeline (precision / recall / F1) | Historical synthetic notebook results only; independent gold data and parity evaluation pending |
| 11 | Epoch workflow and artifact review | Local fake-checkpoint proof only; real trainer/Colab/Drive/resume not verified |
| 12 | Public demo | Not deployed; Always Free account/capacity, TLS, security and live acceptance gates required |

### Stage Gates

1. Infrastructure: disposable DB migration, repeated ontology seed, API health
  through frontend, clean checkout, inspected CI run.
2. Functional/security: owner/role tests, auth failure/expiry tests, real CV upload,
  save/history and job/evaluation persistence, consistent graph failure handling.
3. Model contract: versioned shared features and preprocessing; same input gives
  the same vectors/scores in training and serving. Graph stays explanatory.
4. Training (only after approval): frozen group-disjoint splits; fit scaler on
  train only; fixed epochs, validation loss each epoch, no early stopping;
  checkpoint + JSON each epoch, latest/best selection, verified Drive round-trip,
  exact resume state. No test-based tuning or checkpoint selection.
5. Public demo: approved Always Free resources, secrets/TLS, synthetic-only data,
  abuse controls, real two-user browser/API test and restart persistence.

Do not advance a gate on a build, mock response or historical metric alone.

## 7. Deferred Decisions

- Real dataset permission/provenance and independent labelled evaluation data
- CV verification, privacy retention and measured fairness
- Official ontology mappings and stable graph projection semantics
- Final UI review, accessibility and complete real-backend workflow tests
- Production-grade reliability, moderation and marketplace features
