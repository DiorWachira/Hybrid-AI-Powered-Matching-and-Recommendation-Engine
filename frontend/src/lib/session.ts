import type { UserRole } from "./api";

export function getSessionRole(): UserRole | null {
  const token = localStorage.getItem("jobbridge_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as { role?: UserRole };
    return payload.role ?? null;
  } catch {
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem("jobbridge_token");
}