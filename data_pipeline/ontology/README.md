# Week 4 Ontology Inputs

`curated_skill_relationships.json` is a small project seed graph used when no
ESCO export is supplied. It contains weighted related-skill links for the
roles currently used in the demo.

It is also the skill graph behind matching feature contract
`serving-related-skill-readiness-v2`: a required skill the candidate does not
list earns the product of the relationship weights along the strongest path of
at most two links from a skill they do list. Scoring reads this file rather than
live Neo4j, so admin edits to the graph never change a trained model's inputs.
A v2 model artifact pins this file's SHA-256, and serving refuses to score with a
v2 model if the file has changed since training. Edit the file, then retrain
and re-promote; do not edit it under a promoted v2 model.

To add a trimmed ESCO export, pass a CSV with a `preferredLabel` column (the
loader also accepts `name` or `label`) and optional `skillType` or `category`:

    python data_pipeline/load_esco_ontology.py --skills-csv path/to/skills_en.csv

Optional relationships can be provided as a normalized CSV with columns
`source_skill`, `target_skill`, and optional `weight`:

    python data_pipeline/load_esco_ontology.py --skills-csv path/to/skills_en.csv --relationships-csv path/to/related_skills.csv

The loader merges skill nodes and weighted `RELATED_TO` relationships into
Neo4j. It retains source labels so curated links and imported ESCO data can be
distinguished.

`cdacc_esco_mapping.json` contains illustrative working mappings for the demo.
They are explicitly marked as pending verification against the relevant official
CDACC occupational-standard release. Do not describe them as officially
validated mappings until that source review is completed. The loader creates
`CDACCStandard` nodes and `MAPS_TO` relationships.

## CDACC and ESCO source review (2026-11-04)

`cdacc_esco_mapping.json` remains provisional. Scoring does not read it.

| Working CDACC name | In CDACC Level 6 guide? | Working ESCO label | Top ESCO skill-search results |
|---|---|---|---|
| Apply Digital Literacy | Listed as "Demonstrate Digital Literacy" | ICT literacy | have computer literacy; teach ESOL literacy class; teach digital literacy |
| Perform Data Analysis | No | data analysis | statistics; use specific data analysis software; perform data analysis |
| Manage Financial Records | No | financial accounting | monitor financial accounts; synthesise financial information; inspect government expenditures |
| Prepare Tax Returns | No | taxation | research taxation procedures; spirit taxation regulations; international taxation of transfer prices |
| Develop Software Applications | No | software development | software frameworks; levels of software testing; manage software releases |
| Manage Projects | No | project management | project management; project commissioning; project management principles |

Sources: [TVET CDACC Learning Guide for Basic Competencies, Level 6](https://www.tvetcdacc.go.ke/wp-content/uploads/2023/07/LEARNING-GUIDE-FOR-BASIC-COMPETENCIES-LEVEL-6.pdf)
(all 401 pages searched for the exact names) and the [ESCO search API](https://ec.europa.eu/esco/api/search)
(top three results only). That guide covers basic units, so "No" does not rule a name out of a
course-specific occupational standard; those standards still need checking.
