# Explanations

A plain-language guide to how the JobBridge matching model was built, trained and evaluated, what the results mean, and how the recruiter hiring flow treats match scores.

**Last updated:** 2026-11-05
**Model described:** `2026-10-19-epoch-combiner-v2-r001`, epoch 4, decision threshold 0.46. This is the model the live site serves.
**Figures:** every figure number refers to `notebooks/model_visuals.ipynb`. The images are in `notebooks/figures/`.

## Contents

1. [The short version](#1-the-short-version)
2. [How matching works](#2-how-matching-works)
3. [The dataset](#3-the-dataset)
4. [How the model was trained](#4-how-the-model-was-trained)
5. [What the training results show](#5-what-the-training-results-show)
6. [What each metric means](#6-what-each-metric-means)
7. [What the evaluation results show](#7-what-the-evaluation-results-show)
8. [Random forest and gradient boosting](#8-random-forest-and-gradient-boosting)
9. [Understanding ROC-AUC](#9-understanding-roc-auc)
10. [Warm test and cold test](#10-warm-test-and-cold-test)
11. [Why the cold test scored higher than the warm test](#11-why-the-cold-test-scored-higher-than-the-warm-test)
12. [Can a recruiter choose a low-scoring candidate?](#12-can-a-recruiter-choose-a-low-scoring-candidate)
13. [Ranking speed on the live server](#13-ranking-speed-on-the-live-server)
14. [What you can and cannot claim](#14-what-you-can-and-cannot-claim)
15. [Questions an examiner may ask](#15-questions-an-examiner-may-ask)
16. [Figures and how to reproduce them](#16-figures-and-how-to-reproduce-them)

---

## 1. The short version

The trained model is a **logistic regression, fitted with stochastic gradient descent (SGD)**. It combines three match scores into one probability that a candidate suits a job.

- **It ranks well above chance.** ROC-AUC is 0.807 on the warm test and 0.847 on the cold test.
- **It clearly beats semantic similarity alone,** but it is not shown to beat the hand-set fixed weights.
- **Random forest and gradient boosting rank slightly better,** with the same F1. Logistic regression was kept because it is small and explainable, not because it was the most accurate.
- **Its yes/no decision is lenient.** It accepts 95-99% of good matches, but rejects only 31-42% of poor ones.
- **Everything is measured on synthetic data.** The results show the method works as designed, not that it predicts real hiring outcomes. The 150 gold-slice pairs, which would give the first independent check, are not yet labelled.

---

## 2. How matching works

Matching has three stages.

### Stage 1: hard rules

These run first. A candidate who fails any of them gets a score of 0 and is marked as not eligible (`backend/app/core/rule_filter.py`).

| Rule | Fails when |
|---|---|
| Work authorisation | The job requires it and the candidate has not confirmed it |
| Experience | The candidate has fewer years than the job requires |
| Location | Both locations are set and they differ |
| Salary | The candidate expects more than the job's maximum |
| Certifications | A mandatory certification is missing |

### Stage 2: three scores

Each remaining candidate is measured against the job. Each score is between 0 and 1.

| Input | Name in the code | What it measures |
|---|---|---|
| Semantic similarity | `S_bert` | How similar the CV and job description are in meaning, using the pretrained `all-MiniLM-L6-v2` sentence encoder. The encoder was not retrained |
| Related-skill overlap | `S_graph` | How many required skills the candidate has. An exact match earns full credit. A related skill earns partial credit, found through at most two relationships in the skill graph, with the weights along the path multiplied together |
| Experience readiness | `S_growth` | The candidate's years divided by the years required, capped at 1.5 times the requirement, then scaled so the cap equals 1 |

### Stage 3: the trained combiner

A logistic regression turns the three scores into one probability. This is the only part that was trained. It has four learned values: three weights and an intercept.

1. Each score is standardised using the training data's average and spread.
2. The standardised scores are multiplied by their weights and added to the intercept. This total is the *logit*.
3. The logit is converted into a probability between 0 and 1.

| Value | Semantic similarity | Related-skill overlap | Experience readiness |
|---|---|---|---|
| Weight | 0.708 | 0.682 | 0.942 |
| Training average | 0.622 | 0.893 | 0.784 |
| Training spread | 0.114 | 0.122 | 0.325 |

The intercept is 1.463.

**Worked example.** Take a candidate with semantic similarity 0.70, skill overlap 0.90 and experience readiness 1.00:

- Standardised scores: (0.70 - 0.622) / 0.114 = 0.69, (0.90 - 0.893) / 0.122 = 0.06, and (1.00 - 0.784) / 0.325 = 0.67.
- Logit: 1.463 + (0.708 x 0.69) + (0.682 x 0.06) + (0.942 x 0.67) = about 2.62.
- Probability: 1 / (1 + e^-2.62) = about **0.93**, or a match score of 93%.

The score is at or above the 0.46 threshold, so the candidate is marked as recommended.

**Why "hybrid"?** The system combines rules, a language model and a skill graph, and a trained model weighs the results.

---

## 3. The dataset

No real CVs or hiring outcomes were used. The data comes from a seeded synthetic generator, so it can be recreated exactly.

### Size and roles (Figure 1)

800 candidates and 100 jobs, across five roles:

| Role | Candidates | Jobs |
|---|---|---|
| DevOps Engineer | 186 | 17 |
| Data Analyst | 166 | 23 |
| Business Analyst | 153 | 16 |
| Software Engineer | 152 | 26 |
| Accountant | 143 | 18 |

**The Accountant role is not IT.** The project keeps jobs to IT roles, and the generator was fixed to replace it after this training run. The served model was still trained on it. It uses only three role-neutral scores, so this adds no role-specific logic, but the training population is not IT-only. Removing it needs a new training run.

### Pairs and labels

Each candidate is paired with up to 5 jobs in the same role, which gives **3,883 candidate-job pairs**. Each pair gets a label: 1 for a good match and 0 for a poor match.

A label is drawn at random from a probability calculated from:

```
logit = 6.0 x (true skill credit - 0.75)
      + 3.8 x (experience - 0.5)
      + 3.6 x (same specialisation - 1/3)
      + 1.6 x (candidate's hidden competence - job's hidden quality bar)
      + 0.4 x (candidate's hidden adaptability - 0.5)
      + random noise
```

Three things follow from this:

- **Perfect accuracy is impossible.** Hidden traits, specialisation and randomness all affect the label, and the model sees none of them directly.
- **The labels resemble the inputs.** Skills and experience drive the labels, and the inputs measure something close to them. Good results therefore partly reflect the design of the data.
- **v3 labels depend on an assumption.** These labels follow a candidate's *true* skills, while their *listed* skills sometimes use another name (alias rate 0.35). This reflects people describing the same skill differently, and related-skill overlap was designed to catch exactly this.

### Class balance (Figure 2)

**73% of pairs are labelled good matches.** This is the most important fact about the data. A model that always says yes would already reach about 72% accuracy and 0.83 to 0.84 F1 on the test sets, so those are the numbers to beat.

### Splits (Figure 2)

| Split | Candidates | Pairs | Good matches | Used for |
|---|---|---|---|---|
| Train | 477 | 2,385 | 73% | Fitting the model |
| Validation | 160 | 800 | 75% | Choosing the epoch and threshold |
| Warm test | 80 | 400 | 72% | Final test: new candidates, known jobs |
| Cold test | 83 | 298 | 71% | Final test: new candidates, new jobs |

Two safeguards stop information leaking between splits:

- **Candidates are split, not pairs,** so nobody appears in two splits. The split is 60/20/10/10 within each role.
- **20% of each role's jobs are held back** for the cold test only (18 jobs).

### Profiles and inputs (Figures 3 to 5)

- **Experience:** candidates have 0 to 15 years (mean 7.7), and jobs ask for 0 to 8 (mean 4.0). Candidates often exceed the requirement, so experience readiness has a large spike at 1.0.
- **Education and location:** close to uniform, as a generator would produce. They say nothing about the real Kenyan labour market.
- **Skills:** SQL leads demand (47% of jobs, 29% of candidates). Git has the largest proportional gap (20% of jobs, 9% of candidates).
- **Inputs by label:** good matches score higher on all three, and the inputs are almost unrelated to each other (correlations within 0.05 of zero).

| Average input (training split) | Good match | Poor match |
|---|---|---|
| Semantic similarity | 0.641 | 0.567 |
| Related-skill overlap | 0.914 | 0.834 |
| Experience readiness | 0.854 | 0.593 |

---

## 4. How the model was trained

| Setting | Value |
|---|---|
| Algorithm | `SGDClassifier` with log loss, which is logistic regression fitted by SGD |
| Learning rate | 0.01, constant |
| Regularisation | L2, alpha 0.0003 |
| Batch size | 256, reshuffled each epoch |
| Epochs | 100, fixed, with no early stopping |
| Random seed | 42 |
| Input scaling | Standardised using the training split only |

**The steps:**

1. **Generate the data** and the three inputs for every pair.
2. **Standardise the inputs** using only the training split, so no test information leaks in.
3. **Train for 100 epochs,** saving a checkpoint with a checksum after each one and recording training and validation loss.
4. **Choose the epoch** with the lowest validation loss: epoch 4 (0.4292).
5. **Choose the threshold** with the highest validation F1, from a grid of 0.05 to 0.95: 0.46.
6. **Run the test sets** only after those two choices.

**Where it ran:** Google Colab, with pinned package versions and a recorded code commit (`9621062`).

**Promotion:** training never changes the live model by itself. This run was reviewed and approved for prototype testing on 2026-10-21, replacing v1 epoch 19.

---

## 5. What the training results show

### Loss (Figure 6)

**There is no sign of overfitting, and hardly any learning curve.**

- Training loss stays between 0.430 and 0.433 for all 100 epochs.
- Validation loss stays between 0.429 and 0.446.
- With only four values to learn, one pass over 2,385 pairs is enough for the model to settle. Later movement is noise from the constant learning rate.

**Epoch 4 is the lowest point of that noise, not a clear optimum.** Choosing it by lowest validation loss is the correct rule, but it is not meaningfully better than its neighbours. It also explains why validation loss dips below training loss there (a gap of -0.0036), when the usual gap is about +0.005.

The chart's y-axis is zoomed in heavily. On an axis starting at 0, the two lines would look almost identical.

### Metrics by epoch (Figure 7)

Training and validation stay close on every metric. At epoch 4, ROC-AUC is 0.835 on training and 0.818 on validation. Validation F1 and precision run slightly above training only because validation has more good matches (75% against 73%). These figures use the trainer's standard 0.50 threshold, so they differ slightly from results at the final 0.46.

### Model weights (Figure 8)

| Input | Weight at epoch 4 | Lowest to highest across all epochs | Odds multiplier |
|---|---|---|---|
| Experience readiness | 0.942 | 0.748 to 1.029 | About 2.6 |
| Semantic similarity | 0.708 | 0.707 to 0.926 | About 2.0 |
| Related-skill overlap | 0.682 | 0.657 to 0.882 | About 2.0 |

The odds multiplier is the effect of a one standard deviation rise in that input.

**Read the order with care.** Semantic similarity and skill overlap swap places repeatedly between epochs, so only experience readiness being highest for most of the run is fairly stable. These weights show what the synthetic labels reward, not what real recruiters value.

---

## 6. What each metric means

Every metric below uses the four outcomes of a yes/no decision:

| | Model says good match | Model says poor match |
|---|---|---|
| **Actually good** | True positive (TP) | False negative (FN) |
| **Actually poor** | False positive (FP) | True negative (TN) |

| Metric | Question it answers | Calculation |
|---|---|---|
| Accuracy | How often is the model right overall? | (TP + TN) / all |
| Precision | Of those it accepted, how many were good? | TP / (TP + FP) |
| Recall (true positive rate) | Of the good matches, how many did it accept? | TP / (TP + FN) |
| Specificity | Of the poor matches, how many did it reject? | TN / (TN + FP) |
| False positive rate | Of the poor matches, how many did it wrongly accept? | FP / (TN + FP), or 1 - specificity |
| F1 | A single balance of precision and recall | 2 x precision x recall / (precision + recall) |
| Balanced accuracy | Accuracy treating both classes as equally important | (recall + specificity) / 2 |
| ROC-AUC | How often does a good match outrank a poor one? | See [section 9](#9-understanding-roc-auc) |
| Average precision | How well does precision hold up across all thresholds? | Area under the precision-recall curve. Random picking scores about the share of good matches |
| Log loss | How well do the probabilities match the outcomes? | Penalises confident wrong answers heavily. Lower is better |
| Brier score | How far are the probabilities from the outcomes? | Average of (probability - label) squared. Lower is better |
| Expected calibration error (ECE) | How far are scores from observed rates? | Weighted average gap across score bins. Lower is better |
| Precision@k | How many of the top k are good? | Good matches in the top k / k |
| NDCG@5 | Are good matches placed near the top of the top 5? | Rewards higher placement; 1 is a perfect order |

**Terms used with results:**

- **Threshold:** the score at or above which the model says "good match". The live value is 0.46.
- **Calibration:** whether a score of 0.7 is right about 70% of the time.
- **Bootstrap:** a way to estimate uncertainty by re-drawing the test set with replacement many times. Here it resamples whole candidates 1,000 times, because one candidate's pairs are related.
- **95% interval:** the range the result is likely to fall in. If a difference's interval includes 0, the data does not show a real difference. These intervals do not capture uncertainty from the small number of jobs, so they are, if anything, too narrow.

---

## 7. What the evaluation results show

### Confusion matrices (Figure 9)

**This is the most important figure for honest reporting.** The model finds almost every good match, but lets many poor ones through.

| Split | TN | FP | FN | TP | Accuracy | Precision | Recall | Specificity | F1 | Balanced accuracy |
|---|---|---|---|---|---|---|---|---|---|---|
| Validation | 75 | 123 | 32 | 570 | 0.806 | 0.823 | 0.947 | 0.379 | 0.880 | 0.663 |
| Warm test | 47 | 66 | 14 | 273 | 0.800 | 0.805 | 0.951 | 0.416 | 0.872 | 0.684 |
| Cold test | 26 | 59 | 3 | 210 | 0.792 | 0.781 | 0.986 | 0.306 | 0.871 | 0.646 |

In the cold test, 59 of 85 poor matches are accepted. Accuracy near 80% sounds reasonable, but always saying yes already gets about 72%. Balanced accuracy is the fairer summary.

**Why it happens:** the threshold was chosen for the highest F1, and on data that is 75% positive, F1 favours saying yes.

### Comparison with baselines (Figures 10 to 12)

| Model | Threshold | ROC-AUC warm / cold | F1 warm / cold | Accuracy warm / cold | Specificity warm / cold |
|---|---|---|---|---|---|
| **Hybrid model (live)** | 0.46 | **0.807 / 0.847** | **0.872 / 0.871** | **0.800 / 0.792** | **0.416 / 0.306** |
| Fixed weights | 0.66 | 0.803 / 0.853 | 0.866 / 0.865 | 0.792 / 0.782 | 0.425 / 0.282 |
| Semantic only | 0.05 | 0.625 / 0.728 | 0.836 / 0.834 | 0.718 / 0.715 | 0 / 0 |
| Always say yes | n/a | 0.500 / 0.500 | 0.836 / 0.834 | 0.718 / 0.715 | 0 / 0 |

- **Fixed weights** are a hand-set formula: 0.45 x semantic + 0.40 x skill + 0.15 x experience.
- **Semantic only** is the score a plain embedding matcher would give. Its best threshold is 0.05, which accepts everyone, so it matches always-say-yes on F1 and accuracy.

**Hybrid against semantic only: a clear win.** ROC-AUC gains 0.182 warm and 0.120 cold, and both intervals exclude zero.

**Hybrid against fixed weights: no demonstrated difference.**

| Hybrid minus fixed weights | Warm (95% interval) | Cold (95% interval) |
|---|---|---|
| ROC-AUC | +0.004 (-0.005 to +0.014) | -0.005 (-0.014 to +0.004) |
| F1 | +0.006 (-0.008 to +0.020) | +0.006 (-0.001 to +0.015) |

Every interval includes zero. The learned model's practical advantage is that its scores are calibrated probabilities, while the fixed-weight score is not a probability.

**Average precision** is 0.902 warm and 0.928 cold, against a floor of about 0.72.

### Calibration (Figure 13)

| | Warm | Cold |
|---|---|---|
| ECE | 0.042 | 0.066 |
| Brier score | 0.147 | 0.141 |
| Brier if always guessing the share of good matches | 0.203 | 0.204 |

Above a score of 0.9, 92 to 95% of pairs are good matches, so high scores work as a rough likelihood **on this synthetic population**. The middle is weaker: in the cold test, pairs scoring 0.5 to 0.7 are good matches only about 44% of the time, though those two bins hold only 18 and 16 pairs.

### Score distribution (Figure 14)

Good matches cluster above 0.8, while poor matches spread across the whole range, including many above 0.7. No single threshold separates them cleanly.

### The threshold trade-off (Figure 15)

F1 barely changes from 0.05 to 0.65, so choosing by F1 has little effect on F1 and a large effect on specificity. On validation data:

| Threshold | Accuracy | Precision | Recall | Specificity | F1 |
|---|---|---|---|---|---|
| **0.46 (live)** | 0.806 | 0.823 | 0.947 | 0.379 | 0.880 |
| 0.50 | 0.800 | 0.825 | 0.932 | 0.399 | 0.875 |
| 0.60 | 0.805 | 0.852 | 0.897 | 0.525 | 0.874 |
| 0.70 | 0.778 | 0.872 | 0.826 | 0.631 | 0.848 |
| 0.75 | 0.761 | 0.887 | 0.782 | 0.697 | 0.831 |
| 0.80 | 0.728 | 0.905 | 0.713 | 0.773 | 0.797 |

This shows the trade-off only, and nothing was changed. Because the app ranks candidates and a recruiter makes the decision, a missed good match may be the costlier error, which is a reasonable defence of the current setting.

### Ranking (Figure 16)

Ranking is the job the product actually does. These results combine the warm and cold tests:

| | Hybrid | Fixed weights | Semantic only | Random order |
|---|---|---|---|---|
| **Candidates for each job (96 jobs)** | | | | |
| Precision@1 | 0.927 | 0.927 | 0.865 | 0.710 |
| Precision@3 | 0.837 | 0.837 | 0.788 | 0.709 |
| NDCG@5 | 0.940 | 0.939 | 0.907 | 0.814 |
| **Jobs for each candidate (163 candidates)** | | | | |
| Precision@1 | 0.939 | 0.933 | 0.890 | 0.721 |
| Precision@3 | 0.777 | 0.779 | 0.753 | 0.719 |
| NDCG@5 | 0.967 | 0.965 | 0.946 | 0.885 |

The top-ranked candidate is a good match 93% of the time, against 71% for a random order. The test sets have few pairs per group, so read these as indicative. Hard rules run before scoring in the live app and are not part of these numbers.

### Results by role (Figure 17)

| Role | Pairs | Poor matches | ROC-AUC | F1 | Specificity |
|---|---|---|---|---|---|
| Software Engineer | 155 | 43 | 0.900 | 0.903 | 0.581 |
| Data Analyst | 153 | 48 | 0.846 | 0.848 | 0.271 |
| Accountant | 115 | 28 | 0.806 | 0.886 | 0.429 |
| Business Analyst | 123 | 33 | 0.792 | 0.883 | 0.394 |
| DevOps Engineer | 152 | 46 | 0.773 | 0.846 | 0.217 |

Most intervals overlap, so these are leads to check, not firm differences. This compares job roles. It is not a fairness audit of people.

### Previous model and a fresh population (Figure 18)

| ROC-AUC on v3 labels | Previous model (v1, epoch 19) | Current model (v2, epoch 4) |
|---|---|---|
| Training population, warm | 0.672 | 0.807 |
| Training population, cold | 0.713 | 0.847 |
| Fresh population, warm | 0.735 | 0.864 |
| Fresh population, cold | 0.707 | 0.814 |

Two cautions before quoting that gap:

- **Part of it comes from the labels.** v1 was trained on older labels and is tested here on newer ones. Retrained on the same labels, v1 reaches 0.706 / 0.746 on the training population and 0.749 / 0.752 on the fresh one, which is the fairer comparison. On the older labels, the two tie on warm data (0.799 each) and v2 leads on cold (0.870 against 0.825).
- **The gain depends on the alias assumption** described in [section 3](#3-the-dataset). It only holds if people really do describe skills they hold under other names.

The fresh population uses seed 20261015 and the same generator. It checks that the model did not fit one random draw, but it is not outside evidence.

The current model's confusion matrices on the fresh population:

| Fresh population | TN | FP | FN | TP | Recall | Specificity |
|---|---|---|---|---|---|---|
| Warm test | 63 | 72 | 17 | 248 | 0.936 | 0.467 |
| Cold test | 33 | 56 | 9 | 216 | 0.960 | 0.371 |

---

## 8. Random forest and gradient boosting

The served model is linear. This experiment tests whether non-linear algorithms do better on the same inputs. **It is for the report only and does not change the live model.**

### How it was run

- **Same three inputs and same splits,** with seed 42.
- **Tuned on validation data only,** using the same rule as the served model: lowest validation log loss, then the threshold with the best validation F1.
- **Test data used once,** after tuning.

| Algorithm | Settings tried | Best setting | Threshold |
|---|---|---|---|
| Random forest | 16 | 300 trees, no depth limit, at least 20 pairs per leaf | 0.49 |
| Gradient boosting | 36 | 200 trees of depth 1, learning rate 0.05 | 0.48 |

### Results (Figure 19)

| ROC-AUC | Logistic regression (live) | Random forest | Gradient boosting |
|---|---|---|---|
| Warm test | 0.807 | 0.817 | 0.824 |
| Cold test | 0.847 | 0.848 | 0.859 |
| Fresh population, warm | 0.864 | 0.884 | 0.883 |
| Fresh population, cold | 0.814 | 0.842 | 0.846 |

| Other results | Logistic regression (live) | Random forest | Gradient boosting |
|---|---|---|---|
| Log loss, warm test | 0.459 | 0.451 | 0.440 |
| Log loss, cold test | 0.435 | 0.430 | 0.419 |
| F1, warm test | 0.872 | 0.868 | 0.875 |
| F1, cold test | 0.871 | 0.871 | 0.861 |
| Specificity, warm test | 0.416 | 0.513 | 0.442 |
| Specificity, cold test | 0.306 | 0.424 | 0.318 |
| Recall, warm test | 0.951 | 0.913 | 0.948 |
| Recall, cold test | 0.986 | 0.948 | 0.962 |

**What this shows:**

- **Ranking:** both tree models score higher in all four tests and have lower log loss, but the gain is small: 0.011 to 0.032 ROC-AUC for gradient boosting, and 0.001 to 0.028 for random forest. On the training population every interval includes zero. Only gradient boosting on the fresh population excludes it (+0.018 warm, only just, and +0.032 cold).
- **Yes/no decisions:** F1 does not change. Every interval includes zero, with differences from -0.010 to +0.003.
- **Rejecting poor matches:** random forest's specificity is 9 to 13 points higher, but its recall is about 3 to 5 points lower. That is a trade-off, not a clean win.

**How far to take this:**

- The 32 comparisons were not corrected for testing many things at once.
- The four tests share the same trained models, so they are not four independent confirmations.
- Gradient boosting's best trees have depth 1, which cannot combine inputs, so the gain likely comes from curved effects of single inputs. Because the labels come from a generator, that curve may reflect the generator and not real hiring.

### Overfitting and size (Figure 20)

| | Training ROC-AUC | Validation ROC-AUC | Gap | Size |
|---|---|---|---|---|
| Logistic regression | 0.835 | 0.818 | 0.018 | 4 values |
| Gradient boosting | 0.862 | 0.828 | 0.034 | 600 tree nodes |
| Random forest | 0.885 | 0.823 | 0.063 | 23,672 tree nodes |

The larger models fit their training data more closely, as expected, though they still hold up on new data.

### Why logistic regression stays

**Do not claim logistic regression was the most accurate.** The case for it is:

- **Explainable:** each weight is readable as the effect of one input, which lets a recruiter see why a candidate scored as they did.
- **Small:** four values, against hundreds or thousands of tree nodes.
- **A small cost:** the accuracy given up on synthetic data is small and may reflect the generator.

Changing the model would need real evidence from the gold slice, plus your approval.

---

## 9. Understanding ROC-AUC

### The one-sentence meaning

**If you pick one good match and one poor match at random, ROC-AUC is how often the model scores the good match higher.**

### Worked out on your data

The warm test has 287 good matches and 113 poor ones, which makes 287 x 113 = 32,431 possible pairings. The model scored the good match higher in 26,178 of them:

```
26,178 / 32,431 = 0.807
```

Figure 21's notebook cell checks this calculation against the area under the curve, and the two match.

### How to read the score

| ROC-AUC | Meaning |
|---|---|
| 0.5 | A coin toss |
| 0.7 to 0.8 | Usually called acceptable |
| 0.8 to 0.9 | Usually called good |
| 1.0 | Every good match outranks every poor match |

These bands are a common rule of thumb, not a formal standard.

### How to read the curve (Figure 21)

Each point on the curve is one threshold. This is the same warm test at five thresholds:

| Threshold | Good matches accepted (moves up) | Poor matches accepted (moves right) |
|---|---|---|
| 0.90 | 39% | 9% |
| 0.75 | 78% | 29% |
| 0.60 | 89% | 42% |
| **0.46 (live)** | **95%** | **58%** |
| 0.30 | 98% | 80% |

- **Lowering the threshold** accepts more of both, so you move up and to the right.
- **A good model bulges towards the top-left,** because it accepts many good matches before many poor ones get through.
- **Random guessing** gives the diagonal line, with an area of 0.5.
- **ROC-AUC is the area** under the curve.

### What it does not tell you

- **How the live threshold performs.** The model scores 0.807 and still wrongly accepts 58% of poor matches at 0.46. Always show it next to the confusion matrix.
- **Whether scores are real probabilities.** A model can rank perfectly with badly scaled scores, which is why the calibration chart exists.
- **Whether small gaps matter.** The warm 0.807 has a 95% interval of 0.746 to 0.858, so a difference of 0.01 between models means little on its own.
- **Whether it works on real hiring.** It only measures agreement with the labels you test against, and here those are synthetic.

**A sentence for your report:**

> On held-out synthetic data, the model scored a randomly chosen good match above a randomly chosen poor match 80.7% of the time for known jobs (ROC-AUC 0.807) and 84.7% for unseen jobs (0.847).

---

## 10. Warm test and cold test

**Both tests use candidates the model has never seen. The only difference is the jobs.** Warm test jobs come from the same pool the model trained on, while cold test jobs were kept out of training and validation completely.

| | Candidates | Jobs | Real-world situation |
|---|---|---|---|
| **Warm test** | New | From the pool used in training | A new applicant applies to a role already on the site |
| **Cold test** | New | Never seen (18 jobs) | A company posts a new job, and people are matched to it |

"Cold" comes from the **cold start problem** in recommendation systems: how well can you recommend something the system has no history for?

Think of a recruiter who has only ever handled a certain set of job adverts. The warm test gives them new CVs for those familiar adverts. The cold test gives them new CVs and adverts they have never read.

### Why test both

A model can look good by memorising particular jobs, and a warm test alone would not reveal that. The cold test would, because its score would drop on unseen jobs. New jobs are also routine on a live site, so the model has to handle them.

### What your results show

| ROC-AUC (live model) | Warm | Cold |
|---|---|---|
| Training population | 0.807 | 0.847 |
| Fresh population | 0.864 | 0.814 |

**Unseen jobs do not appear to hurt the model.** There are two likely reasons:

- **It cannot memorise jobs.** The model never sees a job's identity, only three scores for each candidate-job pair. A new job is scored the same way as a familiar one.
- **The encoder was not trained here.** The text encoder behind semantic similarity is pretrained, so it never learned your training jobs either.

### What not to overclaim

- **"Cold" does not mean a new kind of job.** Each of the five roles contributed some cold jobs, all from the same generator. A cold job is a new advert for a familiar role, so the test says nothing about a role the model has never seen, such as a data engineer.
- **The two scores are not a pure comparison.** Each test has different candidates as well as different jobs. The cold test also rests on only 18 jobs, so its result is less certain than its 298 pairs suggest.

---

## 11. Why the cold test scored higher than the warm test

**Most likely chance. There is no sign that the model is better on unseen jobs.** The cold test appears to have received a slightly easier sample.

These checks were a one-off analysis and are not in the notebook.

| Check | Result | What it means |
|---|---|---|
| **Random groupings:** split the same test candidates into two groups at random, 5,000 times | The gap was +0.040, while random groups usually differ by up to about ±0.075. About 30% of splits gave a gap at least this big | The gap is ordinary |
| **Fresh population:** the same test on new synthetic data | The gap flips to -0.050, with warm higher. About 14% of random splits were this big | It does not repeat |
| **Share of good matches:** an easier mix could inflate the score | 71.8% warm, 71.5% cold | The mix is not the cause |
| **One unusual job:** remove each cold job in turn | Cold stays between 0.839 and 0.858 | No single job explains it |

### Where the gap came from

It mostly comes down to which pairs landed in each test, and the biggest swings by role do not agree with each other:

| ROC-AUC by role (training population) | Warm | Cold |
|---|---|---|
| Accountant | 0.806 | 0.830 |
| Business Analyst | **0.859** | 0.704 |
| Data Analyst | **0.880** | 0.807 |
| DevOps Engineer | 0.701 | **0.892** |
| Software Engineer | 0.883 | 0.923 |

These scores rest on only 9 to 28 poor matches per role in each test, so a few pairs can move them a lot. DevOps also does not repeat: on the fresh population it scores 0.853 warm and 0.828 cold.

In the cold test's sample, semantic similarity and skill overlap also separated good from poor matches more clearly (gaps of 0.092 and 0.087, against 0.052 and 0.064 for warm). On the fresh population the semantic gaps were almost equal, and so were the skill gaps, so that pattern did not repeat.

### Why cold does not have to be lower

People usually expect unseen data to score lower because a model has memorised what it trained on. This model never sees which job it is scoring, so it has nothing job-specific to memorise. Warm and cold should therefore score about the same, with random differences either way, and that is what the two populations show.

**This does not prove the two are exactly equal.** With tests this small, a real difference of a few points could go undetected, and the random splits do not fully capture how few jobs are involved. What you can say is that there is no evidence of a difference.

**A sentence for your report:**

> ROC-AUC was higher on unseen jobs in the main test (0.847 against 0.807) but lower on a second synthetic population (0.814 against 0.864). Both gaps fall within what random grouping of candidates produces, so there is no evidence that performance differs between known and unseen jobs.

---

## 12. Can a recruiter choose a low-scoring candidate?

**Yes. A recruiter can shortlist and hire someone with any score, even 0%. The system does not warn them or notify the admin.** The move is written to an activity log the admin can read. This section describes the code as of 2026-11-05, read from the source and not tested on the live site.

### What the scores mean

- **Score of 1 (100%):** the strongest possible match, so there is nothing to warn about.
- **Score of 0:** usually means the candidate failed a hard rule. An eligible candidate with a very low score can also display as 0%, because scores are rounded.

### What happens at each step

| Where the recruiter acts | Can they pick a candidate with a 0 score? | What they see |
|---|---|---|
| **Hiring flow** (match analysis page), first step | No. Candidates who failed a hard rule are not offered, only counted in a note | Eligible candidates with low scores can still be picked by raising "Move on the top", with no warning. They just lack the "Recommended" label |
| **Hiring flow**, later steps | Yes, if they were already moved forward | The score is shown, but the hire prompt only says "Hire [name]? This cannot be reversed." |
| **Applicant list on the roles page** | **Yes, for any applicant** | The list shows no score, and the prompt is the same for everyone |
| **Directly through the API** | **Yes** | The server only checks that the stage order is valid and that the recruiter owns the job. It never looks at the score or hard rules |

**Stage order is enforced:** a hire must follow a confirmed interview. The allowed moves are:

| From | Can move to |
|---|---|
| Submitted | Reviewing, shortlisted, rejected |
| Reviewing | Shortlisted, rejected |
| Shortlisted | Interviewed, rejected |
| Interviewed | Hired, rejected |

**Simulated hiring is stricter than a real recruiter:** it only ever picks eligible candidates, and only demo applicants.

### What the admin gets

- **Activity log:** each move records who made it, which application and the new status, but not the score or whether the candidate passed the rules. A move on a 0% candidate looks the same as any other.
- **Notifications:** the app has no notification system, by email or in-app. The admin would only find out by reading the log, and could not tell which entries matter.

### Recommended design (not built)

**Warn and record the decision, but do not block it.** Recruiters should keep the final say, because the model is only tested on synthetic data and can be wrong. A hard-rule failure can also be out of date, such as a certificate the candidate has earned but not yet listed.

1. **Warning:** when a recruiter advances someone who failed a hard rule or scored below the 0.46 threshold, show why and ask them to confirm, on every screen.
2. **Required reason:** ask for a short reason when hiring someone who failed a hard rule. This keeps a human in control and accountable.
3. **Server check:** enforce this on the server too, so it cannot be skipped through the API.
4. **Admin visibility:** record the score, the rule result and the reason in the log, and add an "Overrides" filter with a count on the admin dashboard. An admin can then review overrides together, instead of receiving a message for each one.

**Still to decide:** whether the reason is required only for hard-rule failures, or for low scores too. Starting with hard-rule failures avoids a box people soon click through without thinking.

---

## 13. Ranking speed on the live server

The project's speed target (NFR-02) is 2 to 5 seconds per matching request. `deploy/jb measure-latency` measured the live server on 2026-11-05, using the role with the most eligible candidates (170 candidates, 115 eligible):

| Ranking run | Median | Range | Target of 2-5 s |
|---|---|---|---|
| Nothing cached | 9.46 s | 8.66 to 10.75 s | Missed |
| Repeat, cached | 0.03 s | 0.03 s every run | Met |

- Loading the model and the first pass took a further 16.4 s, which is excluded.
- This covers the ranking step only, without saving results or the web request, so a real evaluation takes slightly longer.
- Embeddings are held in memory, so the slow case should mostly come after an API restart, which includes every deploy.

**Decision on 2026-11-05:** leave this as an accepted limitation for now. If this changes, building the embedding cache when the API starts is the likely fix.

---

## 14. What you can and cannot claim

### Safe to claim

On seeded synthetic data with leakage-controlled splits, the three-input model:

- ranks well above random and above semantic similarity alone,
- shows no sign of overfitting,
- gives reasonably calibrated scores, especially at the high end,
- does not consistently perform worse on unseen jobs.

### Not safe to claim

- That it predicts real hiring outcomes.
- That it beats the hand-set fixed weights.
- That logistic regression is the most accurate algorithm tried.
- That it rejects weak candidates reliably.
- That the full gap over the previous model comes from better features.
- That it handles job roles it has never seen.

### Summary table

| Question | Answer | Figure |
|---|---|---|
| Is the data balanced? | Roles yes. Labels no: about 73% good matches | 1, 2 |
| Did it overfit? | No sign of it | 6, 7 |
| Did it need 100 epochs? | No. Loss settles in the first epoch | 6 |
| How well does it rank? | ROC-AUC 0.807 warm, 0.847 cold. Top pick good 93% of the time, against 71% at random | 11, 16 |
| How good is the yes/no decision? | Recall 95-99%, specificity only 31-42% | 9 |
| Better than semantic similarity alone? | Yes, clearly | 10, 11 |
| Better than fixed weights? | Not shown. Differences are within noise | 10 |
| Are scores usable as probabilities? | Reasonably at the high end, noisier in the middle | 13 |
| Is logistic regression the most accurate? | No. The tree models rank slightly better, with the same F1 | 19, 20 |
| Does it match human judgement? | **Unknown.** Gold slice: 0 of 150 labelled | Last notebook cell |

---

## 15. Questions an examiner may ask

**Why logistic regression?**
It is explainable and small, which suits a recruiting tool where people need to see why someone scored as they did. Random forest and gradient boosting were tested on the same data and ranked slightly better, with the same F1. The small gain does not outweigh explainability while the data is synthetic.

**Why is the training curve flat?**
The model has only four values and three inputs, so it settles within one epoch. A flat curve with training and validation close together shows no overfitting, and it also shows there was little left to learn.

**Why did you train for 100 epochs then?**
The run was fixed at 100 so the whole curve could be inspected instead of assuming when to stop. The chart then showed that far fewer were needed.

**Accuracy is 80%. Is that good?**
Only modestly, because always saying yes gets about 72%. Balanced accuracy (0.65 to 0.68), ROC-AUC and the confusion matrix give a fairer picture.

**Why is specificity so low?**
The threshold maximises F1 on data that is mostly positive, which favours saying yes. A higher threshold would reject more poor matches at the cost of missing good ones. A recruiter makes the final decision, so missing a good match may be the costlier error.

**Why not use real data?**
Permitted real hiring outcomes were not available. The gold slice is the planned independent check: 150 pairs for a person to judge without seeing any score.

**How do you know the test results are not inflated?**
Candidates are kept separate across splits, cold jobs are held out completely, scaling uses only training data, and the epoch and threshold were chosen on validation data. The remaining limit is that the labels come from the same generator as the data, which is why results are not presented as real-world quality.

**Could the system be biased?**
These results do not test fairness across people. Results by role are not a fairness audit. See `docs/BIAS_AND_EXPLAINABILITY.md`.

---

## 16. Figures and how to reproduce them

| Figure | File in `notebooks/figures/` | Shows |
|---|---|---|
| 1 | `01_candidates_jobs_by_role.png` | Candidates and jobs by role |
| 2 | `02_splits_and_class_balance.png` | Splits and class balance |
| 3 | `03_profiles.png` | Experience, education and location |
| 4 | `04_top_skills.png` | Top skills |
| 5 | `05_features_by_label.png` | Model inputs by label |
| 6 | `06_training_validation_loss.png` | Training and validation loss |
| 7 | `07_metrics_by_epoch.png` | Training and validation metrics by epoch |
| 8 | `08_model_weights.png` | Model weights |
| 9 | `09_confusion_matrices.png` | Confusion matrices |
| 10 | `10_baseline_comparison.png` | Comparison with baselines |
| 11 | `11_roc_curves.png` | ROC curves |
| 12 | `12_precision_recall_curves.png` | Precision-recall curves |
| 13 | `13_calibration.png` | Calibration |
| 14 | `14_score_distribution.png` | Score distribution |
| 15 | `15_threshold_tradeoff.png` | Threshold trade-off |
| 16 | `16_ranking_quality.png` | Ranking quality |
| 17 | `17_results_by_role.png` | Results by role |
| 18 | `18_model_generations_and_fresh_population.png` | Previous model and fresh population |
| 19 | `19_algorithm_comparison.png` | Random forest and gradient boosting |
| 20 | `20_overfitting_by_algorithm.png` | Overfitting and model size |
| 21 | `21_how_to_read_roc.png` | How to read ROC-AUC |

The same folder holds `test_metrics.csv`, `algorithm_comparison.csv` and `epoch_history.csv`.

**To re-run the notebook:** open `notebooks/model_visuals.ipynb` with the project's `venv` kernel on the original laptop. It reads data from git-ignored folders and from `%LOCALAPPDATA%\JobBridge`, so another machine needs `data_pipeline/compare_feature_contracts.py` run first. The saved notebook still opens anywhere with its charts.

**Integrity check:** the notebook recalculates the recorded metrics and stops if they differ. ROC-AUC and F1 match exactly, and log loss is within 1e-8. The cached inputs are not byte-identical to the Colab run, because the embeddings were computed on a different machine.
