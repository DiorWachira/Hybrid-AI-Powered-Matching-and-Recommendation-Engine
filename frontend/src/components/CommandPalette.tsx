import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, BriefcaseBusiness, Check, Clock3, CornerDownLeft, FileText, FlaskConical, KeyRound, LayoutDashboard, LogOut, Network, Plus, Search, Sparkles, Target, UserRound, UserRoundSearch, UserX, Users } from "lucide-react";
import type { UserRole } from "../lib/api";

type Command = { id: string; label: string; group: string; icon: ComponentType<{ size?: number }>; to?: string; run?: () => void; keywords?: string };

const commandsByRole: Record<UserRole, Command[]> = {
  admin: [
    { id: "overview", label: "Admin overview", group: "Go to", icon: LayoutDashboard, to: "/admin" },
    { id: "accounts", label: "Accounts", group: "Go to", icon: Users, to: "/admin?panel=accounts", keywords: "users people" },
    { id: "activity", label: "Activity log", group: "Go to", icon: Activity, to: "/admin?panel=activity", keywords: "audit events history" },
    { id: "ontology", label: "Skill ontology", group: "Go to", icon: Network, to: "/admin?panel=ontology", keywords: "skills graph relations" },
    { id: "oversight", label: "Recruiter oversight", group: "Go to", icon: UserRoundSearch, to: "/admin/recruiters", keywords: "employers postings jobs" },
    { id: "simulation", label: "Matching simulation", group: "Go to", icon: FlaskConical, to: "/admin/simulation" },
    { id: "matches", label: "Match analysis", group: "Go to", icon: Target, to: "/matches" },
    { id: "flagged", label: "Review roles that need attention", group: "Actions", icon: AlertTriangle, to: "/admin/recruiters?attention=1", keywords: "stale flagged" },
    { id: "suspended", label: "Show suspended accounts", group: "Actions", icon: UserX, to: "/admin?panel=accounts&status=suspended" },
    { id: "recruiters", label: "Show recruiter accounts", group: "Actions", icon: BriefcaseBusiness, to: "/admin?panel=accounts&role=recruiter" },
  ],
  recruiter: [
    { id: "postings", label: "My postings", group: "Go to", icon: LayoutDashboard, to: "/recruiter" },
    { id: "matches", label: "Match analysis", group: "Go to", icon: Target, to: "/matches" },
    { id: "new", label: "Create a job posting", group: "Actions", icon: Plus, to: "/recruiter?new=1", keywords: "publish role" },
  ],
  candidate: [
    { id: "for-you", label: "Recommended for you", group: "Go to", icon: Sparkles, to: "/candidate?view=for-you" },
    { id: "all", label: "All opportunities", group: "Go to", icon: BriefcaseBusiness, to: "/candidate?view=all", keywords: "jobs browse" },
    { id: "history", label: "My activity", group: "Go to", icon: Clock3, to: "/candidate?view=history", keywords: "saved" },
    { id: "applications", label: "My applications", group: "Go to", icon: Check, to: "/candidate?view=applications" },
    { id: "profile", label: "Edit my profile", group: "Actions", icon: UserRound, to: "/candidate?view=profile", keywords: "skills" },
    { id: "resume", label: "Upload a new resume", group: "Actions", icon: FileText, to: "/candidate?view=resume", keywords: "cv" },
  ],
};

export function CommandPalette({ role, onSignOut }: { role: UserRole; onSignOut: () => void }) {
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen((value) => !value); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (open) { setQuery(""); setCursor(0); dialog.current?.showModal(); requestAnimationFrame(() => input.current?.focus()); } else dialog.current?.close();
  }, [open]);

  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    const base: Command[] = [...commandsByRole[role], { id: "security", label: "Security settings", group: "Go to", icon: KeyRound, to: "/security", keywords: "password two-step mfa" }, { id: "signout", label: "Sign out", group: "Account", icon: LogOut, run: onSignOut }];
    const matches = term ? base.filter((command) => `${command.label} ${command.keywords ?? ""}`.toLowerCase().includes(term)) : base;
    // Free text becomes a search where the role has one.
    if (term && role === "admin") matches.unshift(
      { id: "find-account", label: `Find accounts matching "${query.trim()}"`, group: "Search", icon: Search, to: `/admin?${new URLSearchParams({ panel: "accounts", q: query.trim() })}` },
      { id: "find-posting", label: `Find postings matching "${query.trim()}"`, group: "Search", icon: Search, to: `/admin/recruiters?${new URLSearchParams({ q: query.trim() })}` },
    );
    return matches;
  }, [query, role, onSignOut]);

  const execute = (command: Command | undefined) => {
    if (!command) return;
    setOpen(false);
    if (command.run) command.run(); else if (command.to) navigate(command.to);
  };

  return <>
    <button type="button" className="palette-trigger" onClick={() => setOpen(true)} aria-label="Open command palette" aria-keyshortcuts="Control+K"><Search size={15} /><span>Jump to...</span><kbd>Ctrl K</kbd></button>
    <dialog ref={dialog} className="command-palette" aria-label="Command palette" onClose={() => setOpen(false)} onClick={(event) => { if (event.target === dialog.current) setOpen(false); }}>
      <div className="palette-search"><Search size={17} /><input ref={input} value={query} placeholder="Search pages and actions" aria-label="Search pages and actions" role="combobox" aria-expanded="true" aria-controls="palette-results" aria-activedescendant={results[cursor] ? `palette-${results[cursor].id}` : undefined}
        onChange={(event) => { setQuery(event.target.value); setCursor(0); }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") { event.preventDefault(); setCursor((value) => Math.min(results.length - 1, value + 1)); }
          else if (event.key === "ArrowUp") { event.preventDefault(); setCursor((value) => Math.max(0, value - 1)); }
          else if (event.key === "Enter") { event.preventDefault(); execute(results[cursor]); }
        }} /><kbd>Esc</kbd></div>
      <ul id="palette-results" role="listbox" className="palette-results">
        {results.map((command, index) => <li key={command.id} id={`palette-${command.id}`} role="option" aria-selected={index === cursor}>
          {(index === 0 || results[index - 1].group !== command.group) && <span className="palette-group">{command.group}</span>}
          <button type="button" tabIndex={-1} className={index === cursor ? "is-active" : ""} onMouseMove={() => setCursor(index)} onClick={() => execute(command)}><command.icon size={16} /><span>{command.label}</span>{index === cursor && <CornerDownLeft size={14} />}</button>
        </li>)}
        {!results.length && <li className="palette-empty">No matching pages or actions</li>}
      </ul>
    </dialog>
  </>;
}
