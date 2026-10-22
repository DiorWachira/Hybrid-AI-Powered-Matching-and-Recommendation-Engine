import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, AlertTriangle, ArrowRight, BadgeCheck, BriefcaseBusiness, CheckCircle2, Database, GitBranch, KeyRound, Network, RefreshCw, ShieldCheck, UserX, Users } from "lucide-react";
import { api, type AdminOverview, type AdminUserFilters, type ApiHealth, type OversightSummary, type UserRole } from "../lib/api";
import { OntologyEditor } from "../components/OntologyEditor";
import { AdminAccounts } from "../components/AdminAccounts";
import { AdminActivityLog } from "../components/AdminActivityLog";
import { HiringFunnel, Sparkline } from "../components/Insights";

const panels = [
  { id: "accounts", label: "Accounts", icon: Users },
  { id: "activity", label: "Activity log", icon: Activity },
  { id: "ontology", label: "Skill ontology", icon: Network },
] as const;
type Panel = typeof panels[number]["id"];
const modelLabels = { ready: "Ready", loading: "Loading", not_loaded: "Loads on first use" } as const;

type Attention = { key: string; tone: "warn" | "info"; icon: ReactNode; text: string; action: string; to: string };

export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const panel: Panel = panels.find((item) => item.id === params.get("panel"))?.id ?? "accounts";
  const accountFilters = useMemo<AdminUserFilters>(() => ({
    search: params.get("q") ?? "",
    role: (params.get("role") ?? "") as UserRole | "",
    status: (params.get("status") ?? "") as AdminUserFilters["status"],
  }), [params]);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [oversight, setOversight] = useState<OversightSummary | null>(null);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setLoading(false); setError("Sign in again to view administration."); return; }
    setError(null); setLoading(true);
    // The oversight summary is supplementary: the overview still renders if it fails.
    void api.oversightSummary(token).then((data) => { if (active) setOversight(data); }).catch(() => { if (active) setOversight(null); });
    void Promise.all([api.adminOverview(token), api.health()]).then(([data, readiness]) => { if (active) { setOverview(data); setHealth(readiness); setUpdatedAt(new Date()); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  const showPanel = (id: Panel, extra: Record<string, string> = {}) => setParams({ panel: id, ...extra });
  const trend = overview?.daily_activity ?? [];
  const sum = (key: "signups" | "applications" | "hires") => trend.reduce((total, day) => total + day[key], 0);
  const hired = overview?.application_status_counts.hired ?? 0;
  const mfaShare = overview?.users_count ? Math.round(overview.mfa_enabled_count / overview.users_count * 100) : 0;
  const servicesDown = health ? [health.database.postgres !== "ok" && "PostgreSQL", health.database.neo4j !== "ok" && "Neo4j"].filter(Boolean) as string[] : [];

  const attention: Attention[] = [];
  if (servicesDown.length) attention.push({ key: "services", tone: "warn", icon: <Database size={16} />, text: `${servicesDown.join(" and ")} ${servicesDown.length > 1 ? "are" : "is"} unavailable`, action: "Check status", to: "#platform-health" });
  if (oversight?.attention_jobs) attention.push({ key: "roles", tone: "warn", icon: <AlertTriangle size={16} />, text: `${oversight.attention_jobs} open ${oversight.attention_jobs === 1 ? "role needs" : "roles need"} review`, action: "Review roles", to: "/admin/recruiters?attention=1" });
  if (overview?.suspended_users_count) attention.push({ key: "suspended", tone: "info", icon: <UserX size={16} />, text: `${overview.suspended_users_count} suspended ${overview.suspended_users_count === 1 ? "account" : "accounts"}`, action: "Show them", to: "?panel=accounts&status=suspended" });
  if (overview?.pending_graph_events) attention.push({ key: "graph", tone: "info", icon: <GitBranch size={16} />, text: `${overview.pending_graph_events} graph ${overview.pending_graph_events === 1 ? "update is" : "updates are"} waiting to sync`, action: "See health", to: "#platform-health" });

  const kpis = [
    { label: "Accounts", value: overview?.users_count, detail: overview ? `${overview.candidates_count} candidates · ${overview.employers_count} employers` : "", trend: trend.map((day) => day.signups), trendLabel: "New accounts per day", delta: sum("signups"), deltaLabel: "new" },
    { label: "Job postings", value: overview?.jobs_count, detail: oversight ? `${oversight.jobs_open} open · ${oversight.jobs_closed} closed` : "", trend: [], trendLabel: "", delta: null, deltaLabel: "" },
    { label: "Applications", value: overview?.applications_count, detail: `${overview?.match_results_count ?? "—"} match records`, trend: trend.map((day) => day.applications), trendLabel: "Applications per day", delta: sum("applications"), deltaLabel: "new" },
    { label: "Hires", value: hired, detail: overview?.applications_count ? `${Math.round(hired / overview.applications_count * 100)}% of applications` : "No applications yet", trend: trend.map((day) => day.hires), trendLabel: "Hires per day", delta: sum("hires"), deltaLabel: "hired" },
  ];

  return <main className="studio-page admin-page">
    <div className="page-heading"><div><p className="eyebrow">Administration</p><h1>The bigger picture.</h1><p>What needs you, how hiring is moving, and every account in one place.</p></div><div className="admin-heading-actions">{updatedAt && <span className="admin-updated">Updated {updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}<button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh"}</button></div></div>
    {error && <p className="notice error" role="alert">{error}</p>}

    <section className={`attention-strip ${attention.length ? "" : "is-clear"}`} aria-label="Needs your attention" aria-busy={loading}>
      {attention.length ? attention.map((item) => <div key={item.key} className={`attention-item ${item.tone}`}>{item.icon}<span>{item.text}</span>{item.to.startsWith("/") ? <Link to={item.to}>{item.action}<ArrowRight size={14} /></Link> : <a href={item.to} onClick={(event) => { if (item.to.startsWith("?")) { event.preventDefault(); setParams(new URLSearchParams(item.to.slice(1))); document.getElementById("admin-workspace")?.scrollIntoView({ behavior: "smooth" }); } }}>{item.action}<ArrowRight size={14} /></a>}</div>)
        : <div className="attention-item good"><CheckCircle2 size={16} /><span>{loading ? "Checking the platform..." : "All clear. Nothing needs your attention right now."}</span></div>}
    </section>

    <section className="kpi-grid" aria-label="Platform totals" aria-busy={loading}>
      {kpis.map((item) => <article key={item.label} className="kpi-tile">
        <span>{item.label}</span>
        <strong>{loading && !overview ? "..." : item.value ?? "—"}</strong>
        <small>{item.detail}</small>
        {item.trend.length > 1 && <div className="kpi-trend"><Sparkline values={item.trend} label={item.trendLabel} /><em>+{item.delta} {item.deltaLabel} / {item.trend.length}d</em></div>}
        {item.label === "Job postings" && <Link className="kpi-link" to="/admin/recruiters">Recruiter oversight<ArrowRight size={13} /></Link>}
      </article>)}
    </section>

    <div className="admin-insights">
      <section className="insight-card" aria-labelledby="funnel-heading">
        <div className="insight-heading"><h2 id="funnel-heading" className="section-heading"><BriefcaseBusiness size={18} />Hiring funnel</h2><Link className="text-button" to="/admin/recruiters">By recruiter<ArrowRight size={14} /></Link></div>
        {overview ? <HiringFunnel counts={overview.application_status_counts} /> : <p className="admin-row-note">{loading ? "Loading..." : "Unavailable"}</p>}
      </section>
      <section id="platform-health" className="insight-card" aria-labelledby="health-heading">
        <div className="insight-heading"><h2 id="health-heading" className="section-heading"><ShieldCheck size={18} />Platform health</h2></div>
        <ul className="health-list">
          <li><i className={health?.database.postgres === "ok" ? "ok" : loading ? "" : "bad"} />PostgreSQL<span>{loading ? "Checking" : health?.database.postgres === "ok" ? "Online" : "Unavailable"}</span></li>
          <li><i className={health?.database.neo4j === "ok" ? "ok" : loading ? "" : "bad"} />Neo4j skill graph<span>{loading ? "Checking" : health?.database.neo4j === "ok" ? "Online" : "Unavailable"}</span></li>
          <li><i className={health?.matching_model === "ready" ? "ok" : health?.matching_model ? "wait" : ""} />Matching model<span>{loading ? "Checking" : health?.matching_model ? modelLabels[health.matching_model] : "Unavailable"}</span></li>
          <li><i className={overview?.pending_graph_events ? "wait" : "ok"} />Graph sync queue<span>{overview ? overview.pending_graph_events ? `${overview.pending_graph_events} pending` : "Up to date" : "—"}</span></li>
        </ul>
        <div className="mfa-adoption"><div><KeyRound size={15} /><span>Two-step verification</span><strong>{overview ? `${overview.mfa_enabled_count} of ${overview.users_count}` : "—"}</strong></div><div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={mfaShare} aria-label="Accounts with two-step verification"><i style={{ width: `${mfaShare}%` }} /></div><small>{mfaShare}% of accounts protected{overview?.suspended_users_count ? ` · ${overview.suspended_users_count} suspended` : ""}</small></div>
        <Link className="text-button" to="/admin/simulation"><BadgeCheck size={15} />Run a matching simulation</Link>
      </section>
    </div>

    <section id="admin-workspace" className="admin-workspace" aria-label="Administration workspace">
      <div className="tab-bar" role="tablist" aria-label="Administration views">
        {panels.map(({ id, label, icon: Icon }, index) => <button key={id} role="tab" id={`admin-tab-${id}`} tabIndex={panel === id ? 0 : -1} aria-selected={panel === id} aria-controls="admin-panel" onClick={() => showPanel(id)} onKeyDown={(event) => {
          const next = event.key === "ArrowRight" ? (index + 1) % panels.length : event.key === "ArrowLeft" ? (index + panels.length - 1) % panels.length : null;
          if (next === null) return;
          event.preventDefault(); showPanel(panels[next].id);
          event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`#admin-tab-${panels[next].id}`)?.focus();
        }}><Icon size={15} />{label}{id === "accounts" && overview ? <span className="tab-count">{overview.users_count}</span> : null}</button>)}
      </div>
      <div id="admin-panel" role="tabpanel" aria-labelledby={`admin-tab-${panel}`}>
        {panel === "accounts" ? <AdminAccounts initialFilters={accountFilters} onChanged={() => setRefresh((value) => value + 1)} /> : panel === "activity" ? <AdminActivityLog trend={trend} /> : <OntologyEditor />}
      </div>
    </section>
  </main>;
}
