export type ApiHealth = {
  status: "ok" | "degraded";
  database: { postgres: "ok" | "error"; neo4j: "ok" | "error" };
};

export type UserRole = "candidate" | "recruiter" | "admin";

export type RegisterInput = {
  email: string;
  password: string;
  role: Exclude<UserRole, "admin">;
  full_name?: string;
  company_name?: string;
  industry?: string;
  location?: string;
};

export type JobInput = {
  title: string;
  description: string;
  location: string;
  requiredExperienceYears: number;
  salaryRangeMax: number;
  requiredSkills: string[];
  mandatoryCertifications: string[];
};

export type CandidateProfileInput = {
  full_name: string;
  location?: string;
  years_experience: number;
  expected_salary?: number;
  parsed_resume_text?: string;
  skills: string[];
  certifications: string[];
};

export type MatchCandidate = {
  candidate_id: string;
  full_name: string;
  hard_rule_passed: boolean;
  rule_reasons: string[];
  skill_overlap: number;
  semantic_score: number;
  growth_score: number;
  final_score: number;
};

const API_PREFIX = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<ApiHealth>("/health"),
  register: (payload: RegisterInput) =>
    request<{ access_token: string; role: UserRole }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string; role: UserRole }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  createJob: (job: JobInput, token: string) =>
    request<{ job_id: string }>("/jobs/create", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        title: job.title,
        description: job.description,
        location: job.location,
        required_experience_years: job.requiredExperienceYears,
        salary_range_max: job.salaryRangeMax,
        required_skills: job.requiredSkills,
        mandatory_certifications: job.mandatoryCertifications,
      }),
    }),
  getCandidateProfile: (token: string) =>
    request<CandidateProfileInput>("/candidates/me", {
      headers: { Authorization: `Bearer ${token}` },
    }),
  updateCandidateProfile: (profile: CandidateProfileInput, token: string) =>
    request<CandidateProfileInput>("/candidates/me", {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(profile),
    }),
  evaluateMatches: (jobId: string, token: string) =>
    request<{ job_id: string; candidates: MatchCandidate[] }>(`/matches/evaluate/${jobId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
};
