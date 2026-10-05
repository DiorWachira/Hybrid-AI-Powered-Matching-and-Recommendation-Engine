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
  salaryRangeMax: number | null;
  salaryRangeMin?: number | null;
  requiresWorkAuthorization?: boolean;
  requiredSkills: string[];
  mandatoryCertifications: string[];
};

export type JobPosting = {
  job_id: string; title: string; description: string; location: string | null;
  required_experience_years: number; salary_range_max: number | string | null;
  salary_range_min: number | string | null; requires_work_authorization: boolean;
  required_skills: string[] | null; mandatory_certifications: string[] | null;
  status: "open" | "closed"; posted_at: string | null;
};
export type ApplicationStatus = "submitted" | "reviewing" | "shortlisted" | "rejected" | "hired" | "withdrawn";
export type RecruiterStatus = "reviewing" | "shortlisted" | "rejected" | "hired";
export type Application = { application_id: string; candidate_id: string; job_id: string; status: ApplicationStatus; created_at: string; updated_at: string };
export type Applicant = Application & { candidate_name: string; candidate_location: string | null; years_experience: number; skills: string[]; certifications: string[] };
export type CandidateApplication = Application & { job_title: string; company_name: string; job_location: string | null; job_status: "open" | "closed" };

const jobPayload = (job: JobInput) => ({
  title: job.title, description: job.description, location: job.location || null,
  required_experience_years: job.requiredExperienceYears, salary_range_max: job.salaryRangeMax,
  salary_range_min: job.salaryRangeMin ?? null, requires_work_authorization: job.requiresWorkAuthorization ?? false,
  required_skills: job.requiredSkills, mandatory_certifications: job.mandatoryCertifications,
});

export type CandidateProfileInput = {
  full_name: string;
  location?: string | null;
  years_experience: number;
  expected_salary?: number | string | null;
  work_authorized?: boolean | null;
  parsed_resume_text?: string | null;
  skills: string[];
  certifications: string[];
};

export type MatchCandidate = {
  match_id?: string | null;
  matched_skills?: string[] | null;
  missing_skills?: string[] | null;
  model_version?: string | null;
  candidate_id: string;
  full_name: string;
  hard_rule_passed: boolean;
  rule_reasons: string[];
  skill_overlap: number;
  semantic_score: number;
  growth_score: number;
  final_score: number;
};

export type MatchEvaluation = {
  job_id: string;
  evaluated_at: string | null;
  candidates: MatchCandidate[];
};

export type MatchGraph = {
  nodes: Array<{ id: string; label: string; kind: "candidate" | "job" | "skill" }>;
  edges: Array<{ id: string; source: string; target: string; label: string; weight?: number | null; status?: string | null }>;
  state: "current_projection" | "awaiting_projection";
  truncated: boolean;
};

export type AdminUser = {
  user_id: string;
  email: string;
  role: UserRole;
  display_name: string;
  company_name?: string | null;
  is_active: boolean;
  is_demo: boolean;
  created_at: string;
};

export type OntologySkill = { name: string; category: string | null; source: string | null };
export type OntologyRelation = { source_skill: string; target_skill: string; weight: number; source: string | null };
export type OntologyData = { skills: OntologySkill[]; relationships: OntologyRelation[] };

export type AdminOverview = {
  users_count: number;
  candidates_count: number;
  employers_count: number;
  jobs_count: number;
  match_results_count: number;
  applications_count: number;
  pending_graph_events: number;
  suspended_users_count: number;
  recent_users: AdminUser[];
  recent_activity: Array<{ event_id: string; actor_user_id: string | null; action: string; resource_type: string; resource_id: string | null; details: Record<string, unknown> | null; created_at: string }>;
  recent_jobs: Array<{ job_id: string; title: string; status: string; location?: string; required_experience_years: number; salary_range_max?: number; required_skills?: string[]; mandatory_certifications?: string[]; description: string }>;
};

export type Opportunity = {
  job_id: string;
  title: string;
  company_name: string;
  description: string;
  location?: string;
  salary_range_max?: number;
  required_experience_years: number;
  required_skills: string[];
  mandatory_certifications: string[];
  match_score: number;
  status?: "saved" | "applied" | "viewed";
};

export type CandidateDashboard = {
  available_opportunities: Opportunity[];
  for_you: Opportunity[];
  history: Opportunity[];
};

export type BrowsedOpportunity = Omit<Opportunity, "match_score" | "location" | "salary_range_max"> & {
  match_score: null;
  location: string | null;
  salary_range_max: number | string | null;
  job_status: "open" | "closed";
};

const API_PREFIX = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  } catch {
    throw new Error("Cannot reach JobBridge. Check your connection and try again.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | Array<{ msg: string; loc: string[] }> } | null;
    const detail = typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map((item) => `${item.loc.slice(1).join(" ")}: ${item.msg}`).join(". ") : null;
    throw new Error(detail ?? (response.status >= 500 ? "The service is currently unavailable. Please try again shortly." : `Request failed (${response.status}). Please try again.`));
  }

  return response.json() as Promise<T>;
}

export const api = {
  ontology: (token: string, search: string) => request<OntologyData>(`/admin/ontology?${new URLSearchParams({search})}`, {headers:{Authorization:`Bearer ${token}`}}),
  saveSkill: (token: string, skill: OntologySkill) => request<OntologySkill>("/admin/ontology/skills", {method:"PUT",headers:{Authorization:`Bearer ${token}`},body:JSON.stringify(skill)}),
  saveRelation: (token: string, relation: OntologyRelation, remove: boolean) => request<{status:string}>(`/admin/ontology/relationships?remove=${remove}`, {method:"PUT",headers:{Authorization:`Bearer ${token}`},body:JSON.stringify(relation)}),
    resetPassword: (token: string, newPassword: string) => request<{ message: string }>("/auth/reset-password", {
      method: "POST", body: JSON.stringify({ token, new_password: newPassword }),
    }),
    issuePasswordReset: (token: string, userId: string, password: string) => request<{ token: string; expires_at: string }>(`/admin/users/${userId}/password-reset`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ password }),
    }),
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
    request<JobPosting>("/jobs/create", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(jobPayload(job)),
    }),
  myJobs: (token: string, offset = 0, limit = 6) => request<JobPosting[]>(`/jobs/mine?${new URLSearchParams({ offset: String(offset), limit: String(limit) })}`, { headers: { Authorization: `Bearer ${token}` } }),
  updateJob: (jobId: string, job: JobInput, status: "open" | "closed", token: string) => request<JobPosting>(`/jobs/${jobId}`, { method: "PUT", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ ...jobPayload(job), status }) }),
  changeOwnJobStatus: (jobId: string, status: "open" | "closed", token: string) => request<JobPosting>(`/jobs/${jobId}/status`, { method: "PATCH", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }) }),
  jobApplications: (jobId: string, token: string, offset = 0, limit = 6) => request<Applicant[]>(`/jobs/${jobId}/applications?${new URLSearchParams({ offset: String(offset), limit: String(limit) })}`, { headers: { Authorization: `Bearer ${token}` } }),
  changeApplicationStatus: (jobId: string, applicationId: string, status: RecruiterStatus, token: string) => request<Application>(`/jobs/${jobId}/applications/${applicationId}`, { method: "PATCH", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }) }),
  myApplications: (token: string, offset = 0, limit = 6) => request<CandidateApplication[]>(`/candidates/me/applications?${new URLSearchParams({ offset: String(offset), limit: String(limit) })}`, { headers: { Authorization: `Bearer ${token}` } }),
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
  uploadResume: (file: File, token: string) => {
    const body = new FormData();
    body.append("resume", file);
    return request<CandidateProfileInput>("/candidates/upload-resume", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
  },
  browseOpportunities: (token: string, filters: Record<string, string>) => request<BrowsedOpportunity[]>(`/candidates/opportunities?${new URLSearchParams(filters)}`, { headers: { Authorization: `Bearer ${token}` } }),
  removeSavedOpportunity: (jobId: string, token: string) => request<{ removed: boolean }>(`/candidates/opportunities/${jobId}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }),
  candidateDashboard: (token: string) =>
    request<CandidateDashboard>("/candidates/dashboard", {
      headers: { Authorization: `Bearer ${token}` },
    }),
  updateOpportunityStatus: (jobId: string, status: "saved" | "applied" | "viewed", token: string) =>
    request<Opportunity>(`/candidates/opportunities/${jobId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ status }),
    }),
  evaluateMatches: (jobId: string, token: string) =>
    request<MatchEvaluation>(`/matches/evaluate/${jobId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  savedMatches: (jobId: string, token: string) =>
    request<MatchEvaluation>(`/matches/jobs/${jobId}`, { headers: { Authorization: `Bearer ${token}` } }),
  matchGraph: (matchId: string, token: string) =>
    request<MatchGraph>(`/matches/${matchId}/graph`, { headers: { Authorization: `Bearer ${token}` } }),
  adminOverview: (token: string) =>
    request<AdminOverview>("/admin/overview", {
      headers: { Authorization: `Bearer ${token}` },
    }),
  adminUsers: (token: string, search: string, offset: number) =>
    request<AdminUser[]>(`/admin/users?${new URLSearchParams({ search, offset: String(offset) })}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  setAccountActive: (token: string, userId: string, isActive: boolean) =>
    request<AdminUser>(`/admin/users/${userId}`, {
      method: "PATCH", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ is_active: isActive }),
    }),
  setJobStatus: (token: string, jobId: string, status: "open" | "closed") =>
    request<AdminOverview["recent_jobs"][number]>(`/admin/jobs/${jobId}`, {
      method: "PATCH", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }),
    }),
};
