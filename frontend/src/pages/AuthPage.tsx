import { useState } from "react";
import { KeyRound, Network } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, type UserRole } from "../lib/api";

export function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("recruiter@jobbridge.local");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Exclude<UserRole, "admin">>("recruiter");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [location, setLocation] = useState("Nairobi");
  const [notice, setNotice] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setNotice(null);
    try {
      const response = mode === "login"
        ? await api.login(email, password)
        : await api.register({ email, password, role, full_name: fullName || undefined, company_name: companyName || undefined, location });
      localStorage.setItem("jobbridge_token", response.access_token);
      navigate(response.role === "candidate" ? "/candidate" : "/recruiter");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Authentication failed. Check your details and try again.");
    }
  };

  const isRegistering = mode === "register";
  return <main className="grid min-h-screen place-items-center bg-obsidian p-5"><section className="w-full max-w-md glass-panel wave-violet rounded-2xl p-7"><Link to="/recruiter" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-spectral-emerald text-obsidian"><Network className="h-5 w-5" /></span><span><strong>JobBridge</strong><span className="block font-mono text-[9px] uppercase tracking-[0.18em] text-white/35">secure workspace</span></span></Link><div className="mt-8"><p className="section-label latent-label">Identity gateway</p><h1 className="mt-3 text-2xl font-semibold">{isRegistering ? "Create your workspace account." : "Sign in to your workspace."}</h1><p className="mt-2 text-sm text-white/45">Candidates manage evidence. Recruiters configure roles and audit match reasoning.</p></div><form className="mt-7 space-y-4" onSubmit={submit}>{isRegistering && <><label className="field"><span>Account type</span><select value={role} onChange={(event) => setRole(event.target.value as Exclude<UserRole, "admin">)}><option value="recruiter">Recruiter</option><option value="candidate">Candidate</option></select></label>{role === "candidate" ? <label className="field"><span>Full name</span><input value={fullName} onChange={(event) => setFullName(event.target.value)} required /></label> : <label className="field"><span>Company name</span><input value={companyName} onChange={(event) => setCompanyName(event.target.value)} required /></label>}<label className="field"><span>Location</span><input value={location} onChange={(event) => setLocation(event.target.value)} required /></label></>}<label className="field"><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label className="field"><span>Password{isRegistering && " (at least 12 characters)"}</span><input type="password" minLength={isRegistering ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{notice && <p className="rounded-lg border border-spectral-amber/35 bg-spectral-amber/10 p-3 text-xs text-spectral-amber">{notice}</p>}<button className="flex w-full items-center justify-center gap-2 rounded-lg bg-spectral-emerald px-4 py-3 text-sm font-semibold text-obsidian shadow-glow-emerald"><KeyRound className="h-4 w-4" />{isRegistering ? "Create account" : "Sign in"}</button></form><p className="mt-5 text-center text-xs text-white/40">{isRegistering ? "Already have an account?" : "No account?"} <button type="button" onClick={() => { setMode(isRegistering ? "login" : "register"); setNotice(null); }} className="text-spectral-emerald hover:underline">{isRegistering ? "Sign in" : "Create one"}</button></p></section></main>;
}
