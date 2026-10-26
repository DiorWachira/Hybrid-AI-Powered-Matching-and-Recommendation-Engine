import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ArrowUpRight, FlaskConical, KeyRound, LayoutDashboard, LogOut, Menu, Network, ShieldCheck, Target, UserRoundSearch, Users, X } from "lucide-react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api, type ApiHealth, type CurrentAccount } from "../lib/api";
import { clearSession, getSessionRole } from "../lib/session";
import { CommandPalette } from "./CommandPalette";

const navigationByRole = {
  candidate: [{ to: "/candidate", label: "My opportunities", icon: Users }, { to: "/security", label: "Security", icon: KeyRound }],
  recruiter: [
    { to: "/recruiter", label: "Recruiter workspace", icon: LayoutDashboard },
    { to: "/matches", label: "Match analysis", icon: Target },
    { to: "/security", label: "Security", icon: KeyRound },
  ],
  admin: [
    { to: "/admin", label: "Admin overview", icon: ShieldCheck },
    { to: "/admin/recruiters", label: "Recruiter oversight", icon: UserRoundSearch },
    { to: "/admin/simulation", label: "Simulation", icon: FlaskConical },
    { to: "/matches", label: "Match analysis", icon: Target },
    { to: "/security", label: "Security", icon: KeyRound },
  ],
} as const;

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileNav, setMobileNav] = useState(false);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [checking, setChecking] = useState(true);
  const [account, setAccount] = useState<CurrentAccount | null>(null);

  useEffect(() => {
    let active = true;
    void api.health().then((value) => { if (active) setHealth(value); }).catch(() => { if (active) setHealth(null); }).finally(() => { if (active) setChecking(false); });
    const token = localStorage.getItem("jobbridge_token");
    if (token) void api.currentAccount(token).then((value) => { if (active) setAccount(value); }).catch(() => { if (active) setAccount(null); });
    return () => { active = false; };
  }, []);

  const status = checking ? "Connecting" : health?.status === "ok" ? "All systems online" : health ? "Service degraded" : "API unavailable";
  const sessionRole = getSessionRole() ?? "recruiter";
  const visibleNavigation = navigationByRole[sessionRole];
  const homePath = sessionRole === "candidate" ? "/candidate" : sessionRole === "admin" ? "/admin" : "/recruiter";
  const accountName = account?.display_name?.trim() || null;
  const initials = accountName ? accountName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() : sessionRole === "admin" ? "AD" : sessionRole === "candidate" ? "CA" : "RE";
  const accountLine = accountName ? [accountName, account?.company_name].filter(Boolean).join(" · ") : account?.company_name || `${sessionRole} account`;
  const signOut = useCallback(() => { clearSession(); navigate("/auth", { replace: true }); }, [navigate]);

  return (
    <div className="workspace-shell">
      <a className="skip-link" href="#workspace-content">Skip to content</a>
      {mobileNav && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <aside id="workspace-navigation" className={`workspace-nav ${mobileNav ? "is-open" : ""}`}>
        <div className="nav-brand-row">
          <Link to={homePath} className="brand-lockup"><span className="brand-symbol"><Network size={22} /></span><span>JobBridge<span className="brand-dot">.</span></span></Link>
          <button className="icon-button mobile-only" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <div className="workspace-identity"><span className="identity-avatar" aria-hidden="true">{initials}</span><div><strong>{sessionRole === "admin" ? "Administration" : sessionRole === "candidate" ? "Career workspace" : "Talent workspace"}</strong><span title={accountLine}>{accountLine}</span>{account && <span className="identity-email" title={account.email}>{account.email}</span>}</div></div>
        <p className="eyebrow nav-label">Workspace</p>
        <nav aria-label="Primary workspace" className="workspace-links">
          {visibleNavigation.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end onClick={() => setMobileNav(false)} className={({ isActive }) => isActive ? "is-active" : ""}><Icon size={18} /><span>{label}</span><ArrowUpRight className="nav-arrow" size={15} /></NavLink>)}
        </nav>
        <div className="nav-bottom"><div className="engine-signature"><Network size={24} /><strong>Human potential.<br />Intelligent connections.</strong><span>JobBridge matching engine</span></div><div className="connection-state" role="status"><i className={health?.status === "ok" ? "online" : ""} />{status}</div></div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <div className="topbar-location"><button className="icon-button mobile-only" aria-label="Open navigation" aria-expanded={mobileNav} aria-controls="workspace-navigation" onClick={() => setMobileNav(true)}><Menu size={20} /></button><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{location.pathname === "/security" ? "Security" : location.pathname === "/admin/simulation" ? "Simulation" : location.pathname === "/admin/recruiters" ? "Recruiter oversight" : sessionRole === "candidate" ? "Discover" : sessionRole === "admin" ? "Overview" : "Recruitment"}</strong></div>
          <div className="topbar-actions"><CommandPalette role={sessionRole} onSignOut={signOut} /><span className="role-tag">{sessionRole}</span><button className="icon-button" title="Sign out" aria-label="Sign out" onClick={signOut}><LogOut size={18} /></button></div>
        </header>
        <div id="workspace-content">{children}</div>
        <footer className="workspace-footer"><span>JobBridge / Workforce placement</span><span>Rules. Relevance. Opportunity.</span></footer>
      </div>
    </div>
  );
}
