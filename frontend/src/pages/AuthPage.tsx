import { useEffect, useState } from "react";
import { ArrowRight, BriefcaseBusiness, Eye, EyeOff, Network, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, type UserRole } from "../lib/api";
import { clearSession } from "../lib/session";

export function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register" | "reset">(() => window.location.hash.startsWith("#reset=") ? "reset" : "login");
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
  const [role, setRole] = useState<Exclude<UserRole, "admin">>("candidate");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [location, setLocation] = useState("Nairobi");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const isRegistering = mode === "register";
  const isResetting = mode === "reset";

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
      const response = isRegistering
        ? await api.register({ email, password, role, full_name: fullName, ...(role === "recruiter" ? { company_name: companyName } : {}), location })
        : await api.login(email, password);
      clearSession(); localStorage.setItem("jobbridge_token", response.access_token);
      navigate(response.role === "candidate" ? "/candidate" : response.role === "admin" ? "/admin" : "/recruiter", { replace: true });
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not sign in. Please try again."); }
    finally { setBusy(false); }
  };

  return <main className="auth-scene">
    <img className="auth-image" src="/media/workspace.jpg" alt="Sunlight falling across an open workspace with plants and shared desks" />
    <Link to="/" className="brand-lockup auth-brand"><span className="brand-symbol"><Network size={22} /></span><span>JobBridge<span className="brand-dot">.</span></span></Link>
    <div className="auth-content">
      <span className="eyebrow">People. Potential. Possibility.</span>
      <h1>{isResetting ? "Reset your password." : isRegistering ? "Make your next connection." : "Welcome to your next chapter."}</h1>
      <p>{isResetting ? "Account recovery" : isRegistering ? "Create your JobBridge account." : "Sign in to your JobBridge workspace."}</p>
      <form onSubmit={submit} className="auth-form">
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
      <div className="auth-switch">{mode === "login" ? "New to JobBridge?" : "Already part of JobBridge?"}<button disabled={busy} onClick={() => { setMode(mode === "login" ? "register" : "login"); setNotice(null); setPassword(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button>{mode === "login" && <button disabled={busy} onClick={() => { setMode("reset"); setNotice(null); setPassword(""); }}>Reset password</button>}</div>
    </div>
    <div className="auth-caption">Room for your next idea.<span>JobBridge / Intelligent workforce placement</span></div>
  </main>;
}