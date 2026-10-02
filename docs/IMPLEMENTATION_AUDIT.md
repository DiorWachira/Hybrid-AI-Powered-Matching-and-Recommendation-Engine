# Implementation Audit

Historical audit below. The 2026-10-02 follow-up implements password recovery,
ontology editing, local graph scheduling and targeted security guards; dependency
updates pass regression checks. See [WORKFLOW.md](WORKFLOW.md) for current evidence.
Model-contract validation now explicitly fails; public deployment remains blocked.

Date: 2026-10-01. Scope: roadmap, workflow increments, Sprint 1, current API
boundaries, training evidence and public-demo readiness. This is not a penetration
test, a new model evaluation or a completed deployment.

## Decision

Sprint 1 source preparation is substantially implemented, but its integrated
runtime exit criterion is not currently signed off. Weeks 2-6 contain working
implementation surfaces, not completed end-to-end increments. Weeks 7-8 remain
partial/pending. Public deployment and real Colab epoch training are not done.

Previous claims of complete CRUD, Colab execution, training/serving parity and
comprehensive anonymization were too strong and have been corrected in the
[roadmap](ROADMAP.txt) and [workflow](WORKFLOW.md).

## Findings

| Priority | Finding and source | Resolution / remaining gate |
| --- | --- | --- |
| High | Match evaluation checked role but not job ownership in [matches.py](../backend/app/api/matches.py) | Fixed before candidate reads/writes; owner/admin permitted, other employer denied; UUID validation added |
| High | Known default JWT secret and cwd-dependent dotenv in [config.py](../backend/app/config.py) | Root dotenv path fixed; staging/production rejects default/short secret and non-HTTPS origins. This does not establish secure DB credentials, dependency safety or complete authentication hardening |
| High | API direct skill intersection and 50/50 growth formula differ from historical notebook weighted skill links and 70/30 growth | BLOCKS live model-quality claims. Define/version shared features, then retrain only with approval; keep graph explanatory |
| High | [jobs.py](../backend/app/api/jobs.py) commits a job before graph projection; upload writes graph before PostgreSQL commit | Dual-write inconsistency remains; need retryable projection with explicit status and failure-injection tests |
| High | No verified public host/TLS/abuse controls; development DB/viewer ports previously bound all interfaces | Compose ports now loopback. Public release still blocked; review upload limits, throttling, secret rotation and synthetic-only data policy |
| Medium | Candidate For You included hard-rule failures; open-job endpoint did not filter status | Both fixed with focused tests. No threshold guarantee; scores still have feature-contract limitations |
| Medium | [session.ts](../frontend/src/lib/session.ts) decodes role without expiry/allow-list validation; job context survives sign-out | Browser session UX/state isolation remains open; backend authorization remains authority |
| Medium | Candidate activity timestamps/transitions/concurrent inserts and match delete/reinsert evaluation can race | Need DB integration/concurrency tests and explicit state/persistence semantics; frontend evaluation POST on mount may repeat |
| Medium | Resume extraction has size/extension guards, not comprehensive parser resource/signature checks | Need malformed PDF/DOCX, archive expansion, timeout and real storage tests; do not accept real public CVs yet |
| Medium | Graph MERGE is case-sensitive and append-only; jobs projected by title, not unique job | Normalize identities, remove stale edges, separate postings; test repeated updates and missing required nodes |
| Medium | Synthetic labels and row-wise inner CV are not independent matching evidence | Group-aware CV and cold/validation isolation, independent gold slice, provenance review required |
| Medium | Epoch artifact helper uses fake checkpoint bytes in tests and local directory mirroring | Not an epoch trainer or Drive durability proof. Restore can replace local folder before full validation; validate/verify before mutation and test interrupted recovery |
| Medium | Per-pair embeddings repeat during dashboard/evaluation requests | No measured 2-5 second latency or memory envelope; benchmark/batch/cache after feature contract is fixed |

## Milestone Evidence

| Stage | Established | Still required for completion |
| --- | --- | --- |
| Week 1 / Sprint 1 | Structure, manifests, migrations, Compose, CI source; local tests/build/config pass | Running DBs, applied migration head, repeated seed, proxy health, clean checkout and inspected green CI commit |
| Week 2 | bcrypt/JWT/roles/admin overview/bootstrap source, request schemas and rules | Full auth lifecycle/expiry/abuse tests, actual admin bootstrap, real recruiter-to-job flow; overview is read-only, not moderation |
| Week 3 | Routed UI and typed HTTP client; profile/upload/activity/evaluation handlers | Current real CV-to-PostgreSQL-to-graph flow, state/concurrency fixes, full accessibility/E2E checks; no claim of complete upload hardening |
| Week 4 | Seeded synthetic generation, normalization, trimmed ontology CSV loader, regex redaction and clean export tests | Permitted real jobs, official CDACC mappings, full ESCO ingestion as needed, live repeatable seed and privacy evaluation |
| Week 5 | Historical local notebook metrics and coefficient export; JSONB schema decision | Actual Colab run and reproducibility. JSONB columns do not prove embedding caching is implemented |
| Week 6 | Lazy MiniLM and artifact loading, rules-first path, result persistence code, graph queries | Feature parity, DB failure handling, cached GET and graph app visualization; component score is not validated confidence |
| Week 7 | Redesigned UI build, selected browser fixtures, rules/data/API tests | Full live functional suite, matched/missing skill response/UI, security, latency, independent evaluation and simulation command |
| Week 8 | Cleanup/deployment checklist documented | Clean-machine demo, release, backup/restore and public acceptance checks; no release tag or deployment yet |
| Epoch increment | Two local artifact-store tests in the passing suite | Real trainer, validation each epoch without early stopping, optimizer/RNG state, Drive sync/resume, locked tests and reviewed promotion |

## Training Contract Evidence

Historical artifact feature order: `S_bert`, `S_graph`, `S_growth`.

- Notebook `graph_overlap_score` credits related skills; API divides direct
  casefolded intersection by the number of required skills.
- Notebook growth: `0.7 * (min(years / max(required, 1), 1.5) / 1.5)` plus
  `0.3 * min(cert_count / 3, 1)`.
- API growth: `(min(years / max(required, 1), 1) + min(cert_count / 2, 1)) / 2`.
- Preprocessing and sentence-transformer versions also differ. Loading the same
  coefficient JSON is not feature parity. Do not silently switch graph ranking
  back on or change historical weights to make a test pass.
- Warm F1 0.774 / AUC 0.834 and cold F1 0.779 / AUC 0.799 are historical synthetic
  notebook reports, not certified public-service metrics. Cold top-k is degenerate;
  cold candidates exclude train but may overlap validation; inner CV is row-wise.
- Latest saved runtime probe reports `is_colab=False`, `drive_mounted=False`.
  No training or artifact promotion was performed in this audit.

## Checks Performed

```powershell
& .\venv\Scripts\python.exe -m pytest backend/tests --ignore=backend/tests/test_database_health.py -q --tb=short --disable-warnings
npm --prefix frontend run build
docker compose config --quiet
```

Results: **30 passed**, frontend build passed, Compose configuration passed.
The tests emit dependency deprecation warnings. API boundary tests override DB
and current-user dependencies: they prove route/authorization logic, not real JWT
validation or PostgreSQL persistence. The open-list test checks SQL expression
construction, not live query execution. Scoring is mocked in feed tests.

`docker compose ps` failed because the Docker Desktop Linux engine pipe was absent.
Direct HTTP health on port 8000 could not connect. The two tests in
[test_database_health.py](../backend/tests/test_database_health.py) were not run.
No current remote Actions run, clean checkout, cloud deployment, Linux/ARM install,
real Drive synchronization or real-backend browser workflow was verified.

Selected earlier UI tests used browser-only fixtures and a test token; they are
not data persistence evidence. The fixture page is no longer available and the
remaining auth page had no matching test token at cleanup. The frontend redesign
remains uncommitted with final UI acceptance pending.

## Next Increment

1. Restore Docker/Neo4j availability and complete Sprint 1's repeatable checks;
   handle native PostgreSQL separately when the user is ready.
2. Close graph/persistence and auth/upload abuse issues; use synthetic-only demo
   records and independently generated account credentials.
3. Version and test shared training/serving features before any retraining.
4. After training approval, implement fixed epochs and isolated validation/test
   selection with verified checkpoint recovery, not merely fake artifact files.
5. Provision only approved Always Free resources, then execute the
   [public-demo acceptance checklist](DEPLOYMENT.md). Do not call the app live
   until it passes from an external browser and after a restart.

No commits, branch changes, pushes, cloud provisioning or native PostgreSQL
changes were made during this audit. Existing notebook and ignore-file edits
were preserved; Chapter 5 notes remain local-only.