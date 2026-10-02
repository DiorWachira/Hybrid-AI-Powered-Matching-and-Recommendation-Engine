import type { UserRole } from "./api";

export function getSessionRole(): UserRole | null {
  const token = localStorage.getItem("jobbridge_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as { role?: string; exp?: number };
    if (typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now()) return null;
    return payload.role === "candidate" || payload.role === "recruiter" || payload.role === "admin" ? payload.role : null;
  } catch {
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem("jobbridge_token");
  localStorage.removeItem("jobbridge_job_id");
  localStorage.removeItem("jobbridge_active_job");
}