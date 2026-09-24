import { useEffect, useState, type ReactNode } from "react";
import { Bell, LayoutDashboard, Menu, Network, Settings2, ShieldCheck, Target, Users, X } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { api, type ApiHealth } from "../lib/api";
import { getSessionRole } from "../lib/session";

const navigation = [
  { to: "/recruiter", label: "Recruiter workspace", icon: LayoutDashboard },
  { to: "/matches", label: "Match analysis", icon: Target },
  { to: "/candidate", label: "Candidate profile", icon: Users },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileNav, setMobileNav] = useState(false);
  const [health, setHealth] = useState<ApiHealth | null>(null);

  useEffect(() => {
    void api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const status = health?.status === "ok" ? "connected" : health ? "degraded" : "demo";
  const sessionRole = getSessionRole();
  const visibleNavigation = sessionRole === "admin" ? [...navigation, { to: "/admin", label: "Admin overview", icon: ShieldCheck }] : navigation;

  return (
    <div className="min-h-screen bg-obsidian text-white">
      <aside className={`fixed inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-obsidian-surface/95 p-4 backdrop-blur-xl transition-transform lg:translate-x-0 ${mobileNav ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-2 py-1">
          <Link to="/recruiter" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-spectral-emerald to-spectral-mint text-obsidian shadow-glow-emerald"><Network className="h-5 w-5" /></span>
            <span><strong className="block text-sm tracking-tight">JobBridge</strong><span className="font-mono text-[9px] uppercase tracking-[0.2em] text-white/35">placement OS</span></span>
          </Link>
          <button className="text-white/55 lg:hidden" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X className="h-5 w-5" /></button>
        </div>
        <p className="mt-10 px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/30">Workspace</p>
        <nav className="mt-3 space-y-1" aria-label="Primary workspace">
          {visibleNavigation.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setMobileNav(false)} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${isActive ? "bg-spectral-emerald/10 text-spectral-emerald" : "text-white/55 hover:bg-white/5 hover:text-white"}`}><Icon className="h-4 w-4" />{label}</NavLink>)}
        </nav>
        <p className="mt-8 px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/30">System</p>
        <div className="mt-3 space-y-1 text-xs text-white/55"><div className="flex items-center gap-3 px-3 py-2"><ShieldCheck className="h-3.5 w-3.5 text-spectral-amber" />Rule gate</div><div className="flex items-center gap-3 px-3 py-2"><Network className="h-3.5 w-3.5 text-spectral-violet" />Skill graph</div><div className="flex items-center gap-3 px-3 py-2"><Settings2 className="h-3.5 w-3.5 text-spectral-emerald" />Engine settings</div></div>
        <div className="absolute inset-x-4 bottom-4 rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="flex items-center gap-2 text-xs text-white/70"><span className={`h-1.5 w-1.5 rounded-full ${status === "connected" ? "bg-spectral-emerald animate-status" : status === "degraded" ? "bg-spectral-amber" : "bg-white/35"}`} />API {status}</div><p className="mt-2 font-mono text-[10px] text-white/30">POSTGRES · NEO4J · FASTAPI</p></div>
      </aside>
      <div className="lg:pl-64"><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-obsidian/85 px-5 backdrop-blur-xl lg:px-8"><div className="flex items-center gap-3"><button className="text-white/65 lg:hidden" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">Hybrid workforce placement</p><p className="text-sm font-medium text-white/85">Operations workspace</p></div></div><div className="flex items-center gap-3"><Link to="/auth" className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:border-spectral-emerald/50 hover:text-spectral-emerald">Sign in</Link><button className="relative rounded-lg border border-white/10 p-2 text-white/55 hover:text-white" aria-label="Notifications"><Bell className="h-4 w-4" /><span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-spectral-amber" /></button></div></header>{children}</div>
    </div>
  );
}
