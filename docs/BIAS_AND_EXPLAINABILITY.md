# Bias controls and explainable matching

**Last updated:** 2026-11-08. This describes the code on the `feat/decision-transparency` branch and the live model `2026-10-19-epoch-combiner-v2-r001` (threshold 0.46).

After a recruiter runs an evaluation, the match analysis page explains every result in two places:

- **Fairness check for this evaluation**, above the ranking: the same rules, model and threshold for everyone, how many candidates each rule removed, and what the model is never given.
- **How this decision was reached**, under each candidate's breakdown: the four steps that produced the result, with the bias risk at each step and what the system does about it.

The wording lives in one file, `frontend/src/lib/decisionGuide.ts`, so the page and this document say the same thing. If the code below changes, that file and this document must change with it.

## Contents

1. [The four steps of a decision](#1-the-four-steps-of-a-decision)
2. [Bias in each eligibility rule](#2-bias-in-each-eligibility-rule)
3. [Bias in each model input](#3-bias-in-each-model-input)
4. [Bias in the trained model](#4-bias-in-the-trained-model)
5. [Bias in each outcome scenario](#5-bias-in-each-outcome-scenario)
6. [What the model is never given](#6-what-the-model-is-never-given)
7. [Controls on the recruiter's decision](#7-controls-on-the-recruiters-decision)
8. [What has not been shown](#8-what-has-not-been-shown)

---

## 1. The four steps of a decision

| Step | What happens | Code |
|---|---|---|
| **01 Eligibility rules** | Each candidate is checked against the hard rules on the posting. A failure stops here, with a score of 0 and the exact reason. | `backend/app/core/rule_filter.py` |
| **02 What the model read** | Three numbers between 0 and 1: semantic similarity, related-skill overlap and experience readiness. | `backend/app/core/match_features.py`, `hybrid_matcher.py` |
| **03 Combining the scores** | Each number is compared with the average training candidate, weighted, and added to a starting point. The total becomes a match score. At or above the threshold means "Recommended". | `calibrated_score_for` in `hybrid_matcher.py` |
| **04 The recruiter's decision** | The system recommends; the recruiter decides. Moving forward someone it did not recommend shows a warning and is recorded. | `backend/app/core/overrides.py` |

Step 03 is shown as arithmetic on the page, for example: *starting point 1.46 +0.48 +0.04 +0.63 = 2.61, a match score of 93%; the threshold is 46%, so this is recommended*. Each input's push is `weight × (value − training average) ÷ training spread`, which is exactly what the served model computes. A recruiter can see which input raised or lowered the score.

The posting's rules are saved with each evaluation (`requirements` in the `matches.evaluated` audit event), so editing the posting later cannot rewrite what an earlier evaluation checked.

---

## 2. Bias in each eligibility rule

The rules remove people before any score exists, so they are the most direct source of exclusion. The fairness panel shows how many candidates each rule removed and highlights the largest, so a recruiter can see when a rule is doing most of the filtering.

| Rule | Bias risk | How it is avoided |
|---|---|---|
| **Right to work** | Can exclude refugees and foreign nationals who are in fact allowed to work, and anyone who left the question unanswered. | Applied only when the recruiter marks it required. It reads the candidate's own yes or no, never nationality, country of birth or ID type. A failure means "not confirmed", not "not allowed". |
| **Minimum experience** | Years of experience follow age, so a high minimum screens out younger people and those with career breaks, who are often carers. | Only the posted minimum is used. Age and date of birth are never read. Above the minimum, experience earns credit only up to 1.5 times the requirement, so a long career cannot outrank someone who meets the bar on years alone. |
| **Location** | Where someone lives can stand in for region, ethnic community or income, and can exclude capable people from other counties. | Applied only when both sides give a location, as a plain same-or-different check with no ranking of places. Major Kenyan town names are removed from CV text before the language model reads it, so location does not move an eligible candidate's score. Remote roles should leave location blank. |
| **Salary ceiling** | Screens on one figure the candidate typed, which may be out of date or negotiable. | Compared only with the posted maximum. Salary is never part of the match score, so asking for less does not rank anyone higher. |
| **Mandatory certifications** | Excludes people with equal skill but no certificate, such as the self-taught or those who could not afford exam fees. | Only certifications the recruiter marks mandatory count. Optional certifications add nothing to the score, so paid credentials cannot buy a higher ranking. |

---

## 3. Bias in each model input

| Input | Bias risk | How it is avoided |
|---|---|---|
| **Semantic similarity** | The pretrained language model (`all-MiniLM-L6-v2`) learnt from general English web text. It can favour polished English and familiar phrasing, and may carry stereotypes from that text. | Names, emails, phone numbers, links, gender words, ages, dates of birth and major Kenyan town names are removed first (`text_preprocessing.py`). It is one of three inputs; the other two come from structured skills and years. |
| **Related-skill overlap** | Exact skill names favour people who know the industry's jargon or trained where a skill has another name. | Related skills earn partial credit through a curated graph, so PostgreSQL counts towards SQL. The graph is a versioned file pinned to the model by its hash, so nobody can quietly re-weight skills for one evaluation. |
| **Experience readiness** | More years usually means older, so experience can favour age over ability. | Capped at 1.5 times the requirement. Years beyond that add nothing. |

---

## 4. Bias in the trained model

**Risk.** A model trained on past hiring decisions can learn the bias in them.

**How it is avoided.** This model has no past hiring decisions to learn from: it was trained on synthetic labels, and it sees only the three numbers above, never who the person is. Everyone is scored with the same weights and the same threshold. Equal scores are ordered by the candidate's random ID, never by name or sign-up order (tested in `test_evaluation_uses_candidate_id_to_break_score_ties`).

**The other side.** Synthetic training means the model has not been checked against real hiring outcomes.

---

## 5. Bias in each outcome scenario

Every candidate falls into one of four scenarios. The page names the scenario and gives these four points.

| Scenario | How the decision was reached | Bias to watch | How it was avoided | What the recruiter should do |
|---|---|---|---|---|
| **Recommended** | Passed every rule, and the score is at or above the threshold. | Automation bias: trusting the label too much. In synthetic tests the model accepted 95-99% of good matches but turned away only 31-42% of weak ones, so "Recommended" is a broad pass, not proof of fit. | The score uses only skills, experience and anonymised CV text. The breakdown shows which inputs raised it. | Check the missing skills, then let the interview decide. |
| **Eligible, below the threshold** | Passed every rule, but the score is below the threshold. | A capable candidate can score low because they write differently or name skills differently. | Related skills earn partial credit; the language model is not shown names, gender words, ages or major town names; the threshold is the same for everyone. | Check which input pulled the score down. If it is semantic similarity, read the CV. They can still be moved forward, with a warning, and the move is recorded. |
| **Requirements not met** | Failed one or more of the posting's rules, so no score was calculated. | The rule, not the model, decided. A rule stricter than the job needs excludes people unfairly, and a profile can be out of date. | No score was calculated, so the model's possible biases played no part. The rules are the recruiter's own, applied the same way to everyone. | If a rule is not a real need, edit the posting and evaluate again rather than overriding people one by one. Moving one person forward needs a written reason. |
| **Scored by an earlier model** | The result came from a model that is no longer served. | Comparing scores from two models is unfair to one of them. | The page withholds the recommendation and asks for a new evaluation. | Evaluate again so everyone is scored by the same model. |

---

## 6. What the model is never given

- Name, email, phone number and links, removed from the CV text before scoring.
- Gender words, age and date of birth, removed from the CV text before scoring.
- Major Kenyan town names, removed from the CV text; location is only an eligibility rule.
- Photos: only the CV's text is read, and the uploaded file is not kept.
- Nationality, ethnicity, religion, marital status and disability: the platform never asks for them.
- Salary, application date and sign-up order.

**Removal is best effort.** It uses patterns, not understanding. Pronouns, school names, clubs or a town missing from the list can still hint at who someone is. Redaction does not prove anonymity.

---

## 7. Controls on the recruiter's decision

The system recommends; the recruiter decides. These controls keep that decision visible and accountable without taking it away.

- **Blind review.** A switch on the match analysis page replaces names with a stable code (for example `Candidate 3F9A1C`) and hides locations, in the ranking, the breakdown and the hiring flow. The setting is remembered in that browser.
- **Override warning.** Moving forward anyone the evaluation did not recommend opens a warning listing who and why, on the hiring flow and on the roles-page applicant list. The applicant list now shows each applicant's score and rule result.
- **Required reason for a failed rule.** Moving forward someone who failed an eligibility rule needs a reason of at least 10 characters. The server enforces this (`advance_applications` in `hiring.py`, `update_application` in `jobs.py`), so it cannot be skipped through the API. A low score alone needs no reason, so the box is not clicked through without thought.
- **Record and review.** Every forward move saves the score, threshold, rule result and any reason in the audit event. Overrides are tagged `below_threshold` or `hard_rule`. The admin dashboard counts them, and the activity log has an "Overrides" filter.
- **Never blocked.** The model is tested only on synthetic data and a failed rule can rest on an out-of-date profile, so the system warns and records rather than refusing.

---

## 8. What has not been shown

- **Fairness across groups has not been measured.** The platform does not collect group data such as gender or ethnicity, so selection rates cannot be compared between groups. Doing so would need a separate, consented audit set. Protected attributes must not be added to the ranking.
- **Results by role are not a fairness audit.** They compare job types, not people.
- **No real outcomes.** The model is tested only on synthetic data. The 150-pair gold slice, once labelled, is the first independent check of match quality, though not of fairness.
- **Location stays a hard rule** because it is part of the job contract. A future study should compare results with and without location filtering.
