import { useEffect, useRef, useState } from "react";
import { Copy, KeyRound, Search, ShieldOff, UserCheck, UserX, X } from "lucide-react";
import { api, type AdminUser, type AdminUserFilters } from "../lib/api";
import { ListPagination } from "./ListPagination";
import { relativeTime } from "./Insights";

const PAGE_SIZE = 10;
const roleOptions = [["", "All roles"], ["candidate", "Candidates"], ["recruiter", "Recruiters"], ["admin", "Admins"]] as const;
const statusOptions = [["", "Any status"], ["active", "Active"], ["suspended", "Suspended"]] as const;

export function AdminAccounts({ initialFilters, onChanged }: { initialFilters: AdminUserFilters; onChanged: () => void }) {
  const [accounts, setAccounts] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(initialFilters.search);
  const [filters, setFilters] = useState(initialFilters);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [resetUser, setResetUser] = useState<AdminUser | null>(null);
  const [resetKind, setResetKind] = useState<"password" | "mfa">("password");
  const [mfaResetDone, setMfaResetDone] = useState(false);
  const [confirmationPassword, setConfirmationPassword] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const resetDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (resetUser) resetDialog.current?.showModal(); else resetDialog.current?.close(); }, [resetUser]);
  const closeReset = () => { setResetUser(null); setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); setMfaResetDone(false); };
  const openReset = (account: AdminUser, kind: "password" | "mfa" = "password") => { setConfirmationPassword(""); setResetLink(""); setResetError(null); setCopied(false); setMfaResetDone(false); setResetKind(kind); setResetUser(account); };
  const issueReset = async (event: React.FormEvent) => {
    event.preventDefault(); if (!resetUser) return;
    setBusy(resetUser.user_id); setResetError(null);
    try {
      const token = localStorage.getItem("jobbridge_token") ?? "";
      if (resetKind === "mfa") {
        await api.resetAccountMfa(token, resetUser.user_id, confirmationPassword);
        setMfaResetDone(true);
        setAccounts((items) => items.map((item) => item.user_id === resetUser.user_id ? { ...item, mfa_enabled: false } : item));
      } else {
        const result = await api.issuePasswordReset(token, resetUser.user_id, confirmationPassword);
        setResetLink(`${location.origin}/auth#reset=${encodeURIComponent(result.token)}`);
      }
    } catch (reason) { setResetError(reason instanceof Error ? reason.message : "Reset could not be issued."); }
    finally { setConfirmationPassword(""); setBusy(null); }
  };

  // Filters from the command palette or attention strip arrive as new props.
  useEffect(() => { setSearch(initialFilters.search); setFilters(initialFilters); setOffset(0); }, [initialFilters]);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    setError(null);
    if (!token) { setLoading(false); setError("Sign in again to view accounts."); return; }
    setLoading(true);
    void api.adminUsers(token, filters, offset).then((data) => { if (active) setAccounts(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setAccounts([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters, offset, refresh]);

  const changeAccount = async (account: AdminUser) => {
    const action = account.is_active ? "Suspend" : "Reactivate";
    const consequence = account.is_active ? "They will be signed out and blocked from signing in." : "This restores account access.";
    if (!window.confirm(`${action} ${account.display_name} (${account.email})? ${consequence}`)) return;
    setBusy(account.user_id); setError(null);
    try {
      const updated = await api.setAccountActive(localStorage.getItem("jobbridge_token") ?? "", account.user_id, !account.is_active);
      setAccounts((items) => items.map((item) => item.user_id === updated.user_id ? updated : item));
      onChanged();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Account update failed."); }
    finally { setBusy(null); }
  };
  const filter = (next: Partial<AdminUserFilters>) => { setOffset(0); setFilters((current) => ({ ...current, ...next })); };

  return <div className="admin-panel-body">
    <div className="admin-filter-bar">
      <form className="admin-filter-search" role="search" aria-label="Account search" onSubmit={(event) => { event.preventDefault(); filter({ search: search.trim() }); setRefresh((value) => value + 1); }}>
        <label className="search-field"><Search size={16} /><span className="sr-only">Name, company or email</span><input value={search} onChange={(event) => setSearch(event.target.value)} maxLength={120} type="search" placeholder="Name, company or email" /></label>
        <button className="secondary-button" type="submit" disabled={loading}>Search</button>
      </form>
      <div className="chip-group" role="group" aria-label="Filter by role">{roleOptions.map(([value, label]) => <button key={value} type="button" className="chip" aria-pressed={(filters.role ?? "") === value} onClick={() => filter({ role: value })}>{label}</button>)}</div>
      <div className="chip-group" role="group" aria-label="Filter by status">{statusOptions.map(([value, label]) => <button key={value} type="button" className="chip" aria-pressed={(filters.status ?? "") === value} onClick={() => filter({ status: value })}>{label}</button>)}</div>
    </div>
    <dialog className="admin-dialog" ref={resetDialog} onCancel={(event) => { if (busy !== null) event.preventDefault(); else closeReset(); }} aria-labelledby="reset-title">
      <div className="page-heading"><h2 id="reset-title">{resetKind === "mfa" ? "Reset two-step verification" : "Password recovery"}</h2><button className="icon-button" aria-label={resetKind === "mfa" ? "Close two-step verification reset" : "Close password recovery"} title="Close" onClick={closeReset} disabled={busy !== null}><X size={18} /></button></div>
      <p>{resetUser?.display_name}</p>
      <p className="recovery-email">{resetUser?.email}</p>
      {resetError && <p className="notice error" role="alert">{resetError}</p>}
      {resetKind === "mfa" ? (mfaResetDone ? <p className="notice" role="status">Two-step verification is off for this account and its sessions were signed out. They can sign in with their password and set it up again.</p> : <form onSubmit={issueReset}><p>This removes their authenticator and recovery codes. Do this only after confirming who is asking, for example when they lost their phone.</p><label className="studio-field">Your administrator password<input type="password" autoComplete="current-password" value={confirmationPassword} onChange={(event) => setConfirmationPassword(event.target.value)} required /></label><button className="primary-button" disabled={busy !== null}><ShieldOff size={16} />Reset two-step verification</button></form>)
        : resetLink ? <div><label className="studio-field">Reset link (expires in 15 minutes)<input value={resetLink} readOnly autoComplete="off" /></label><button className="secondary-button" onClick={() => { void navigator.clipboard.writeText(resetLink).then(() => setCopied(true)).catch(() => setResetError("Could not copy the link. Select the field to copy it.")); }}><Copy size={16} />{copied ? "Copied" : "Copy reset link"}</button></div> : <form onSubmit={issueReset}><label className="studio-field">Your administrator password<input type="password" autoComplete="current-password" value={confirmationPassword} onChange={(event) => setConfirmationPassword(event.target.value)} required /></label><button className="primary-button" disabled={busy !== null}><KeyRound size={16} />Issue reset link</button></form>}
    </dialog>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="data-table-wrap" aria-busy={loading}><table className="data-table admin-accounts-table"><thead><tr><th scope="col">Account</th><th scope="col">Role</th><th scope="col">Joined</th><th scope="col">2-step</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead><tbody>
      {accounts.slice(0, PAGE_SIZE).map((account) => <tr key={account.user_id}>
        <td><div className="account-cell"><span className={`account-avatar role-${account.role}`} aria-hidden="true">{account.display_name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span><div><strong>{account.display_name}</strong><div className="admin-job-employer">{account.email}{account.company_name ? ` · ${account.company_name}` : ""}</div>{account.is_demo && <span className="oversight-flag">Demo data</span>}</div></div></td>
        <td className="capitalize">{account.role}</td><td title={new Date(account.created_at).toLocaleString()}>{relativeTime(account.created_at)}</td><td>{account.mfa_enabled ? <span className="admin-job-status open">On</span> : <span className="admin-row-note">Off</span>}</td>
        <td><span className={`admin-job-status ${account.is_active ? "open" : "closed"}`}>{account.is_active ? "Active" : "Suspended"}</span></td>
        <td>{account.role === "admin" ? <span className="admin-row-note">Managed outside the dashboard</span> : <div className="admin-row-actions">
          {account.is_active && <button className="text-button" disabled={busy !== null} onClick={() => openReset(account)} aria-label={`Reset password for ${account.email}`}><KeyRound size={15} />Reset password</button>}
          {account.mfa_enabled && <button className="text-button" disabled={busy !== null} onClick={() => openReset(account, "mfa")} aria-label={`Reset two-step verification for ${account.email}`}><ShieldOff size={15} />Reset 2-step</button>}
          <button className="text-button" disabled={busy !== null || loading} onClick={() => void changeAccount(account)} aria-label={`${account.is_active ? "Suspend" : "Reactivate"} ${account.email}`}>{account.is_active ? <><UserX size={15} />Suspend</> : <><UserCheck size={15} />Reactivate</>}</button>
        </div>}</td>
      </tr>)}
      {!accounts.length && <tr><td colSpan={6}>{loading ? "Loading accounts..." : error ? "Accounts unavailable" : "No accounts match these filters"}</td></tr>}
    </tbody></table></div>
    <ListPagination label="accounts" offset={offset} pageSize={PAGE_SIZE} hasNext={accounts.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </div>;
}
