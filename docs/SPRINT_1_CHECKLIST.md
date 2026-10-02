# Sprint 1: Data Preparation and Development Environment

Status: Source preparation substantially complete; runtime sign-off BLOCKED.
Audit: 2026-10-01. See [implementation audit](IMPLEMENTATION_AUDIT.md).

## Requirements checklist

- [ ] Development environment sign-off: configuration is present and the local
    Python tests/frontend build pass, but Docker Engine is currently unavailable.
    PostgreSQL/Neo4j connectivity and migrations must be reverified.
- [x] Codebase organisation: backend, frontend, data pipeline, notebooks, tests,
  documentation, and CI configuration are separated into clear directories.
- [x] Git version control scaffolding: feature branch and CI configuration exist.
    No merge or push to main is authorized; audit changes are not committed.
- [x] Synthetic resources: generator, quality report, migrations, ontology seed
    logic and historical weights exist. This does not certify real-job sourcing,
    official CDACC mappings, model quality or the live scoring feature contract.
- [ ] Automation sign-off: backend CI is configured, but no current remote green
    run was inspected. Frontend CI is absent.

## Evidence From This Audit

- 30 database-independent pytest tests passed.
- Frontend TypeScript/Vite production build passed.
- `docker compose config --quiet` passed (syntax/configuration only).
- `docker compose ps` failed: Docker Desktop Linux engine pipe unavailable.
- Direct request to `http://127.0.0.1:8000/api/health` could not connect.
- Two database integration tests were deliberately not run against an unavailable
    stack. Earlier successful local runs are historical evidence, not current proof.

Sprint 1 is not yet fully signed off. Closure requires the integrated checks below
on disposable/demo data, an inspected green CI run at the reviewed commit, and a
clean-checkout reproduction. No native PostgreSQL configuration was changed.

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