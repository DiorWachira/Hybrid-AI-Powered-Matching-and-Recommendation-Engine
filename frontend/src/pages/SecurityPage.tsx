import { useEffect, useState } from "react";
import { KeyRound, RefreshCw, ShieldCheck, ShieldOff, Smartphone } from "lucide-react";
import { api, type CurrentAccount, type MfaSetup, type Session } from "../lib/api";
import { MfaEnrollment, OneTimeCodeField, RecoveryCodes } from "../components/TwoStep";

type Panel = "idle" | "start" | "scan" | "regenerate" | "disable";

export function SecurityPage() {
  const [account, setAccount] = useState<CurrentAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>("idle");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const token = () => localStorage.getItem("jobbridge_token") ?? "";

  useEffect(() => {
    let active = true;
    setLoading(true);
    void api.currentAccount(token()).then((value) => { if (active) { setAccount(value); setError(null); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  const open = (next: Panel) => { setPanel(next); setPassword(""); setCode(""); setError(null); setNotice(null); };
  // Turning MFA on or off signs out other sessions, so the response carries this tab's replacement token.
  const keepSession = (session: Session) => localStorage.setItem("jobbridge_token", session.access_token);
  const run = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { await action(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed."); setCode(""); }
    finally { setBusy(false); setPassword(""); }
  };

  const enabled = account?.mfa_enabled ?? false;
  return <main className="studio-page security-page">
    <div className="page-heading"><div><p className="eyebrow">Account</p><h1>Security.</h1><p>{account?.email ?? "Your sign-in settings."}</p></div></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <section className="data-section security-card" aria-labelledby="mfa-heading" aria-busy={loading}>
      <h2 id="mfa-heading" className="section-heading"><Smartphone size={18} />Two-step verification</h2>
      {loading && !account ? <p>Loading...</p> : account && <>
        <p className="security-status"><span className={`admin-job-status ${enabled ? "open" : "closed"}`}>{enabled ? "On" : "Off"}</span>
          {enabled ? `Sign-ins need a code from your authenticator app. ${account.mfa_recovery_codes_remaining} of 10 recovery codes left.` : "Add a code from your phone to every sign-in, so a stolen password alone cannot open your account."}
          {account.mfa_required && <span className="security-note">Required for {account.role} accounts.</span>}</p>
        {enabled && account.mfa_recovery_codes_remaining <= 3 && panel === "idle" && <p className="notice error">You are running low on recovery codes. Generate a new set.</p>}

        {codes ? <RecoveryCodes codes={codes} email={account.email} doneLabel="Done" onDone={() => { setCodes(null); setSetup(null); open("idle"); setRefresh((value) => value + 1); }} />
          : panel === "scan" && setup ? <MfaEnrollment token={token()} setup={setup} onEnabled={(session, recoveryCodes) => { keepSession(session); setCodes(recoveryCodes); setNotice("Two-step verification is on. Other sessions were signed out."); }} />
          : panel === "start" ? <form className="security-form" onSubmit={(event) => { event.preventDefault(); void run(async () => { setSetup(await api.startMfaSetup(token(), password)); setPanel("scan"); }); }}>
            <label className="studio-field">Confirm your password<input type="password" autoComplete="current-password" maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} required autoFocus /></label>
            <div className="workflow-actions"><button className="primary-button" disabled={busy}><KeyRound size={16} />{busy ? "Preparing..." : "Continue"}</button><button type="button" className="secondary-button" disabled={busy} onClick={() => open("idle")}>Cancel</button></div>
          </form>
          : panel === "regenerate" || panel === "disable" ? <form className="security-form" onSubmit={(event) => { event.preventDefault(); void run(async () => {
              if (panel === "regenerate") setCodes((await api.regenerateRecoveryCodes(token(), password, code)).recovery_codes);
              else { keepSession(await api.disableMfa(token(), password, code)); open("idle"); setNotice("Two-step verification is off."); setRefresh((value) => value + 1); }
            }); }}>
            <label className="studio-field">Password<input type="password" autoComplete="current-password" maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} required autoFocus /></label>
            <OneTimeCodeField value={code} onChange={setCode} label="Authenticator or recovery code" kind="either" />
            <p className="security-note">{panel === "regenerate" ? "Your old recovery codes stop working." : "Your other sessions will be signed out."}</p>
            <div className="workflow-actions"><button className="primary-button" disabled={busy || code.length < 6}>{panel === "regenerate" ? <><RefreshCw size={16} />Generate new codes</> : <><ShieldOff size={16} />Turn off</>}</button><button type="button" className="secondary-button" disabled={busy} onClick={() => open("idle")}>Cancel</button></div>
          </form>
          : <div className="workflow-actions">{enabled ? <>
              <button className="secondary-button" onClick={() => open("regenerate")}><RefreshCw size={16} />New recovery codes</button>
              {!account.mfa_required && <button className="secondary-button" onClick={() => open("disable")}><ShieldOff size={16} />Turn off</button>}
            </> : <button className="primary-button" onClick={() => open("start")}><ShieldCheck size={16} />Set up two-step verification</button>}</div>}
      </>}
    </section>
  </main>;
}
