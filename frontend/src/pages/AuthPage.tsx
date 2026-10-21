import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, BriefcaseBusiness, Eye, EyeOff, KeyRound, Network, ShieldCheck, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, type MfaSetup, type Session, type UserRole } from "../lib/api";
import { clearSession } from "../lib/session";
import { MfaEnrollment, OneTimeCodeField, RecoveryCodes } from "../components/TwoStep";

export function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register" | "reset">(() => window.location.hash.startsWith("#reset=") ? "reset" : new URLSearchParams(window.location.search).get("mode") === "register" ? "register" : "login");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("reset") ?? "");
  useEffect(() => {
    const readResetLink = () => {
      const token = new URLSearchParams(window.location.hash.slice(1)).get("reset");
      if (token) {
        setResetToken(token); setMode("reset");
        history.replaceState(null, "", window.location.pathname + window.location.search);
      }
    };
    readResetLink();
    window.addEventListener("hashchange", readResetLink);
    return () => window.removeEventListener("hashchange", readResetLink);
  }, []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Exclude<UserRole, "admin">>(() => new URLSearchParams(window.location.search).get("role") === "recruiter" ? "recruiter" : "candidate");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [location, setLocation] = useState("Nairobi");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  // After a correct password: "mfa" asks for a code, "enroll" makes a required-MFA account set one up first.
  const [step, setStep] = useState<"credentials" | "mfa" | "enroll">("credentials");
  const [challengeToken, setChallengeToken] = useState("");
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [enrolled, setEnrolled] = useState<{ session: Session; codes: string[] } | null>(null);
  const isRegistering = mode === "register";
  const isResetting = mode === "reset";

  const startSession = (session: Session) => {
    clearSession(); localStorage.setItem("jobbridge_token", session.access_token);
    navigate(session.role === "candidate" ? "/candidate" : session.role === "admin" ? "/admin" : "/recruiter", { replace: true });
  };
  const backToSignIn = (message: string | null = null) => {
    setStep("credentials"); setChallengeToken(""); setCode(""); setUseRecovery(false); setSetup(null); setEnrolled(null); setNotice(message);
  };
  const verify = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setNotice(null); setBusy(true);
    try { startSession(await api.verifyMfa(challengeToken, code)); }
    catch (error) {
      const message = error instanceof Error ? error.message : "Could not verify the code.";
      if (message.includes("expired")) backToSignIn(message); else { setNotice(message); setCode(""); }
    }
    finally { setBusy(false); }
  };
  const beginSetup = async () => {
    if (busy) return;
    setNotice(null); setBusy(true);
    try { setSetup(await api.startMfaSetup(challengeToken)); }
    catch (error) { backToSignIn(error instanceof Error ? `${error.message}. Sign in again to continue setup.` : "Sign in again to continue setup."); }
    finally { setBusy(false); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setNotice(null); setBusy(true);
    try {
      if (isResetting) {
        await api.resetPassword(resetToken, password);
        clearSession(); setResetToken(""); setPassword(""); setMode("login"); setNotice("Password updated. Sign in with your new password.");
        return;
      }
      if (isRegistering) {
        startSession(await api.register({ email, password, role, full_name: fullName, ...(role === "recruiter" ? { company_name: companyName } : {}), location }));
        return;
      }
      const result = await api.login(email, password);
      if (result.status === "authenticated") { startSession(result); return; }
      setChallengeToken(result.challenge_token); setPassword(""); setCode(""); setUseRecovery(false);
      setStep(result.status === "mfa_required" ? "mfa" : "enroll");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not sign in. Please try again."); }
    finally { setBusy(false); }
  };

  return <main className="auth-scene">
    <img className="auth-image" src="/media/workspace.jpg" alt="Sunlight falling across an open workspace with plants and shared desks" />
    <Link to="/" className="brand-lockup auth-brand"><span className="brand-symbol"><Network size={22} /></span><span>JobBridge<span className="brand-dot">.</span></span></Link>
    <div className="auth-content">
      <span className="eyebrow">People. Potential. Possibility.</span>
      <h1>{step === "mfa" ? "One more step." : step === "enroll" ? "Protect your account." : isResetting ? "Reset your password." : isRegistering ? "Make your next connection." : "Welcome to your next chapter."}</h1>
      <p>{step === "mfa" ? (useRecovery ? "Enter one of your saved recovery codes." : "Enter the 6-digit code from your authenticator app.") : step === "enroll" ? "This account must use two-step verification. Set it up once to continue." : isResetting ? "Account recovery" : isRegistering ? "Create your JobBridge account." : "Sign in to your JobBridge workspace."}</p>
      {step === "mfa" && <form onSubmit={verify} className="auth-form">
        <OneTimeCodeField key={useRecovery ? "recovery" : "totp"} value={code} onChange={setCode} label={useRecovery ? "Recovery code" : "Authentication code"} kind={useRecovery ? "recovery" : "totp"} />
        {notice && <p className="notice error" role="alert">{notice}</p>}
        <button className="primary-button" disabled={busy || (useRecovery ? code.replace(/-/g, "").length !== 10 : code.length !== 6)}>{busy ? "Checking..." : "Verify"}<ShieldCheck size={17} /></button>
      </form>}
      {step === "mfa" && <div className="auth-switch"><button disabled={busy} onClick={() => { setUseRecovery(!useRecovery); setCode(""); setNotice(null); }}>{useRecovery ? "Use authenticator app" : "Use a recovery code"}</button><button disabled={busy} onClick={() => backToSignIn()}><ArrowLeft size={13} className="inline-icon" />Back to sign in</button></div>}
      {step === "enroll" && <div className="auth-form">
        {notice && <p className="notice error" role="alert">{notice}</p>}
        {enrolled ? <RecoveryCodes codes={enrolled.codes} email={email} onDone={() => startSession(enrolled.session)} doneLabel="Continue to workspace" />
          : setup ? <MfaEnrollment token={challengeToken} setup={setup} onEnabled={(session, codes) => setEnrolled({ session, codes })} />
          : <button className="primary-button" disabled={busy} onClick={() => void beginSetup()}><KeyRound size={17} />{busy ? "Preparing..." : "Set up authenticator app"}</button>}
      </div>}
      {step === "enroll" && !enrolled && <div className="auth-switch"><button disabled={busy} onClick={() => backToSignIn()}><ArrowLeft size={13} className="inline-icon" />Back to sign in</button></div>}
      {step === "credentials" && <><form onSubmit={submit} className="auth-form">
        {isRegistering && <>
          <fieldset><legend className="sr-only">Account type</legend><div className="account-selector"><label><input type="radio" name="role" value="candidate" checked={role === "candidate"} onChange={() => setRole("candidate")} /><UserRound size={15} />Candidate</label><label><input type="radio" name="role" value="recruiter" checked={role === "recruiter"} onChange={() => setRole("recruiter")} /><BriefcaseBusiness size={15} />Recruiter</label></div></fieldset>
          <label className="studio-field">Full name<input autoComplete="name" value={fullName} minLength={2} maxLength={255} onChange={(event) => setFullName(event.target.value)} required /></label>
          {role === "recruiter" && <label className="studio-field">Company name<input autoComplete="organization" value={companyName} minLength={2} maxLength={255} onChange={(event) => setCompanyName(event.target.value)} required /></label>}
          <label className="studio-field">Location<input autoComplete="address-level2" maxLength={120} value={location} onChange={(event) => setLocation(event.target.value)} required /></label>
        </>}
        {isResetting ? <label className="studio-field">Reset code<input type="password" autoComplete="off" value={resetToken} onChange={(event) => setResetToken(event.target.value)} required /></label> : <label className="studio-field">Email address<input type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>}
        <label className="studio-field">Password<div className="password-field"><input type={showPassword ? "text" : "password"} autoComplete={isRegistering || isResetting ? "new-password" : "current-password"} minLength={isRegistering || isResetting ? 12 : 1} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" className="icon-button" aria-label={showPassword ? "Hide password" : "Show password"} title={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>{(isRegistering || isResetting) && <small>At least 12 characters</small>}</label>
        {notice && <p className="notice error" role="alert">{notice}</p>}
        <button className="primary-button" disabled={busy}>{busy ? "Please wait..." : isResetting ? "Update password" : isRegistering ? "Create account" : "Sign in"}<ArrowRight size={17} /></button>
      </form>
      <div className="auth-switch">{mode === "login" ? "New to JobBridge?" : "Already part of JobBridge?"}<button disabled={busy} onClick={() => { setMode(mode === "login" ? "register" : "login"); setNotice(null); setPassword(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button>{mode === "login" && <button disabled={busy} onClick={() => { setMode("reset"); setNotice(null); setPassword(""); }}>Reset password</button>}</div></>}
    </div>
    <div className="auth-caption">Room for your next idea.<span>JobBridge / Intelligent workforce placement</span></div>
  </main>;
}