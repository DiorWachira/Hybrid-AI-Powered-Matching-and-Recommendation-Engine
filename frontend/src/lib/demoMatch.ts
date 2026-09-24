/**
 * Illustrative data for the marketing page only.
 *
 * Shapes intentionally mirror what /api/match/results/{job_id} will return, so the
 * landing page previews the real explainability payload rather than inventing a
 * different vocabulary. Every value here is demo content until the endpoint lands.
 */

export type SubScore = {
  key: "S_bert" | "S_graph" | "S_growth";
  label: string;
  value: number;
  blurb: string;
};

export type HardFilter = {
  label: string;
  passed: boolean;
};

export const demoCandidate = {
  reference: "CAND-0412",
  role: "DevOps Engineer",
  specialisation: "platform reliability",
  location: "Nairobi",
  yearsExperience: 6,
  expectedSalaryKes: 210_000,
  skills: ["Kubernetes", "Docker", "CI/CD", "Linux", "Terraform"],
  certifications: ["AWS Certified Cloud Practitioner"],
};

export const demoRole = {
  reference: "ROLE-1187",
  title: "Senior DevOps Engineer",
  specialisation: "platform reliability",
  company: "Fintech scale-up",
  location: "Nairobi",
  requiredExperience: 5,
  salaryCeilingKes: 250_000,
  requiredSkills: ["Kubernetes", "Docker", "CI/CD", "Linux", "AWS"],
};

export const demoMatch = {
  index: 0.941,
  subScores: [
    {
      key: "S_bert",
      label: "Semantic fit",
      value: 0.86,
      blurb: "Résumé and role text embedded and compared by meaning, not keywords.",
    },
    {
      key: "S_graph",
      label: "Skill graph overlap",
      value: 0.92,
      blurb: "Direct and related-skill matches traversed across the skill ontology.",
    },
    {
      key: "S_growth",
      label: "Growth headroom",
      value: 0.88,
      blurb: "Experience depth and recent certifications signal room to grow.",
    },
  ] satisfies SubScore[],
  hardFilters: [
    { label: "Minimum experience met", passed: true },
    { label: "Location compatible", passed: true },
    { label: "Within salary band", passed: true },
    { label: "Mandatory certification held", passed: true },
  ] satisfies HardFilter[],
  matchedSkills: ["Kubernetes", "Docker", "CI/CD", "Linux"],
  missingSkills: ["AWS"],
};

/**
 * Engine figures measured on the held-out synthetic evaluation split.
 * `illustrative` marks anything not yet backed by a measurement, so nothing on the
 * page can be mistaken for a production result.
 */
export const engineMetrics = [
  {
    value: "0.50 → 0.80",
    label: "Evaluation band",
    detail: "Majority-class floor to Bayes ceiling on the held-out split",
    illustrative: false,
  },
  {
    value: "2 tier",
    label: "Matching pipeline",
    detail: "Deterministic compliance filter, then hybrid semantic scoring",
    illustrative: false,
  },
  {
    value: "5",
    label: "Role families covered",
    detail: "Data, DevOps, software, finance and business analysis",
    illustrative: false,
  },
  {
    value: "< 5s",
    label: "Target match latency",
    detail: "Per-request budget for filtering and scoring",
    illustrative: true,
  },
];

export const testimonials = [
  {
    quote:
      "The shortlist arrived with the reasoning attached. Seeing which skills matched and which were missing changed how we ran the interview loop.",
    name: "Engineering Manager",
    context: "Fintech scale-up, Nairobi",
    rating: 5,
  },
  {
    quote:
      "Two-way matching meant I stopped getting roles that ignored my salary band and location. The compliance filter does real work before anything is scored.",
    name: "Senior Data Analyst",
    context: "Health informatics",
    rating: 5,
  },
  {
    quote:
      "Transferable skills finally counted. The graph picked up adjacent experience a keyword filter would have discarded outright.",
    name: "Business Analyst",
    context: "Regulatory change programme",
    rating: 5,
  },
];
