# Sprint 1: Data Preparation and Development Environment

Status: Prepared for demonstration.

## Requirements checklist

- [x] Development environment: Python virtual environment, Node.js frontend,
  Docker Compose, PostgreSQL, and Neo4j configuration are present.
- [x] Codebase organisation: backend, frontend, data pipeline, notebooks, tests,
  documentation, and CI configuration are separated into clear directories.
- [x] Git version control: the project is maintained in Git with feature branches,
  conventional commits, and a GitHub Actions workflow.
- [x] Data and resources: the synthetic data generator, dataset-quality report,
  model weights, evaluation reports, database migrations, and Neo4j seed logic
  are prepared.
- [x] Automation: GitHub Actions runs dependency installation, Python compilation,
  Docker Compose validation, database migrations, and backend tests.

## Local verification

Run these commands from the repository root in PowerShell:

```powershell
docker compose up -d
& .\venv\Scripts\python.exe -m compileall backend
Set-Location backend
& ..\venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run build
```

Docker Desktop must be running before the first command. The frontend build and
Python compilation can run without the database containers.