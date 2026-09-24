import { useEffect, useState } from "react";
import { Activity, BriefcaseBusiness, Database, ShieldCheck, Users } from "lucide-react";
import { PageTitle } from "../components/PageTitle";
import { api, type AdminOverview } from "../lib/api";

const metrics = [
  ["users_count", "Registered users", Users],
  ["candidates_count", "Candidate profiles", ShieldCheck],
  ["employers_count", "Employer profiles", BriefcaseBusiness],
  ["jobs_count", "Job postings", Database],
  ["match_results_count", "Evaluated matches", Activity],
] as const;

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const token = localStorage.getItem("jobbridge_token");
    if (!token) return;
    void api.adminOverview(token).then(setOverview).catch((reason: Error) => setError(reason.message));
  }, []);

  return <main className="mx-auto max-w-[1500px] space-y-6 px-5 py-6 lg:px-8"><PageTitle eyebrow="Administration" title="System activity and placement oversight." detail="Review account growth, employer activity, job volume, and completed match evaluations from one protected dashboard." />{error && <p className="rounded-xl border border-spectral-coral/35 bg-spectral-coral/10 px-4 py-3 text-sm text-spectral-coral">{error}</p>}<section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{metrics.map(([key, label, Icon]) => <div key={key} className="glass-panel rounded-2xl p-5"><Icon className="h-4 w-4 text-spectral-emerald" /><p className="mt-5 text-xs text-white/45">{label}</p><strong className="mt-2 block font-mono text-3xl text-white">{overview?.[key] ?? "-"}</strong></div>)}</section><section className="grid gap-6 xl:grid-cols-2"><div className="glass-panel rounded-2xl p-5"><h2 className="text-sm font-semibold">Recent users</h2><div className="mt-4 space-y-3">{overview?.recent_users.map((user) => <div key={user.user_id} className="flex items-center justify-between border-b border-white/5 pb-3 text-sm"><span className="truncate text-white/70">{user.email}</span><span className="font-mono text-xs uppercase text-spectral-emerald">{user.role}</span></div>) ?? <p className="text-sm text-white/40">Loading activity...</p>}</div></div><div className="glass-panel rounded-2xl p-5"><h2 className="text-sm font-semibold">Recent job postings</h2><div className="mt-4 space-y-3">{overview?.recent_jobs.map((job) => <div key={job.job_id} className="border-b border-white/5 pb-3"><div className="flex justify-between gap-3 text-sm"><strong>{job.title}</strong><span className="font-mono text-xs uppercase text-spectral-amber">{job.status}</span></div><p className="mt-1 text-xs text-white/40">{job.location || "Location flexible"} · {job.required_skills?.length ?? 0} required skills</p></div>) ?? <p className="text-sm text-white/40">Loading activity...</p>}</div></div></section></main>;
}