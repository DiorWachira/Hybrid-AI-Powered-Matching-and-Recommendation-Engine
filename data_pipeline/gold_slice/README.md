# Gold slice: hand-labelled candidate-job pairs

An independent check of the matching model against human judgement. Created by
`python -m data_pipeline.gold_slice export --pairs 150`; scored by `... evaluate`.

## How to label

1. Copy `labelling_sheet.csv` (or open it in Excel and save as CSV UTF-8). Do **not** open
   `answer_key.json` until you are done: it records which model-score band each pair came from.
2. For each row, read the job, then the candidate, and fill `label`:
   - `1` = you would shortlist this candidate for an interview for this job.
   - `0` = you would not.
   - leave blank to skip a pair you cannot judge (blanks are excluded, not counted as 0).
3. Judge skills, depth of experience and specialisation fit. Ignore location and salary: the
   model score is computed before those hard rules, so they are not what is being measured.
   Treat a related tool as partial evidence (e.g. PostgreSQL for SQL); use `notes` for edge cases.
4. Label in one or two sittings so your standard does not drift. A second labeller should fill a
   separate copy without seeing the first; agreement (Cohen's kappa) shows how reliable the labels are.

## Score the models

    python -m data_pipeline.gold_slice evaluate --labels data_pipeline/gold_slice/gold-seed20261015-150pairs/labelling_sheet.csv --artifact <candidate artifact_candidate.json> [--second-labels <copy.csv>] [--output report.json]

The active model is always included. At least 20 labelled pairs are required. The answer key freezes each
pair's scoring inputs (semantic score, skills, experience) and synthetic label, so evaluation needs neither the
encoder nor the generator, and labels stay valid if the synthetic generator changes later. A model must use
the encoder revision recorded in the key.

## Limits

The profiles and jobs are synthetic (seed 20261015, held-out test pairs only, never trained on); only the
labels are human. This measures agreement with a person's judgement, not hiring outcomes. Accountant
pairs are excluded because the platform covers IT roles only.
