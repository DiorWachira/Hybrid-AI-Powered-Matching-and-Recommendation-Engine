import { useState } from "react";
import { KeyRound, Network } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export function AuthPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("recruiter@jobbridge.local");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); try { const response = await api.login(email, password); localStorage.setItem("jobbridge_token", response.access_token); navigate(response.role === "candidate" ? "/candidate" : "/recruiter"); } catch { setNotice("Authentication API is not available yet. The final screen will use /api/auth/login with JWT storage and protected routes."); } };
  return <main className="grid min-h-screen place-items-center bg-obsidian p-5"><section className="w-full max-w-md glass-panel wave-violet rounded-2xl p-7"><Link to="/recruiter" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-spectral-emerald text-obsidian"><Network className="h-5 w-5" /></span><span><strong>JobBridge</strong><span className="block font-mono text-[9px] uppercase tracking-[0.18em] text-white/35">secure workspace</span></span></Link><div className="mt-8"><p className="section-label latent-label">Identity gateway</p><h1 className="mt-3 text-2xl font-semibold">Sign in to your workspace.</h1><p className="mt-2 text-sm text-white/45">Candidates manage evidence. Recruiters configure roles and audit match reasoning.</p></div><form className="mt-7 space-y-4" onSubmit={submit}><label className="field"><span>Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><label className="field"><span>Password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>{notice && <p className="rounded-lg border border-spectral-amber/35 bg-spectral-amber/10 p-3 text-xs text-spectral-amber">{notice}</p>}<button className="flex w-full items-center justify-center gap-2 rounded-lg bg-spectral-emerald px-4 py-3 text-sm font-semibold text-obsidian shadow-glow-emerald"><KeyRound className="h-4 w-4" />Sign in</button></form><p className="mt-5 text-center text-xs text-white/40">No account? <button className="text-spectral-emerald hover:underline">Request access</button></p></section></main>;
}
