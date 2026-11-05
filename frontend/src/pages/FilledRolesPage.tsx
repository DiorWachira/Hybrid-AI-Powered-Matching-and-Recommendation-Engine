import { useEffect, useState } from "react";
import { BadgeCheck, CircleAlert, RefreshCw, RotateCcw, Target } from "lucide-react";
import { Link } from "react-router-dom";
import { api, type FilledRole } from "../lib/api";

const percent = (score: number | null) => score === null ? "No score" : `${Math.round(Math.max(0, Math.min(1, score)) * 100)}% match`;

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

export function FilledRolesPage() {
  const [roles, setRoles] = useState<FilledRole[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const token = () => localStorage.getItem("jobbridge_token") ?? "";
  useEffect(() => {
    let active = true;
    setError(null);
    void api.filledRoles(token()).then((items) => { if (active) setRoles(items); }).catch((reason: Error) => { if (active) { setError(reason.message); setRoles([]); } });
    return () => { active = false; };
  }, [refresh]);
  const undo = async (role: FilledRole) => {
    if (busy || !window.confirm(`Undo the simulated hire for ${role.title}? Applicants go back to where they were and the posting reopens.`)) return;
    setBusy(role.job_id); setError(null);
    try { await api.undoHiringSimulation(role.job_id, token()); setRefresh((value) => value + 1); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not undo the simulation."); }
    finally { setBusy(null); }
  };
  const hires = (roles ?? []).flatMap((role) => role.hires);
  const real = hires.filter((hire) => !hire.simulated);
  const days = median(real.flatMap((hire) => hire.days_to_fill === null ? [] : [hire.days_to_fill]));
  const tiles: Array<[string, number | string, string]> = [
    ["Roles filled", roles?.length ?? "—", `${hires.length} ${hires.length === 1 ? "person" : "people"} hired`],
    ["Real hires", real.length, "through your own decisions"],
    ["Simulated hires", hires.length - real.length, "demo runs, can be undone"],
    ["Median days to fill", days ?? "—", "real hires only"],
  ];
  return <main className="studio-page">
    <div className="page-heading"><div><p className="eyebrow">Filled roles</p><h1>Every seat that found someone.</h1><p>Roles with a hire, who got the job and how long it took.</p></div><div className="workflow-actions"><button className="secondary-button" disabled={roles === null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Refresh</button></div></div>
    {error && <p className="notice error" role="alert"><CircleAlert size={18} />{error}</p>}
    <div className="kpi-grid recruiter-kpis" aria-label="Filled role summary">{tiles.map(([label, value, detail]) => <article className="kpi-tile" key={label}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>)}</div>
    {roles === null ? <div className="empty-state" role="status"><RefreshCw size={26} className="animate-spin" /><h2>Loading filled roles</h2></div>
      : !roles.length ? <div className="empty-state"><BadgeCheck size={30} /><h2>No roles filled yet.</h2><p>Evaluate a role, take it through the hiring flow or run a simulation, and it appears here.</p><Link to="/matches" className="primary-button"><Target size={16} />Open match analysis</Link></div>
      : <section className="filled-list" aria-label="Filled roles">{roles.map((role) => <article className="filled-row" key={role.job_id} aria-label={role.title}>
        <div className="filled-role"><h2>{role.title}</h2><p>{role.location || "Remote"} / {role.applicants_total} {role.applicants_total === 1 ? "applicant" : "applicants"} / <span className={`admin-job-status ${role.job_status}`}>{role.job_status}</span></p></div>
        <ul className="filled-hires">{role.hires.map((hire) => <li key={hire.application_id}>
          <span className={`hired-stamp ${hire.simulated ? "is-simulated" : ""}`}>{hire.simulated ? "Simulated" : "Hired"}</span>
          <div><strong>{hire.candidate_name}</strong><small>{percent(hire.final_score)} / {new Date(hire.hired_at).toLocaleDateString()}{hire.days_to_fill === null || hire.simulated ? "" : ` / ${hire.days_to_fill} ${hire.days_to_fill === 1 ? "day" : "days"} to fill`}</small></div>
        </li>)}</ul>
        <div className="workflow-actions"><Link className="secondary-button" to={`/matches?job=${role.job_id}`}><Target size={16} />Match analysis</Link>{role.hires.some((hire) => hire.simulated) && <button className="secondary-button" disabled={busy !== null} onClick={() => void undo(role)}><RotateCcw size={16} />Undo simulation</button>}</div>
      </article>)}</section>}
  </main>;
}
