export type ApiHealth = {
  status: "ok" | "degraded";
  database: { postgres: "ok" | "error"; neo4j: "ok" | "error" };
};

export type UserRole = "candidate" | "recruiter" | "admin";

export type JobInput = {
  title: string;
  description: string;
  location: string;
  requiredExperienceYears: number;
  salaryRangeMax: number;
  mandatoryCertifications: string[];
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
  // Planned contracts: enabled when the corresponding FastAPI routes land.
  login: (email: string, password: string) =>
    request<{ access_token: string; role: UserRole }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  createJob: (job: JobInput, token: string) =>
    request<{ jobId: string }>("/jobs/create", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(job),
    }),
};
