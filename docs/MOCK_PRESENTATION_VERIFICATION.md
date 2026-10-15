MOCK-PRESENTATION VERIFICATION LOG (2026-10-14)
================================================
Purpose: initial testing & evaluation evidence for the Sprint II progress review.
Scope: live end-to-end verification of the running stack against the seeded demo
dataset. Every row records Expected -> Actual. No code or model weights changed
during this log; it is observation only.

ENVIRONMENT (as run)
- Docker engine 29.6.1; `docker compose up -d postgres neo4j`.
- PostgreSQL 16 (container workforce-postgres) on host 5433: HEALTHY, migration
  20261002_0007 applied, 9 domain tables present.
- Neo4j 5 (container workforce-neo4j) on 7687/7474: HEALTHY, cypher-shell OK.
- FastAPI (uvicorn) on 127.0.0.1:8000; React/Vite dev server on 127.0.0.1:5173.
- Seeded dataset already present: 100 users, 91 candidates, 8 employers,
  25 jobs, active admin (admin@jobbridge.example.org).

MODEL / PARITY (Serving uses trained epoch-19 head)
1. Health endpoint GET /api/health
   Expected: {"status":"ok","database":{"postgres":"ok","neo4j":"ok"}}
   Actual:   identical. PASS
2. Admin login POST /api/auth/login (email+password)
   Expected: HTTP 200, JWT with role=admin
   Actual:   HTTP 200, role=admin, access_token issued. PASS
3. Model provenance on scored results
   Expected: model_version == 2026-10-09-epoch-combiner-r001 (epoch 19)
   Actual:   every scored candidate and stored match reports that version. PASS
4. Feature-parity gate `python data_pipeline/validate_model_contract.py`
   Expected: exit 0; feature_parity_passed=true; independent_quality_validated=false
   Actual:   exit 0, parity true, independent eval still BLOCKED. PASS

CORE WORKFLOW (input -> processing -> output)
5. List open jobs GET /api/jobs/
   Expected: non-empty list of open postings
   Actual:   25 open jobs returned (e.g. "Senior DevOps Engineer"). PASS
6. Evaluate matches POST /api/matches/evaluate/{job_id}  [THE core task]
   Expected: HTTP 200; every active candidate scored; Tier-1 hard rules gate the
             ML path; Tier-2 semantic/skill/growth -> calibrated final score.
   Actual:   HTTP 200; 91 candidates scored. Eligible top result final=0.868
             (sem=0.47, skill=1.0, growth=1.0). Ineligible candidates correctly
             returned hard_rule_passed=false with final=0. Results persisted
             (match_results grew by 91) and an audit event was written. PASS
   Note:     first-call latency ~89s (cold MiniLM load + 91 encodes); model is
             cached for subsequent calls. The 2-5s inference target remains an
             open performance item (see roadmap).
7. Stored match GET /api/matches/{match_id}
   Expected: persisted scores + provenance, DB column names.
   Actual:   hard=true, final_weighted_score=0.8679, skill_overlap_score=1.0,
             model_version=2026-10-09-epoch-combiner-r001. PASS
8. Neo4j skill-graph explainability GET /api/matches/{match_id}/graph
   Expected: state=current_projection; candidate/job/skill nodes; HAS_SKILL and
             REQUIRES_SKILL edges (+ RELATED_TO where present).
   Actual:   state=current_projection, 8 nodes, 10 edges (6 HAS_SKILL,
             4 REQUIRES_SKILL) in ~4.2s warm. PASS

RESUME INGESTION (FR-02, module-level)
9. DOCX text extraction + skill detection + PII redaction
   Expected: text recovered; domain skills detected; email and phone redacted.
   Actual:   extraction OK; skills=['python','sql','data analysis','docker',
             'kubernetes','aws']; email and 0712345678 both redacted. PASS

ADMIN / OVERSIGHT
10. Admin overview GET /api/admin/overview
    Expected: platform counts + recent activity/audit feed.
    Actual:   users=100, candidates=91, employers=8, jobs=25,
              match_results=389, applications=1, audit trail populated. PASS

AUTOMATED TEST SUITE (regression)
11. `pytest backend/tests --ignore=backend/tests/test_database_health.py`
    Expected: all pass; opt-in real-DB tests skipped without Docker/creds.
    Actual:   115 passed, 5 skipped, 0 failed. PASS
12. Frontend production build `npm run build`
    Expected: `tsc -b && vite build` succeeds.
    Actual:   exit 0; 1614 modules transformed; built in ~27.6s. PASS
13. Frontend dev proxy http://127.0.0.1:5173/api/health
    Expected: Vite proxies /api to FastAPI; health returns ok.
    Actual:   {"status":"ok","database":{"postgres":"ok","neo4j":"ok"}}. PASS

SUMMARY
- Core workflow input->processing->output works against a live seeded dataset
  with the trained epoch-19 model and both databases healthy.
- Corrections made this session: none to product code. (Prior session redirected
  the feature-parity gate to the shared contract; that change is separately
  logged in ROADMAP/WORKFLOW/epoch_training_workflow.)
- Known open items carried to the review: first-call inference latency vs the
  2-5s target; independent non-synthetic quality evaluation; public deployment.
