import { useEffect, useRef, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, BriefcaseBusiness, Copy, Database, KeyRound, RefreshCw, Search, ShieldCheck, UserCheck, Users, X } from "lucide-react";
import { api, type AdminOverview, type AdminUser, type ApiHealth } from "../lib/api";
import { OntologyEditor } from "../components/OntologyEditor";

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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [accounts, setAccounts] = useState<AdminUser[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [recoverySearch, setRecoverySearch] = useState("");
  const [recoveryQuery, setRecoveryQuery] = useState("");
  const [recoveryOffset, setRecoveryOffset] = useState(0);
  const [recoveryRefresh, setRecoveryRefresh] = useState(0);
  const [recoveryAccounts, setRecoveryAccounts] = useState<AdminUser[]>([]);
  const [recoveryLoading, setRecoveryLoading] = useState(true);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
    const [resetUser, setResetUser] = useState<AdminUser | null>(null);
    const [confirmationPassword, setConfirmationPassword] = useState("");
    const [resetLink, setResetLink] = useState("");
    const [resetError, setResetError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const resetDialog = useRef<HTMLDialogElement>(null);
    useEffect(() => { if (resetUser) resetDialog.current?.showModal(); else resetDialog.current?.close(); }, [resetUser]);
    const closeReset = () => { setResetUser(null); setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); };
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
    void Promise.all([api.adminOverview(token), api.health()]).then(([data, readiness]) => { if (active) { setOverview(data); setHealth(readiness); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setAccountsLoading(false); return; }
    setAccountsLoading(true);
    void api.adminUsers(token, query, offset).then((data) => { if (active) setAccounts(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setAccounts([]); } })
      .finally(() => { if (active) setAccountsLoading(false); });
    return () => { active = false; };
  }, [query, offset, refresh]);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    setRecoveryError(null);
    if (!token) { setRecoveryLoading(false); setRecoveryError("Sign in again to view accounts."); return; }
    setRecoveryLoading(true);
    void api.adminUsers(token, recoveryQuery, recoveryOffset)
      .then((data) => { if (active) setRecoveryAccounts(data); })
      .catch((reason: Error) => { if (active) { setRecoveryError(reason.message); setRecoveryAccounts([]); } })
      .finally(() => { if (active) setRecoveryLoading(false); });
    return () => { active = false; };
  }, [recoveryQuery, recoveryOffset, recoveryRefresh, refresh]);

  const openRecovery = (account: AdminUser) => {
    setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); setResetUser(account);
  };

  const reactivateRecoveryAccount = async (account: AdminUser) => {
    if (!window.confirm(`Reactivate ${account.display_name} (${account.email})? This restores account access.`)) return;
    setBusy(account.user_id); setRecoveryError(null);
    try {
      const updated = await api.setAccountActive(localStorage.getItem("jobbridge_token") ?? "", account.user_id, true);
      setRecoveryAccounts((items) => items.map((item) => item.user_id === updated.user_id ? updated : item));
      setRefresh((value) => value + 1);
    } catch (reason) { setRecoveryError(reason instanceof Error ? reason.message : "Account could not be reactivated."); }
    finally { setBusy(null); }
  };

  const changeAccount = async (account: AdminUser) => {
    if (!window.confirm(`${account.is_active ? "Suspend" : "Reactivate"} ${account.display_name}?`)) return;
    setBusy(account.user_id); setError(null);
    try { await api.setAccountActive(localStorage.getItem("jobbridge_token") ?? "", account.user_id, !account.is_active); setRefresh((value) => value + 1); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Account update failed."); }
    finally { setBusy(null); }
  };

  const changeJob = async (jobId: string, status: "open" | "closed") => {
    if (!window.confirm(`Set this job to ${status}?`)) return;
    setBusy(jobId); setError(null);
    try { await api.setJobStatus(localStorage.getItem("jobbridge_token") ?? "", jobId, status); setRefresh((value) => value + 1); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Job update failed."); }
    finally { setBusy(null); }
  };

  return <main className="studio-page">
    <div className="page-heading"><div><p className="eyebrow">Administration</p><h1>The bigger picture.</h1><p>Accounts, opportunities and matching activity.</p></div><button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh overview"}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <dialog className="admin-dialog" ref={resetDialog} onCancel={(event) => { if (busy !== null) event.preventDefault(); else closeReset(); }} aria-labelledby="reset-title">
      <div className="page-heading"><h2 id="reset-title">Password recovery</h2><button className="icon-button" aria-label="Close password recovery" title="Close" onClick={closeReset} disabled={busy !== null}><X size={18} /></button></div>
      <p>{resetUser?.display_name}</p>
      <p className="recovery-email">{resetUser?.email}</p>
      {resetError && <p className="notice error" role="alert">{resetError}</p>}
      {resetLink ? <div><label className="studio-field">Reset link (expires in 15 minutes)<input value={resetLink} readOnly autoComplete="off" /></label><button className="secondary-button" onClick={() => { void navigator.clipboard.writeText(resetLink).then(() => setCopied(true)).catch(() => setResetError("Could not copy the link. Select the field to copy it.")); }}><Copy size={16} />{copied ? "Copied" : "Copy reset link"}</button></div> : <form onSubmit={issueReset}><label className="studio-field">Your administrator password<input type="password" autoComplete="current-password" value={confirmationPassword} onChange={(event) => setConfirmationPassword(event.target.value)} required /></label><button className="primary-button" disabled={busy !== null}><KeyRound size={16} />Issue reset link</button></form>}
    </dialog>
    <section className="data-section" aria-labelledby="account-recovery-heading">
      <h2 id="account-recovery-heading" className="section-heading"><KeyRound size={18} />Account recovery</h2>
      <form className="admin-search" role="search" aria-label="Account recovery search" onSubmit={(event) => { event.preventDefault(); setRecoveryOffset(0); setRecoveryQuery(recoverySearch.trim()); setRecoveryRefresh((value) => value + 1); }}>
        <label className="studio-field">Recovery account name, company or email<input type="search" value={recoverySearch} maxLength={120} onChange={(event) => setRecoverySearch(event.target.value)} /></label>
        <button className="secondary-button" type="submit" disabled={recoveryLoading}><Search size={16} />Find account</button>
      </form>
      {recoveryError && <p className="notice error" role="alert">{recoveryError}</p>}
      <div className="recovery-results" aria-busy={recoveryLoading}>
        {recoveryLoading ? <p role="status">Loading recovery accounts...</p> : recoveryAccounts.length ? recoveryAccounts.map((account) => <div className="recovery-account" key={account.user_id}>
          <div className="recovery-identity"><strong>{account.display_name}</strong><span className="recovery-email">{account.email}</span>{account.company_name && <span>{account.company_name}</span>}<span>{account.role} / {account.is_active ? "Active" : "Suspended"}</span></div>
          <div className="recovery-action">{account.role === "admin" ? <span>Administrator recovery restricted</span> : account.is_active ? <button className="secondary-button" disabled={busy !== null} onClick={() => openRecovery(account)} aria-label={`Reset password for ${account.email}`}><KeyRound size={16} />Reset password</button> : <button className="secondary-button" disabled={busy !== null} onClick={() => void reactivateRecoveryAccount(account)} aria-label={`Reactivate ${account.email}`}><UserCheck size={16} />Reactivate</button>}</div>
        </div>) : <p role="status">{recoveryError ? "Recovery accounts unavailable" : "No matching accounts"}</p>}
      </div>
      <nav className="admin-pagination" aria-label="Recovery results pagination"><button className="icon-button" title="Previous recovery accounts" aria-label="Previous recovery accounts" disabled={recoveryOffset === 0 || recoveryLoading || busy !== null} onClick={() => setRecoveryOffset((value) => Math.max(0, value - 25))}><ArrowLeft size={18} /></button><span>Page {Math.floor(recoveryOffset / 25) + 1}</span><button className="icon-button" title="Next recovery accounts" aria-label="Next recovery accounts" disabled={recoveryAccounts.length < 25 || recoveryLoading || busy !== null} onClick={() => setRecoveryOffset((value) => value + 25)}><ArrowRight size={18} /></button></nav>
    </section>
    <section className="admin-stats" aria-label="Platform totals" aria-busy={loading}>{metrics.map(([key, label, Icon]) => <div key={key}><Icon size={19} /><span>{label}</span><strong>{loading ? "..." : overview?.[key] ?? "—"}</strong></div>)}</section>
    <section className="data-section"><h2 className="section-heading"><Database size={18} />System health</h2><div className="skill-tags"><span>PostgreSQL: {loading ? "Checking" : health?.database.postgres ?? "Unavailable"}</span><span>Neo4j: {loading ? "Checking" : health?.database.neo4j ?? "Unavailable"}</span></div></section>
    <section className="data-section"><h2 className="section-heading"><Users size={18} />Accounts</h2>
      <form className="admin-search" onSubmit={(event) => { event.preventDefault(); setOffset(0); setQuery(search.trim()); }}><label className="studio-field">Name, company or email<input value={search} onChange={(event) => setSearch(event.target.value)} maxLength={120} type="search" /></label><button className="secondary-button" type="submit"><Search size={16} />Search</button></form>
      <div className="data-table-wrap" aria-busy={accountsLoading}><table className="data-table"><thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Role</th><th scope="col">Data</th><th scope="col">Active</th></tr></thead><tbody>{accounts.map((account) => <tr key={account.user_id}><td><strong>{account.display_name}</strong>{account.company_name && <div>{account.company_name}</div>}</td><td>{account.email}</td><td>{account.role}</td><td>{account.is_demo ? "Fictional demo" : "Registered"}</td><td><input type="checkbox" role="switch" checked={account.is_active} aria-label={`Account active for ${account.display_name}`} disabled={account.role === "admin" || busy !== null || accountsLoading} onChange={() => void changeAccount(account)} /></td></tr>)}{!accounts.length && <tr><td colSpan={5}>{accountsLoading ? "Loading accounts..." : "No accounts found"}</td></tr>}</tbody></table></div>
      <div className="admin-pagination"><button className="icon-button" title="Previous accounts" aria-label="Previous accounts" disabled={offset === 0 || accountsLoading} onClick={() => setOffset((value) => Math.max(0, value - 25))}><ArrowLeft size={18} /></button><span>Page {Math.floor(offset / 25) + 1}</span><button className="icon-button" title="Next accounts" aria-label="Next accounts" disabled={accounts.length < 25 || accountsLoading} onClick={() => setOffset((value) => value + 25)}><ArrowRight size={18} /></button></div>
    </section>
    <section className="data-section"><h2 className="section-heading"><BriefcaseBusiness size={18} />Recent opportunities</h2><div className="data-table-wrap"><table className="data-table"><thead><tr><th scope="col">Role</th><th scope="col">Location</th><th scope="col">Skills</th><th scope="col">Status</th></tr></thead><tbody>{overview?.recent_jobs.map((job) => <tr key={job.job_id}><td>{job.title}</td><td>{job.location || "Not specified"}</td><td>{job.required_skills?.length ?? 0}</td><td><select aria-label={`Status for ${job.title}`} value={job.status} disabled={busy !== null || loading} onChange={(event) => void changeJob(job.job_id, event.target.value as "open" | "closed")}><option value="open">Open</option><option value="closed">Closed</option></select></td></tr>)}{!overview?.recent_jobs.length && <tr><td colSpan={4}>{loading ? "Loading opportunities..." : error ? "Opportunities unavailable" : "No job postings yet"}</td></tr>}</tbody></table></div></section>
    <section className="data-section"><h2 className="section-heading"><Activity size={18} />Recent activity</h2><div className="data-table-wrap"><table className="data-table"><thead><tr><th scope="col">Time</th><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Resource</th></tr></thead><tbody>{overview?.recent_activity.map((event) => <tr key={event.event_id}><td>{new Date(event.created_at).toLocaleString()}</td><td>{event.action.replaceAll(".", " / ").replaceAll("_", " ")}</td><td title={event.actor_user_id ?? "System"}>{event.actor_user_id?.slice(0, 8) ?? "System"}</td><td title={event.resource_id ?? undefined}>{event.resource_type} {event.resource_id?.slice(0, 8)}</td></tr>)}{!overview?.recent_activity.length && <tr><td colSpan={4}>{loading ? "Loading activity..." : "No recorded activity yet"}</td></tr>}</tbody></table></div></section>
    <OntologyEditor />
  </main>;
}