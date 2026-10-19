import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, ArrowRight, BriefcaseBusiness, Copy, Database, KeyRound, RefreshCw, Search, ShieldCheck, UserCheck, UserRoundSearch, UserX, Users, X } from "lucide-react";
import { api, type AdminOverview, type AdminUser, type ApiHealth, type OversightSummary } from "../lib/api";
import { OntologyEditor } from "../components/OntologyEditor";
import { ADMIN_PAGE_SIZE, ListPagination } from "../components/ListPagination";

const metrics = [
  ["users_count", "Registered users", Users],
  ["candidates_count", "Candidates", ShieldCheck],
  ["employers_count", "Employers", BriefcaseBusiness],
  ["jobs_count", "Job postings", Database],
  ["match_results_count", "Match records", Activity],
  ["applications_count", "Applications", BriefcaseBusiness],
  ["pending_graph_events", "Pending graph updates", Database],
  ["suspended_users_count", "Suspended accounts", ShieldCheck],
] as const;

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [oversight, setOversight] = useState<OversightSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [accounts, setAccounts] = useState<AdminUser[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [activityOffset, setActivityOffset] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [resetUser, setResetUser] = useState<AdminUser | null>(null);
  const [confirmationPassword, setConfirmationPassword] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const resetDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (resetUser) resetDialog.current?.showModal(); else resetDialog.current?.close(); }, [resetUser]);
  const closeReset = () => { setResetUser(null); setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); };
  const openReset = (account: AdminUser) => { setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); setResetUser(account); };
  const issueReset = async (event: React.FormEvent) => {
    event.preventDefault(); if (!resetUser) return;
    setBusy(resetUser.user_id); setResetError(null);
    try {
      const result = await api.issuePasswordReset(localStorage.getItem("jobbridge_token") ?? "", resetUser.user_id, confirmationPassword);
      setResetLink(`${location.origin}/auth#reset=${encodeURIComponent(result.token)}`);
    } catch (reason) { setResetError(reason instanceof Error ? reason.message : "Reset could not be issued."); }
    finally { setConfirmationPassword(""); setBusy(null); }
  };

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setLoading(false); setError("Sign in again to view administration."); return; }
    setError(null); setLoading(true);
    // The oversight summary is supplementary: the overview still renders if it fails.
    void api.oversightSummary(token).then((data) => { if (active) setOversight(data); }).catch(() => { if (active) setOversight(null); });
    void Promise.all([api.adminOverview(token), api.health()]).then(([data, readiness]) => { if (active) { setOverview(data); setHealth(readiness); setActivityOffset((value) => Math.min(value, Math.max(0, Math.ceil(data.recent_activity.length / ADMIN_PAGE_SIZE) - 1) * ADMIN_PAGE_SIZE)); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    setAccountsError(null);
    if (!token) { setAccountsLoading(false); setAccountsError("Sign in again to view accounts."); return; }
    setAccountsLoading(true);
    void api.adminUsers(token, query, offset).then((data) => { if (active) setAccounts(data); })
      .catch((reason: Error) => { if (active) { setAccountsError(reason.message); setAccounts([]); } })
      .finally(() => { if (active) setAccountsLoading(false); });
    return () => { active = false; };
  }, [query, offset, refresh]);

  const changeAccount = async (account: AdminUser) => {
    const action = account.is_active ? "Suspend" : "Reactivate";
    const consequence = account.is_active ? "They will be signed out and blocked from signing in." : "This restores account access.";
    if (!window.confirm(`${action} ${account.display_name} (${account.email})? ${consequence}`)) return;
    setBusy(account.user_id); setAccountsError(null);
    try {
      const updated = await api.setAccountActive(localStorage.getItem("jobbridge_token") ?? "", account.user_id, !account.is_active);
      setAccounts((items) => items.map((item) => item.user_id === updated.user_id ? updated : item));
      setRefresh((value) => value + 1);
    } catch (reason) { setAccountsError(reason instanceof Error ? reason.message : "Account update failed."); }
    finally { setBusy(null); }
  };

  return <main className="studio-page admin-page">
    <div className="page-heading"><div><p className="eyebrow">Administration</p><h1>The bigger picture.</h1><p>Accounts, opportunities and matching activity.</p></div><button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh overview"}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <section className="admin-stats" aria-label="Platform totals" aria-busy={loading}>{metrics.map(([key, label, Icon]) => <div key={key}><Icon size={19} /><span>{label}</span><strong>{loading ? "..." : overview?.[key] ?? "—"}</strong></div>)}</section>
    <section className="data-section"><h2 className="section-heading"><Database size={18} />System health</h2><div className="skill-tags"><span>PostgreSQL: {loading ? "Checking" : health?.database.postgres ?? "Unavailable"}</span><span>Neo4j: {loading ? "Checking" : health?.database.neo4j ?? "Unavailable"}</span></div></section>
    <section className="data-section admin-oversight-card" aria-labelledby="oversight-card-heading">
      <div><h2 id="oversight-card-heading" className="section-heading"><UserRoundSearch size={18} />Recruiter oversight</h2>
        <p>{oversight ? `${oversight.jobs_open} open and ${oversight.jobs_closed} closed postings from ${oversight.recruiters_count} recruiters.` : "Postings, applicants and hiring activity for every recruiter."}</p>
        {oversight && oversight.attention_jobs > 0 && <p className="admin-oversight-alert"><AlertTriangle size={15} />{oversight.attention_jobs} open {oversight.attention_jobs === 1 ? "role needs" : "roles need"} attention: {oversight.stale_open_jobs} without applicants after {oversight.stale_after_days} days, {oversight.suspended_open_jobs} from suspended recruiters.</p>}
      </div>
      <div className="admin-oversight-links">{oversight && oversight.attention_jobs > 0 && <Link className="secondary-button" to="/admin/recruiters?attention=1"><AlertTriangle size={16} />Review flagged roles</Link>}<Link className="primary-button" to="/admin/recruiters">Open oversight<ArrowRight size={16} /></Link></div>
    </section>
    <dialog className="admin-dialog" ref={resetDialog} onCancel={(event) => { if (busy !== null) event.preventDefault(); else closeReset(); }} aria-labelledby="reset-title">
      <div className="page-heading"><h2 id="reset-title">Password recovery</h2><button className="icon-button" aria-label="Close password recovery" title="Close" onClick={closeReset} disabled={busy !== null}><X size={18} /></button></div>
      <p>{resetUser?.display_name}</p>
      <p className="recovery-email">{resetUser?.email}</p>
      {resetError && <p className="notice error" role="alert">{resetError}</p>}
      {resetLink ? <div><label className="studio-field">Reset link (expires in 15 minutes)<input value={resetLink} readOnly autoComplete="off" /></label><button className="secondary-button" onClick={() => { void navigator.clipboard.writeText(resetLink).then(() => setCopied(true)).catch(() => setResetError("Could not copy the link. Select the field to copy it.")); }}><Copy size={16} />{copied ? "Copied" : "Copy reset link"}</button></div> : <form onSubmit={issueReset}><label className="studio-field">Your administrator password<input type="password" autoComplete="current-password" value={confirmationPassword} onChange={(event) => setConfirmationPassword(event.target.value)} required /></label><button className="primary-button" disabled={busy !== null}><KeyRound size={16} />Issue reset link</button></form>}
    </dialog>
    <section className="data-section" aria-labelledby="accounts-heading"><h2 id="accounts-heading" className="section-heading"><Users size={18} />Accounts and recovery</h2>
      <form className="admin-search" role="search" aria-label="Account search" onSubmit={(event) => { event.preventDefault(); setOffset(0); setQuery(search.trim()); setRefresh((value) => value + 1); }}><label className="studio-field">Name, company or email<input value={search} onChange={(event) => setSearch(event.target.value)} maxLength={120} type="search" /></label><button className="secondary-button" type="submit" disabled={accountsLoading}><Search size={16} />Search</button></form>
      {accountsError && <p className="notice error" role="alert">{accountsError}</p>}
      <div className="data-table-wrap" aria-busy={accountsLoading}><table className="data-table"><thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Role</th><th scope="col">Data</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead><tbody>
        {accounts.slice(0, ADMIN_PAGE_SIZE).map((account) => <tr key={account.user_id}>
          <td><strong>{account.display_name}</strong>{account.company_name && <div>{account.company_name}</div>}</td><td>{account.email}</td><td>{account.role}</td><td>{account.is_demo ? "Fictional demo" : "Registered"}</td>
          <td><span className={`admin-job-status ${account.is_active ? "open" : "closed"}`}>{account.is_active ? "Active" : "Suspended"}</span></td>
          <td>{account.role === "admin" ? <span className="admin-row-note">Managed outside the dashboard</span> : <div className="admin-row-actions">
            {account.is_active && <button className="text-button" disabled={busy !== null} onClick={() => openReset(account)} aria-label={`Reset password for ${account.email}`}><KeyRound size={15} />Reset password</button>}
            <button className="text-button" disabled={busy !== null || accountsLoading} onClick={() => void changeAccount(account)} aria-label={`${account.is_active ? "Suspend" : "Reactivate"} ${account.email}`}>{account.is_active ? <><UserX size={15} />Suspend</> : <><UserCheck size={15} />Reactivate</>}</button>
          </div>}</td>
        </tr>)}
        {!accounts.length && <tr><td colSpan={6}>{accountsLoading ? "Loading accounts..." : accountsError ? "Accounts unavailable" : "No accounts found"}</td></tr>}
      </tbody></table></div>
      <ListPagination label="accounts" offset={offset} hasNext={accounts.length > ADMIN_PAGE_SIZE} disabled={accountsLoading || busy !== null} onChange={setOffset} />
    </section>
    <section className="data-section" aria-label="Recent activity"><h2 className="section-heading"><Activity size={18} />Recent activity</h2><div className="data-table-wrap"><table className="data-table"><thead><tr><th scope="col">Time</th><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Resource</th></tr></thead><tbody>{overview?.recent_activity.slice(activityOffset, activityOffset + ADMIN_PAGE_SIZE).map((event) => <tr key={event.event_id}><td>{new Date(event.created_at).toLocaleString()}</td><td>{event.action.replaceAll(".", " / ").replaceAll("_", " ")}</td><td title={event.actor_user_id ?? "System"}>{event.actor_email ?? event.actor_user_id?.slice(0, 8) ?? "System"}</td><td title={event.resource_id ?? undefined}>{event.resource_type} {event.resource_id?.slice(0, 8)}</td></tr>)}{!overview?.recent_activity.length && <tr><td colSpan={4}>{loading ? "Loading activity..." : "No recorded activity yet"}</td></tr>}</tbody></table></div><ListPagination label="activity" offset={activityOffset} hasNext={(overview?.recent_activity.length ?? 0) > activityOffset + ADMIN_PAGE_SIZE} disabled={loading} onChange={setActivityOffset} /></section>
    <OntologyEditor />
  </main>;
}
