# Bias Controls and Explainable Matching

The matching pipeline uses three separate stages.

## 1. Rule-based eligibility

The Tier 1 rule gate checks only job-related requirements:

- Minimum experience
- Job location, when the employer requires one
- Salary ceiling
- Mandatory certifications

A candidate who fails a hard requirement is reported with the exact reason. The candidate does not receive hidden model or graph advantages for failing that requirement.

## 2. Trained machine-learning score

Only observable, job-related features are sent to the trained scorer:

- MiniLM semantic similarity between resume text and job description
- Structured skill overlap
- Experience and certification growth score

The production API loads the saved scaler values, logistic-regression coefficients, and decision threshold from `data_pipeline/artifacts/hybrid_match_weights.json`. Names, phone numbers, account emails, and other identity fields are not scoring features.

The data-generation process also keeps hidden competence, adaptability, and job-quality variables out of the model features. They are used only when creating evaluation labels, preventing the model from learning a circular target.

## 3. Knowledge-graph explanation

Neo4j stores candidate skills, job-required skills, certifications, and related-skill paths. Direct and weighted two-hop `RELATED_TO` paths can be explored visually in Neo4j Browser and used to explain skill relationships. The graph visualization is kept separate from the trained model decision so it does not silently change the trained feature definition.

This design improves transparency: a recruiter can see which hard rule failed, which skills matched, how the semantic score contributed, and which graph relationships explain transferable skills.

## Remaining limitation

Location is retained as a hard job requirement because it is part of the current job contract. A future fairness study should compare results with and without location filtering and add an independently labelled, protected-attribute audit set. Protected attributes should not be added to ranking features.
