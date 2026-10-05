# Project Workflow

Living document. Update it whenever the process or the increment status changes.

Audited 2026-10-01. Status is evidence-based, not a count of existing files.
See [IMPLEMENTATION_AUDIT.md](IMPLEMENTATION_AUDIT.md) for findings and verification.

Database update 2026-10-02: local Docker databases/pgAdmin are healthy; migration
`20261002_0007` applied; graph backfill and administrator migration are complete. Isolated migration/graph and
authenticated API persistence tests pass. See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).
The October 1 status table below is historical; model/public-deployment gates stay
open. `JobBridge-GraphSync` was disabled and stopped at the user's request because
it opened terminal windows every minute. It remains disabled. Do not re-enable
or replace it with another recurring task without explicit approval. Manual sync:

```powershell
Set-Location backend
..\venv\Scripts\python.exe -m app.db.graph_sync --limit 1000
```

### Recruitment Workflows

Verified 2026-10-05 on `feat/recruitment-workflows`; no new migration is needed.

- Recruiter workspace opens My postings. `GET /api/jobs/mine` returns only the
  signed-in employer's roles; list pages show five items using a sixth as lookahead.
  Edit reuses the posting form and preserves closed status, nullable salary bounds,
  authorization requirements, skills and certifications. Closing/reopening uses
  `PATCH /api/jobs/{job_id}/status`, which changes no other job fields.
- Applicants uses `GET /api/jobs/{job_id}/applications`. The owner/admin response
  includes name, location, experience, skills and certifications, not email or raw
  resume text. Status updates use `PATCH /api/jobs/{job_id}/applications/{application_id}`.
  Submitted can become reviewing, shortlisted or rejected; reviewing can become
  shortlisted or rejected; shortlisted can become hired or rejected. Terminal
  statuses cannot reopen. The UI requests confirmation and locks terminal controls.
- Candidate My applications is directly available at `/candidate?view=applications`.
  `GET /api/candidates/me/applications` returns the candidate's application status,
  timestamps, job title/location/status and employer name. These reads do not score
  candidates. Recruiter updates appear after refresh, independently of saved activity.
  The ordinary For you dashboard and application-submission scoring are unchanged.
- All three lists have separate five-item pagination and loading/error/empty states.
  Candidate tabs use a single Tab stop, arrow/Home/End focus navigation and manual
  Enter/Space activation, so merely moving focus does not fetch a scoring dashboard.

Checks: 65 regular backend tests passed (3 opt-in database tests skipped in that
run); those 3 database tests passed separately with `RUN_DATABASE_MIGRATION_TESTS=1`.
Frontend production build and edited-page diagnostics pass. Browser checks covered
creation, closed-job editing with field preservation, reopening, applicant details,
reviewing/shortlisted/hired, candidate refresh, terminal locking, all three pagers,
keyboard tabs and refresh recovery after a simulated HTTP 503. Recruiter pipeline
and candidate applications had no page overflow at settled 320/390/1440px viewports;
desktop/mobile screenshots were inspected. Workflow reads made zero dashboard or
evaluation requests. Browser application records were seeded directly; API submission
is covered by PostgreSQL integration tests with scoring mocked, not by live inference
or a browser submission test. Temporary records were removed. Broader screen-reader,
contrast, remote CI and clean-machine acceptance remain open. No training, model
changes, deployment or recurring-task changes were made.

### Local Operations

- The optional `backend/install_graph_sync_task.ps1` is NOT part of normal setup:
  recurring console launches are not approved. Check Task Scheduler or
  `Get-ScheduledTaskInfo -TaskName JobBridge-GraphSync`.
- Completion status: `%LOCALAPPDATA%\JobBridge\graph-sync-status.json`, containing
  time/status/count only, no credentials or profile content. Task result 267009
  means still running, not success; compare the status-file timestamp.
- Remove when no longer needed using
  `Unregister-ScheduledTask -TaskName JobBridge-GraphSync -Confirm:$false`.
- Administrator account recovery is assisted, not email-based: use the independent
  Account recovery search (name, company or email), which includes suspended accounts
  and has its own five-item pagination. Suspended accounts require an explicit confirmed
  Reactivate action before Reset password becomes available. The separate Accounts
  table search does not affect recovery results. Re-enter your admin password, securely deliver
  the 15-minute link. The recipient sets a new password on the auth page. The token
  is held in a fragment, captured and removed; it is single-use and stored hashed.
- Admin recovery cannot reset another admin. Use a controlled local recovery
  procedure for administrator lockout; no public admin signup or promotion exists.
- Ontology editing requires admin role; supply a provenance/source for skill and
  link updates. Nodes are not deleted by the UI. Current listing caps each result
  set at 200; use search for narrower results.
- Admin lists show five items per page with independent controls for recovery,
  accounts, recent opportunities/activity, skills and relationships. Totals and
  health appear first. Ontology editing forms start collapsed and open on Edit.
  Recent-job/activity paging uses the existing overview results, not unlimited
  history; backend result limits and permissions are unchanged.
- Run `python data_pipeline/validate_model_contract.py` from the repository root.
  Nonzero exit currently means the historical training/serving formulas differ.
  It does not train, run notebook cells or alter artifacts.

### Readiness Evidence

2026-10-04: 65 backend tests pass from the backend working directory, including
isolated migration/graph/saved-evaluation tests. Frontend production build passes.
CI installs `backend/requirements-dev.txt` and runs frontend `npm ci`/build plus
database integration checks. A remote green run is not yet verified.

Match Analysis reads `GET /api/matches/jobs/{job_id}` on load/refresh. Only the
Evaluate candidates command sends the evaluation POST. Saved responses include
evaluation time, matched/missing skills and model provenance. The separate graph
shows current Neo4j relationships, not a reconstruction of historic scores.
Graph failure does not erase saved results. No training or weight changes occurred.

One local performance sample: cold offline-cached evaluation 63.034 seconds;
saved read 0.091 seconds. This does not establish NFR latency or model quality.
Browser load/refresh sent zero evaluation POSTs. Graph pixel checks and zoom/fit
passed; explicit evaluation returned HTTP 200 after a cold-start automation timeout.
After layout constraints, the settled 390px viewport had equal client/scroll widths
(375px), three graph canvases and no page errors. Screenshot capture was tiled and
unreliable. Full visual/accessibility/performance sign-off remains open.

Earlier 2026-10-02 backend suite: 59 passed after targeted dependency upgrades. Frontend
production build passed. Live job close/reopen and ontology operations passed;
password reset issued in the admin UI and completed with HTTP 200 via browser
form submission (pointer automation was unreliable). No training was performed.
Known-vulnerability scans: `python -m pip_audit --progress-spinner off` and
`npm --prefix frontend audit --omit=dev` both reported no known vulnerabilities
at this check. This is not a penetration test or a guarantee against unknown flaws.

Security remains a bounded demo baseline: rate-limit counters are in-memory per
process and reset on restart; use shared storage before multiple API workers.
Only trust proxy headers from a controlled reverse proxy. Resume parsing is
thread-offloaded with PDF page and DOCX expansion limits, not process-isolated
with a hard CPU/memory budget. Distributed audit atomicity/retention, email delivery,
independent quality/fairness and public hosting remain open.

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
- Use area-focused branches for substantial work, such as
  `feat/database-workflows` for schema, migrations and graph persistence.
- Group commits by ownership: `db`, `backend`, `data`, `frontend`, and `docs`.
  Include directly related tests with their implementation; do not mix unrelated
  file areas into a catch-all commit.
- Merge prerequisite area branches before their dependent API/UI changes.
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
