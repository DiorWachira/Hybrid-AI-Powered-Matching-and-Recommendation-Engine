# Hybrid AI-Powered Workforce Placement Engine

JobBridge is an ICS II prototype combining rule-based eligibility, local ML scoring,
and graph-based skill explanations for workforce placement.

**Live demo:** <https://140-238-99-64.sslip.io/> (Oracle Cloud Always Free, deployed
2026-10-26). Scores come from a model trained on synthetic labels and are experimental;
use fictional CVs only.

## Current Increment

Two-step verification (2026-10-22): sign-in supports authenticator-app codes (TOTP,
RFC 6238), which work for every account because no email delivery is involved.
Administrators must enrol on their first sign-in (`MFA_REQUIRED_ROLES`); candidates and
recruiters can opt in under **Security**. Each enrolment issues ten single-use recovery
codes, stored hashed; TOTP secrets are Fernet-encrypted (`MFA_ENCRYPTION_KEY`). Codes
cannot be replayed, and five wrong codes lock the second step for 15 minutes.
Administrators can reset a user's two-step verification from the dashboard; an
administrator who loses their phone is reset on the server with
`python backend/reset_mfa.py <email>`. Migration `20261022_0008` adds the columns.

Sign in with Google (2026-10-22): optional, off until `GOOGLE_CLIENT_ID` is set. The
server verifies Google's signed ID token (signature, audience, issuer, expiry and a
Google-verified email) and accepts it only for existing, active, non-admin accounts listed
in `GOOGLE_SIGNIN_EMAILS`; two-step verification still applies. Everyone else, and every
administrator, signs in with their password. Google does not create accounts.
The OAuth client must list every address the app is opened on as an authorized JavaScript
origin (`http://localhost:5173` and `http://127.0.0.1:5173` locally); Google rejects any other
origin before a sign-in reaches the API.

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
- Authenticator-app two-step verification (required for administrators) with recovery codes
- PostgreSQL/Alembic persistence and Neo4j projection/ontology tooling
- Synthetic data preparation and historical model artifacts
- Rule, data-tool and API-boundary tests plus backend CI configuration

Graph sync (2026-10-26) runs inside the API process: a background thread drains the
PostgreSQL outbox into Neo4j every `GRAPH_SYNC_INTERVAL_SECONDS` (default 5; `0` turns it
off). No scheduled task or extra terminal is involved. The one-shot worker
(`python -m app.db.graph_sync`) still works for backfills. See [docs/WORKFLOW.md](docs/WORKFLOW.md) for
status checks and operational limits. The live model is the 2026-10-19 feature
contract v2 run (related-skill readiness), epoch 4, promoted for prototype testing
(`PROTOTYPE_TESTING_APPROVED`); it replaced the 2026-10-09 v1 epoch-19 model. `data_pipeline/validate_model_contract.py` now
verifies training/serving feature parity against the shared feature module and
exits 0; independent non-synthetic quality evaluation and public deployment are
not done.

## Explicitly Deferred

Not yet signed off:

- Independently measured (non-synthetic) model quality
- Epoch training (2026-10-09 Colab run completed and verified; parity gate now on the shared feature contract)
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

The live demo at <https://140-238-99-64.sslip.io/> runs the production stack in `deploy/`
(Caddy HTTPS, FastAPI, PostgreSQL, Neo4j in one Docker Compose project) on an Oracle
Always Free VM; see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Do not expose the Vite server, database
viewers, default credentials or the repository's seed password publicly.

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
