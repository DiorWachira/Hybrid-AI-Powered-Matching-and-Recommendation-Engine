# Dataset Strategy

Decision recorded 2026-09-20. Supersedes the "dataset decision still open" item
in [ROADMAP.txt](ROADMAP.txt). Source notes: `Dataset_sourcing/global_datasets_recommendations.txt`
and `Dataset_sourcing/kenya_specific_datasets.txt` (local, gitignored).

## Decision: hybrid dataset, not a single source

| Layer | Source | Why |
| --- | --- | --- |
| Candidate CVs | **Synthetic**, generated with `Faker('en_KE')` + a curated skill/certification pool (ESCO + CDACC + common industry certs) | Real resumes carry consent/privacy risk and bias; synthetic data can be produced at 10k-100k scale, is free, and lets us control class balance for the anti-bias pipeline. |
| Job postings | **Real, scraped**: BrighterMonday Kenya Jobs (Apify), Kenya-filtered, small paid runs (~500-800 jobs) | Gives authentic KES salary bands, Kenyan locations and natural job-description text for BERT embeddings, at low cost (~$0.001/job). Synthetic job postings (same generator style) are the fallback if the scraper budget/access is unavailable. |
| Skill ontology | **ESCO v1.2.1** (CC BY 4.0) as the Neo4j skill graph backbone | Free, structured, 13k+ skills with `broader_skill` / `narrower_skill` / `related_skill` already modelled — ingest almost directly into the `RELATED_TO` edges. |
| Local skill alignment | A **curated subset** of TVET CDACC occupational standards mapped onto ESCO skills via a `MAPS_TO`-style edge | Keeps certifications and hard-filter criteria meaningful for the Kenyan market (e.g. CDACC "Apply Digital Literacy" -> ESCO "ICT literacy"), without ingesting all 50+ CDACC PDFs. |
| Optional validation | JobSearch-XS, PJB Benchmark | Reserved as an **optional, later** cross-check (Week 7 stretch) for ranking quality — not a core dependency. Non-Kenyan, and PJB's redistribution terms need re-checking before any use. |
| Excluded | Freehire Jobs, Zalize Tech Jobs | Non-Kenyan, no strong reason to prefer over BrighterMonday for this project; Zalize is CC BY-NC which complicates reuse. Skip unless a specific gap appears later. |

## Rationale

- The project's stated non-functional goal is anti-bias, privacy-respecting matching.
  Scraping and scoring real people's resumes works against that; synthetic candidates
  side-step it entirely while still being statistically realistic.
- Real job postings matter more for realism than real resumes do, because job posts
  are already public, employer-authored, non-personal data.
- ESCO gives a ready-made, licensable graph structure instead of hand-building an
  ontology from scratch, while the CDACC mapping keeps it locally relevant for the
  report's Kenyan-labour-market framing.

## Where this lands in the pipeline

1. `data_pipeline/generate_synthetic_data.py` (Week 4) produces the synthetic candidate
   population and, if the scraper isn't used, synthetic job postings too.
2. A small `data_pipeline/import_brightermonday_jobs.py` (optional, Week 4) loads a
   scraped Kenya jobs export (JSON) into the same schema as the synthetic job postings,
   so both can be scored identically.
3. `data_pipeline/load_esco_ontology.py` (Week 1/4) ingests a trimmed ESCO CSV export
   into Neo4j `Skill` nodes and `RELATED_TO` edges, extending the Week 1 seed script.
4. A small hand-authored CDACC-to-ESCO mapping table (JSON, <100 rows) adds
   `MAPS_TO` edges for the certification families used in the demo (software,
   data, accounting — matching the existing Neo4j seed).
5. `data_pipeline/evaluate_model.py` (Week 7) computes precision/recall/F1 against a
   held-out labelled slice of the synthetic set; JobSearch-XS/PJB checks are optional
   additions to that same script, not a prerequisite for it.
