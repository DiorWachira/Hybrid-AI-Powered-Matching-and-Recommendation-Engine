# Dataset Strategy

Decision recorded 2026-09-20. Supersedes the "dataset decision still open" item
in [ROADMAP.txt](ROADMAP.txt). Source notes: `Dataset_sourcing/global_datasets_recommendations.txt`
and `Dataset_sourcing/kenya_specific_datasets.txt` (local, gitignored).

## Decision: hybrid dataset, not a single source

| Layer | Source | Why |
| --- | --- | --- |
| Candidate CVs | **Synthetic**, from a seeded deterministic generator with a curated skill/certification pool (ESCO + CDACC + common industry certs) | Real resumes carry consent/privacy risk and bias; synthetic data can be produced at 10k-100k scale, is free, and lets us control class balance for the anti-bias pipeline. |
| Job postings | Target source: BrighterMonday Kenya Jobs, supplied as a permitted local JSON export. Current demo data remains synthetic. | Local importer normalizes an export to the internal schema without scraping or requiring a paid API key. Synthetic postings remain the free, repeatable default. |
| Skill ontology | ESCO v1.2.1 (CC BY 4.0) as the intended Neo4j graph backbone; current graph also has a small curated demo seed. | The loader accepts trimmed skills and related-skill CSV inputs. Full official ontology loading depends on obtaining the chosen ESCO export. |
| Local skill alignment | Planned curated CDACC occupational-standard to ESCO mapping, represented by `MAPS_TO` edges. | Current repository entries are provisional working examples; verify against official CDACC material before treating the crosswalk as authoritative. |
| Optional validation | JobSearch-XS, PJB Benchmark | Reserved as an **optional, later** cross-check (Week 7 stretch) for ranking quality — not a core dependency. Non-Kenyan, and PJB's redistribution terms need re-checking before any use. |
| Excluded | Freehire Jobs, Zalize Tech Jobs | Non-Kenyan, no strong reason to prefer over BrighterMonday for this project; Zalize is CC BY-NC which complicates reuse. Skip unless a specific gap appears later. |
| Methodology check only | Kaggle "Profile Matching and Recommendation Dataset" (`users.csv` + `feedback.csv`, MIT) | **Not** job/skill data — generic profile-to-profile matching with demographic/personality/free-text fields. Its `feedback.csv` has real accept/reject labels, which the project's own synthetic data doesn't have on its own. Used only in `notebooks/hybrid_matching_model_training.ipynb` (Section 17) to confirm the train/val/test-split + regularized-logistic-regression training procedure works on independently-labelled data, kept fully separate from the exported production artifact. |

## Rationale

- The project's stated non-functional goal is anti-bias, privacy-respecting matching.
  Scraping and scoring real people's resumes works against that; synthetic candidates
  side-step it entirely while still being statistically realistic.
- Real job postings matter more for realism than real resumes do, because job posts
  are already public, employer-authored, non-personal data.
- ESCO gives a ready-made, licensable graph structure instead of hand-building an
  ontology from scratch, while the CDACC mapping keeps it locally relevant for the
  report's Kenyan-labour-market framing.

## Generator design (updated 2026-09-20)

Two properties were added after the first training run exposed problems:

**In-role specialisations.** Every role carries three specialisations (e.g. Data
Analyst -> financial reporting / marketing analytics / health informatics), each
with its own vocabulary, and job/CV text is rendered from several sentence
templates. The first run produced near-identical text within a role, which left
the embedding model nothing to learn and drove BERT-only ROC-AUC down to 0.605.
The regenerated set yields 800/800 distinct resumes and 99/100 distinct job posts.

**Hidden latent traits.** Candidates carry `latent_competence` and
`latent_adaptability`; jobs carry `latent_quality_bar`. These are *never* exposed
to the model as features. Pair labels are sampled as a Bernoulli outcome from a
probability that depends on both observable signal and these hidden traits plus
Gaussian noise.

This replaced the original weak label
`is_match = (S_graph >= 0.6) AND (years_experience >= required_years)`, which was
circular: `S_graph` is itself a model input, so a two-threshold rule over the
model's own features reproduced that label with 97.5% accuracy. Metrics from that
scheme measured rule reconstruction, not matching quality, and must not be
reported as accuracy. The replacement has a finite Bayes ceiling, so results are
compared against that ceiling rather than against 1.0.

## Where this lands in the pipeline

1. `data_pipeline/generate_synthetic_data.py` (Week 4) produces the synthetic candidate
   population and, if the scraper isn't used, synthetic job postings too.
2. `data_pipeline/import_brightermonday_jobs.py` normalizes a permitted local
   Kenya jobs export (JSON) into the same schema as synthetic postings.
3. `data_pipeline/load_esco_ontology.py` ingests a trimmed ESCO CSV export into
   Neo4j `Skill` nodes and `RELATED_TO` edges.
4. A provisional CDACC-to-ESCO mapping JSON adds `MAPS_TO` relationships; verify
   each entry with the official standards before describing it as authoritative.
5. `data_pipeline/evaluate_model.py` (Week 7) computes precision/recall/F1 against a
   held-out labelled slice of the synthetic set; JobSearch-XS/PJB checks are optional
   additions to that same script, not a prerequisite for it.

## Week 4 Implementation Status (2026-10-01)

- `data_pipeline/import_brightermonday_jobs.py` normalizes a researcher-provided
   local JSON export. It does not scrape the site or require a paid API key.
- `data_pipeline/load_esco_ontology.py` accepts a trimmed skills CSV with
   `preferredLabel` plus an optional normalized related-skill CSV containing
   `source_skill`, `target_skill`, and `weight`.
- `data_pipeline/ontology/curated_skill_relationships.json` supplies a compact
   demo graph when an official ESCO export is not present.
- `data_pipeline/ontology/cdacc_esco_mapping.json` contains provisional example
   mappings. Validate every mapping against the selected official CDACC release
   before presenting it as authoritative.
- `data_pipeline/prepare_week4.py` creates anonymized deployment exports and a
   quality report in the ignored local `data_pipeline/processed/` directory. It
   excludes latent label-generation fields and preserves raw training data.
- The one-command workflow was exercised in file-only mode with a fixed seed:
   12 candidates and 8 jobs exported, with zero duplicate IDs, zero missing
   required fields, non-negative experience, and all 12 resume texts distinct.
- Nine focused Week 4 data and rule-gate regression tests pass.
- Docker-backed database seeding is implemented but could not be re-verified in
   this session because the Docker Desktop engine pipe was unavailable.
- Live Docker database loading could not be rerun in this session because the
   Docker Desktop engine was unavailable.
