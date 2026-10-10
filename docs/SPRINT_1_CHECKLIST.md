# Sprint 1: Data Preparation and Development Environment

Status: Local runtime and reviewed main CI verified; full setup/browser sign-off pending.
Update 2026-10-10: inspected successful main CI at
`aae5809ba38b1847636f206f9b0ed01a8b4ddf41`,
[run 37955892189](https://github.com/DiorWachira/Hybrid-AI-Powered-Matching-and-Recommendation-Engine/actions/runs/37955892189).
Fresh hosted jobs installed Python 3.12 and Node 22 dependencies, validated Compose,
applied migrations, ran backend tests and built the frontend. This is clean hosted
build/test evidence, not a full desktop setup or browser walkthrough.
Local focused checks: 3 health/ontology tests, 9 Week 4 data-tool tests and 1
DOCX-to-PostgreSQL-to-Neo4j integration test passed. Updated Compose health settings
passed actual startup without deleting volumes; Neo4j took about 232 seconds.
The new branch changes have focused local test evidence but have not run in remote CI.

Earlier dated updates below describe the evidence available at those times.
Update 2026-10-04: 65 backend tests pass from CI's backend working directory;
frontend build passes. Fixed data_pipeline import root, declared test dependencies,
and added frontend build/database integration CI steps. No remote run was claimed.
Update 2026-10-02: local database health, migration and graph integration checks
now pass; the runtime blocker recorded below has been resolved locally. Full
Sprint 1 closure still awaits a clean-checkout run and reviewed remote CI evidence.
See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for the applied schema and tests.
Audit: 2026-10-01. See [implementation audit](IMPLEMENTATION_AUDIT.md).

## Requirements checklist

- [x] Local development environment: database/graph integration and frontend build
    pass on 2026-10-04. Clean-machine reproduction remains a separate gate.
- [x] Codebase organisation: backend, frontend, data pipeline, notebooks, tests,
  documentation, and CI configuration are separated into clear directories.
- [x] Git version control scaffolding: feature branch and CI configuration exist.
    No push or main merge is authorized by this commit-only step.
- [x] Synthetic resources: generator, quality report, migrations, ontology seed
    logic and historical weights exist. This does not certify real-job sourcing,
    official CDACC mappings, model quality or the live scoring feature contract.
- [x] Reviewed baseline automation: backend and frontend CI passed on main aae5809,
    including fresh dependency installation, migrations and database integration.
- [ ] Publish and verify remote CI for the new Week 1-4 branch when authorized.
- [ ] Full clean-machine setup with seed data, launched API/Vite and browser checks.

## Historical Evidence (2026-10-01)

- 30 database-independent pytest tests passed.
- Frontend TypeScript/Vite production build passed.
- `docker compose config --quiet` passed (syntax/configuration only).
- `docker compose ps` failed: Docker Desktop Linux engine pipe unavailable.
- Direct request to `http://127.0.0.1:8000/api/health` could not connect.
- Two database integration tests were deliberately not run against an unavailable
    stack. Earlier successful local runs are historical evidence, not current proof.

Sprint 1 is not yet fully signed off. The inspected hosted CI gate is satisfied for
main aae5809; complete desktop setup/seed/browser reproduction and the new branch's
remote run remain open. No native PostgreSQL configuration was changed.

## Local verification

Run these commands from the repository root in PowerShell:

```powershell
docker compose up -d
docker compose ps
& .\venv\Scripts\python.exe -m compileall backend
Set-Location backend
& ..\venv\Scripts\alembic.exe upgrade head
& ..\venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run build
```

Docker Desktop must be running before the first command. The frontend build and
Python compilation can run without the database containers.

Start the backend and frontend using [WORKFLOW.md](WORKFLOW.md), then require
`/api/health` through both port 8000 and the Vite `/api` proxy to report both
databases `ok`. An HTTP 200 alone is insufficient: the current health route also
returns 200 with `status: degraded`. Record the commit, command outcomes, migration
head and one repeated ontology-seed result before changing this status to complete.