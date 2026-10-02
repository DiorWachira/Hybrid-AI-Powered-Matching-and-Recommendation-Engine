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

The current API supplies these numeric features to the saved calibration:

- MiniLM semantic similarity between resume text and job description
- Structured skill overlap
- Experience and certification growth score

The API loads saved scaler values, coefficients and threshold from
[hybrid_match_weights.json](../data_pipeline/artifacts/hybrid_match_weights.json).
However, its skill and growth definitions differ from the historical notebook.
Training/serving parity is an open blocker, not an established property.

Structured names/emails are not explicit numeric features, but free-text resumes
can still contain identities and proxies that affect embeddings. Regex redaction
is best effort and does not establish anonymity, job relevance or fairness.

Synthetic hidden latents are excluded from the model inputs. Labels still depend
partly on observable signals related to model features; hidden latents and noise
reduce simple circularity but do not create independent real-world ground truth.

## 3. Knowledge-graph explanation

Neo4j projection/query code stores candidate skills, job requirements and related
paths. Neo4j Browser can be used for exploration when the database is running.
There is no completed in-app graph visualization. The desired architecture keeps
the graph explanatory, but the older training feature did use related-skill
weights; a versioned shared feature contract and reviewed retraining are needed.

The UI shows score components and failed-rule reasons. Matched/missing skill
breakdowns are stored but are not fully delivered/rendered in the current results
workflow. Neither a component score nor a graph path is a validated causal
explanation of hiring suitability.

## Remaining limitation

Location is retained as a hard job requirement because it is part of the current job contract. A future fairness study should compare results with and without location filtering and add an independently labelled, protected-attribute audit set. Protected attributes should not be added to ranking features.
