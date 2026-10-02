import { useEffect, useState } from "react";
import { Activity, BriefcaseBusiness, Database, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { api, type AdminOverview } from "../lib/api";

const metrics = [
  ["users_count", "Registered users", Users],
  ["candidates_count", "Candidates", ShieldCheck],
  ["employers_count", "Employers", BriefcaseBusiness],
  ["jobs_count", "Job postings", Database],
  ["match_results_count", "Match records", Activity],
] as const;

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setLoading(false); setError("Sign in again to view administration."); return; }
    setError(null); setLoading(true);
    void api.adminOverview(token).then((data) => { if (active) setOverview(data); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  return <main className="studio-page">
    <div className="page-heading"><div><p className="eyebrow">Administration</p><h1>The bigger picture.</h1><p>Accounts, opportunities and matching activity.</p></div><button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh overview"}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <section className="admin-stats" aria-label="Platform totals" aria-busy={loading}>{metrics.map(([key, label, Icon]) => <div key={key}><Icon size={19} /><span>{label}</span><strong>{loading ? "..." : overview?.[key] ?? "—"}</strong></div>)}</section>
    <section className="data-section"><h2 className="section-heading"><Users size={18} />Recent accounts</h2><div className="data-table-wrap"><table className="data-table"><thead><tr><th scope="col">Email address</th><th scope="col">Account type</th></tr></thead><tbody>{overview?.recent_users.map((user) => <tr key={user.user_id}><td>{user.email}</td><td><span className="skill-tags m-0"><span>{user.role}</span></span></td></tr>)}{!overview?.recent_users.length && <tr><td colSpan={2}>{loading ? "Loading accounts..." : error ? "Accounts unavailable" : "No accounts yet"}</td></tr>}</tbody></table></div></section>
    <section className="data-section"><h2 className="section-heading"><BriefcaseBusiness size={18} />Recent opportunities</h2><div className="data-table-wrap"><table className="data-table"><thead><tr><th scope="col">Role</th><th scope="col">Location</th><th scope="col">Skills</th><th scope="col">Status</th></tr></thead><tbody>{overview?.recent_jobs.map((job) => <tr key={job.job_id}><td>{job.title}</td><td>{job.location || "Not specified"}</td><td>{job.required_skills?.length ?? 0}</td><td><span className="text-spectral-emerald">{job.status}</span></td></tr>)}{!overview?.recent_jobs.length && <tr><td colSpan={4}>{loading ? "Loading opportunities..." : error ? "Opportunities unavailable" : "No job postings yet"}</td></tr>}</tbody></table></div></section>
  </main>;
}