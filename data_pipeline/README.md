# Data Pipeline Operations

## Local Week 4 preparation

The deterministic synthetic generator preserves its normal raw output directory. The Week 4 workflow generates into a separate ignored work directory, anonymizes resume text, removes training-only latent label variables, validates the exports, writes a quality report, and can seed PostgreSQL and Neo4j:

```powershell
python data_pipeline/prepare_week4.py --candidates 100 --jobs 60 --seed 42 --no-seed
```

Remove `--no-seed` to apply Alembic migrations and load the prepared records
into the local Docker databases. Ensure Docker Desktop is running first. Add
`--skip-graph` only when Neo4j projection is intentionally disabled.

Generated files go to the local-only `data_pipeline/processed/` directory. They are excluded through `.git/info/exclude`, so generated datasets are not committed.

## Optional BrighterMonday export

The importer normalizes a permitted JSON file supplied by the researcher; it does not scrape the site and does not need paid credentials:

```powershell
python data_pipeline/prepare_week4.py --brightermonday-export C:\path\to\permitted_jobs.json
```

Accepted JSON forms are a list of job objects or an object containing a `jobs` or `data` list. Common aliases for title, description, location, experience, skills, certification, salary, company, and source ID are normalized. The output retains company names so imported postings are associated with the correct employer records.

## Canonical deployment candidate fields

- `candidate_id`
- `target_role`
- `specialisation`
- `location`
- `years_experience`
- `education`
- `skills`
- `certifications`
- `expected_salary_kes` (optional)
- `resume_text` (anonymized before export)

The deployment export deliberately excludes `latent_competence` and
`latent_adaptability`, which are training-label variables only.

## Canonical job fields

- `job_id`
- `title`
- `specialisation`
- `location`
- `required_experience_years`
- `required_skills`
- `mandatory_certifications`
- `salary_range_max` (optional)
- `description`
- `company_name` (optional for generated jobs)

The deployment export excludes `latent_quality_bar`. The quality report records
seed, row counts, duplicate IDs, missing required fields, non-negative experience
checks, role counts, and distinct resume-text count.

## Ontology preparation

A small weighted demo graph is stored in `ontology/curated_skill_relationships.json`.
A trimmed ESCO skills CSV may be loaded as follows:

```powershell
python data_pipeline/load_esco_ontology.py --skills-csv C:\path\to\skills_en.csv --relationships-csv C:\path\to\related_skills.csv
```

The skills CSV must contain `preferredLabel` (or `name`/`label`) and may contain
`skillType` or `category`. The optional normalized relationship CSV uses
`source_skill`, `target_skill`, and optional `weight` columns.

`ontology/cdacc_esco_mapping.json` is a working example, not an authoritative
CDACC crosswalk. Confirm each mapping against the official occupational-standard
release before making academic claims about its validity.

## Ground-truth labels

Model evaluation pairs and latent-driven labels are generated in the training
notebook. Latent candidate/job variables are not deployment fields or model
features. Never use the synthetic labels as a substitute for an independent
human-labelled fairness or quality audit.
