import type { EligibilityRequirement, MatchCandidate, ScoringModel } from "./api";

/**
 * What the recruiter is told after an evaluation: how each decision was reached, where bias could enter at each
 * step, and what the system does about it. Every statement here must stay true of the code it describes:
 * backend/app/core/rule_filter.py, text_preprocessing.py, match_features.py and hybrid_matcher.py.
 */

export type RuleKey = EligibilityRequirement["rule"];
export type BiasNote = { risk: string; guard: string };

export const RULES: Record<RuleKey, { name: string; checks: string; failure: string; bias: BiasNote }> = {
  work_authorization: {
    name: "Right to work",
    checks: "The candidate has confirmed they may work in this role, when the posting requires it.",
    failure: "work authorization not confirmed",
    bias: {
      risk: "Can exclude refugees and foreign nationals who are in fact allowed to work, and anyone who simply left the question unanswered.",
      guard: "Applied only when you mark it required. It reads the candidate's own yes or no, never nationality, country of birth or ID type. A failure means \"not confirmed\", not \"not allowed\".",
    },
  },
  experience: {
    name: "Minimum experience",
    checks: "The candidate has at least the years of experience the posting asks for.",
    failure: "minimum experience not met",
    bias: {
      risk: "Years of experience follow age, so a high minimum screens out younger people and those with career breaks, who are often carers.",
      guard: "Only the minimum you posted is used. Age and date of birth are never read. Above the minimum, experience earns credit only up to 1.5 times the requirement, so a long career cannot outrank someone who meets the bar on years alone.",
    },
  },
  location: {
    name: "Location",
    checks: "The candidate's location is the same as the posting's, when both are set.",
    failure: "location incompatible",
    bias: {
      risk: "Where someone lives can stand in for region, ethnic community or income. This rule can exclude capable people from other counties.",
      guard: "Applied only when both you and the candidate give a location. It is a plain same-or-different check with no ranking of places. Major Kenyan town names are removed from CV text before the language model reads it, so location does not move an eligible candidate's score. Leave location blank for remote roles.",
    },
  },
  salary: {
    name: "Salary ceiling",
    checks: "The candidate's expected salary is no more than the posting's maximum, when both are set.",
    failure: "salary expectation exceeds job ceiling",
    bias: {
      risk: "Screens on one figure the candidate typed, which may be out of date or negotiable.",
      guard: "Compared only with the maximum you posted. Salary is never part of the match score, so asking less does not rank anyone higher.",
    },
  },
  certifications: {
    name: "Mandatory certifications",
    checks: "The candidate lists every certification the posting marks as mandatory.",
    failure: "mandatory certifications missing",
    bias: {
      risk: "Excludes people with equal skill but no certificate, such as the self-taught or those who could not afford exam fees.",
      guard: "Only certifications you mark mandatory count. Optional certifications add nothing to the score, so paid credentials cannot buy a higher ranking.",
    },
  },
};

export const RULE_ORDER: RuleKey[] = ["work_authorization", "experience", "location", "salary", "certifications"];

/** Which rule a stored reason refers to. Reasons are the fixed strings from rule_filter.py. */
export function ruleOf(reason: string): RuleKey | null {
  return RULE_ORDER.find((key) => reason.startsWith(RULES[key].failure)) ?? null;
}

export const INPUTS: Record<ScoringModel["inputs"][number]["key"], { name: string; measures: string; bias: BiasNote }> = {
  semantic_score: {
    name: "Semantic similarity",
    measures: "How close the CV is in meaning to the job description, read by a pretrained language model.",
    bias: {
      risk: "The language model learnt from general English web text. It can favour polished English and familiar phrasing, and may carry stereotypes from that text.",
      guard: "Names, email addresses, phone numbers, links, gender words, ages, dates of birth and major Kenyan town names are removed before it reads the CV. It is one of three inputs; the other two come from structured skills and years. Removal is best effort: pronouns, school names or clubs can still hint at who someone is.",
    },
  },
  skill_overlap: {
    name: "Related-skill overlap",
    measures: "How many required skills the candidate lists. A related skill earns partial credit through a fixed skill graph.",
    bias: {
      risk: "Exact skill names favour people who know the industry's jargon, or trained where the same skill has another name.",
      guard: "Related skills earn partial credit, so PostgreSQL counts towards SQL. The skill graph is a versioned file pinned to the model, so nobody can quietly re-weight skills for one evaluation.",
    },
  },
  growth_score: {
    name: "Experience readiness",
    measures: "Years of experience against the posting's requirement, capped at 1.5 times the requirement.",
    bias: {
      risk: "More years usually means older, so experience can favour age over ability.",
      guard: "The cap stops long careers from piling up extra credit. Years beyond 1.5 times the requirement add nothing.",
    },
  },
};

export const INPUT_ORDER = ["semantic_score", "skill_overlap", "growth_score"] as const;

/** What the model is never given, and how. Kept in one list so the page and the report say the same thing. */
export const NOT_USED = [
  "Name, email, phone number and links, removed from the CV text before scoring",
  "Gender words, age and date of birth, removed from the CV text before scoring",
  "Major Kenyan town names, removed from the CV text; location is only an eligibility rule",
  "Photos: only the CV's text is read, and the uploaded file is not kept",
  "Nationality, ethnicity, religion, marital status and disability: never asked for",
  "Salary, application date and the order people signed up in",
];

export const COMBINER_NOTE: BiasNote = {
  risk: "A model trained on past hiring decisions can learn the bias in them.",
  guard: "This model has no past hiring decisions to learn from: it was trained on synthetic labels, and it sees only the three numbers above. Everyone is scored with the same weights and the same threshold, and ties are broken by a random ID, never by name or sign-up order. The other side of this is that it has not been checked against real hiring outcomes, and fairness across groups has not been measured, because the platform does not collect group data.",
};

export type Scenario = "recommended" | "below_threshold" | "failed_rules" | "older_model";

export const SCENARIOS: Record<Scenario, { title: string; decision: string; watch: string; avoid: string; next: string }> = {
  recommended: {
    title: "Recommended",
    decision: "Passed every eligibility rule, and the combined score is at or above the decision threshold.",
    watch: "Automation bias: trusting the label more than it deserves. In synthetic testing the model accepted 95 to 99% of good matches but turned away only 31 to 42% of weak ones, so \"Recommended\" is a broad pass, not proof of fit.",
    avoid: "The score uses only skills, experience and anonymised CV text, never who the person is. The breakdown below shows exactly which inputs raised it.",
    next: "Check the missing skills, then let the interview decide.",
  },
  below_threshold: {
    title: "Eligible, below the threshold",
    decision: "Passed every eligibility rule, but the combined score is below the decision threshold.",
    watch: "A capable candidate can score low because they write differently or name their skills differently. Check which input pulled the score down: if it is semantic similarity, read the CV yourself.",
    avoid: "Related skills earn partial credit, and the language model is not shown names, gender words, ages or major town names. The threshold is the same for everyone.",
    next: "You can still move this person forward. You will see a warning, and the move is recorded with the score.",
  },
  failed_rules: {
    title: "Requirements not met",
    decision: "Did not meet one or more of the eligibility rules set on this posting, so no match score was calculated.",
    watch: "The rule, not the model, decided here. A rule that is stricter than the job needs excludes people unfairly, and a profile can be out of date.",
    avoid: "Because no score was calculated, the model's possible biases played no part. The rules are the ones you set, applied the same way to every candidate.",
    next: "If a rule does not reflect a real need, edit the posting and evaluate again rather than overriding people one by one. To move this person forward anyway you must give a reason, which the administrator can review.",
  },
  older_model: {
    title: "Scored by an earlier model",
    decision: "This result came from a model that is no longer served, so its threshold is not known here.",
    watch: "Comparing scores from two models side by side is unfair to one of them.",
    avoid: "Evaluate again so every candidate is scored by the same model.",
    next: "Select Evaluate candidates.",
  },
};

export function scenarioOf(candidate: MatchCandidate): Scenario {
  if (!candidate.hard_rule_passed) return "failed_rules";
  if (candidate.recommended == null) return "older_model";
  return candidate.recommended ? "recommended" : "below_threshold";
}

export type Contribution = { key: (typeof INPUT_ORDER)[number]; value: number; average: number; push: number };

/**
 * The logistic regression, step by step, exactly as calibrated_score_for computes it: each input is standardised
 * against the training average and spread, multiplied by its weight, and added to the intercept.
 */
export function explainScore(candidate: MatchCandidate, model: ScoringModel) {
  const contributions: Contribution[] = model.inputs.map((input) => ({
    key: input.key, value: candidate[input.key], average: input.mean,
    push: input.weight * (candidate[input.key] - input.mean) / input.scale,
  }));
  const logit = model.intercept + contributions.reduce((sum, item) => sum + item.push, 0);
  return { contributions, logit, probability: 1 / (1 + Math.exp(-logit)) };
}

/** How many candidates each rule removed, so a rule that excludes many people is visible. */
export function exclusionsByRule(candidates: MatchCandidate[]) {
  const counts = Object.fromEntries(RULE_ORDER.map((key) => [key, 0])) as Record<RuleKey, number>;
  for (const candidate of candidates) {
    const rules = new Set(candidate.rule_reasons.map(ruleOf).filter((key): key is RuleKey => key !== null));
    for (const key of rules) counts[key] += 1;
  }
  return counts;
}
