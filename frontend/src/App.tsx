import { useState } from "react";
import {
  Activity,
  Bell,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  CircleDot,
  Clock3,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  Menu,
  Network,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  X,
} from "lucide-react";
import { demoCandidate, demoMatch, demoRole } from "./lib/demoMatch";

const candidates = [
  { id: "CAND-0412", name: "Amina Wanjiku", role: "DevOps Engineer", score: 94.1, state: "Shortlisted", color: "emerald" },
  { id: "CAND-0398", name: "Brian Otieno", role: "Platform Engineer", score: 89.7, state: "Review", color: "violet" },
  { id: "CAND-0442", name: "Njeri Kamau", role: "Cloud Reliability", score: 86.3, state: "Review", color: "amber" },
  { id: "CAND-0371", name: "David Mwangi", role: "DevOps Engineer", score: 82.9, state: "New", color: "slate" },
];

const navItems = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Match queue", icon: Target, count: "24" },
  { label: "Job postings", icon: BriefcaseBusiness, count: "08" },
  { label: "Candidates", icon: Users },
];

function ScoreRow({ label, value, tone, icon: Icon }: { label: string; value: number; tone: "emerald" | "amber" | "violet"; icon: typeof Sparkles }) {
  const colors = {
    emerald: "bg-spectral-emerald shadow-glow-emerald",
    amber: "bg-spectral-amber shadow-glow-amber",
    violet: "bg-spectral-violet shadow-glow-violet",
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="flex items-center gap-2 text-white/65"><Icon className="h-3.5 w-3.5 text-white/40" />{label}</span>
        <span className="font-mono text-white">{Math.round(value * 100)}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/8">
        <div className={`h-full rounded-full ${colors[tone]}`} style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}

function App() {
  const [mobileNav, setMobileNav] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(candidates[0]);

  return (
    <div className="min-h-screen bg-obsidian text-white">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-spectral-emerald focus:px-4 focus:py-2 focus:text-obsidian">
        Skip to workspace
      </a>

      <aside className={`fixed inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-obsidian-surface/95 p-4 backdrop-blur-xl transition-transform lg:translate-x-0 ${mobileNav ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-2 py-1">
          <a href="#top" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-spectral-emerald to-spectral-mint text-obsidian shadow-glow-emerald"><Network className="h-5 w-5" /></span>
            <span><strong className="block text-sm tracking-tight">JobBridge</strong><span className="font-mono text-[9px] uppercase tracking-[0.2em] text-white/35">placement OS</span></span>
          </a>
          <button className="text-white/55 lg:hidden" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X className="h-5 w-5" /></button>
        </div>

        <div className="mt-10 px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/30">Workspace</div>
        <nav className="mt-3 space-y-1" aria-label="Workspace">
          {navItems.map(({ label, icon: Icon, count }, index) => (
            <button key={label} className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${index === 1 ? "bg-spectral-emerald/10 text-spectral-emerald" : "text-white/55 hover:bg-white/5 hover:text-white"}`}>
              <span className="flex items-center gap-3"><Icon className="h-4 w-4" />{label}</span>{count && <span className="font-mono text-[10px] text-white/30">{count}</span>}
            </button>
          ))}
        </nav>

        <div className="mt-8 px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/30">Engine modules</div>
        <div className="mt-3 space-y-1">
          {[{ label: "Rule gate", icon: ShieldCheck, tone: "amber" }, { label: "Semantic vector", icon: Sparkles, tone: "emerald" }, { label: "Skill knowledge graph", icon: GitBranch, tone: "violet" }].map(({ label, icon: Icon, tone }) => (
            <div key={label} className="flex items-center gap-3 px-3 py-2 text-xs text-white/55"><span className={`h-1.5 w-1.5 rounded-full ${tone === "amber" ? "bg-spectral-amber" : tone === "violet" ? "bg-spectral-violet" : "bg-spectral-emerald"}`} /><Icon className="h-3.5 w-3.5 text-white/35" />{label}</div>
          ))}
        </div>

        <div className="absolute inset-x-4 bottom-4 rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <div className="flex items-center gap-2 text-xs text-white/70"><span className="animate-status h-1.5 w-1.5 rounded-full bg-spectral-emerald" />All systems operational</div>
          <p className="mt-2 font-mono text-[10px] text-white/30">POSTGRES · NEO4J · API</p>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-obsidian/85 px-5 backdrop-blur-xl lg:px-8">
          <div className="flex items-center gap-3"><button className="text-white/65 lg:hidden" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">Recruiter workspace</p><h1 className="text-sm font-medium text-white/85">Match queue / DevOps Engineer</h1></div></div>
          <div className="flex items-center gap-3"><div className="hidden items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/40 sm:flex"><Search className="h-3.5 w-3.5" />Search candidates</div><button className="relative rounded-lg border border-white/10 p-2 text-white/55 hover:border-white/20 hover:text-white" aria-label="Notifications"><Bell className="h-4 w-4" /><span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-spectral-amber" /></button><div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-spectral-violet to-spectral-indigo font-mono text-xs">RW</div></div>
        </header>

        <main id="main" className="relative mx-auto max-w-[1600px] space-y-6 overflow-hidden px-5 py-6 lg:px-8">
          <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid-pattern bg-grid-sm opacity-40" />
          <section className="relative grid gap-4 xl:grid-cols-[1.35fr_1fr_0.8fr]">
            <div className="glass-panel wave-violet rounded-2xl p-5 xl:col-span-2">
              <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><span className="status-chip compliance"><span className="h-1.5 w-1.5 rounded-full bg-spectral-amber" />Tier 1 passed</span><span className="font-mono text-[10px] text-white/30">ROLE-1187</span></div><h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Senior DevOps Engineer</h2><p className="mt-1 text-sm text-white/45">Platform reliability · Nairobi · KES 150k–250k</p></div><button className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 hover:border-spectral-emerald/50 hover:text-spectral-emerald">Open role <ChevronDown className="h-3.5 w-3.5" /></button></div>
              <div className="mt-7 grid gap-5 sm:grid-cols-3"><div><p className="metric-label">Eligible profiles</p><p className="metric-value">24</p><p className="metric-note text-spectral-emerald">+6 since yesterday</p></div><div><p className="metric-label">Avg. match index</p><p className="metric-value">87.4%</p><p className="metric-note text-spectral-violet">graph confidence</p></div><div><p className="metric-label">Time in queue</p><p className="metric-value">02:41</p><p className="metric-note text-spectral-amber">within target</p></div></div>
            </div>
            <div className="glass-panel wave-amber rounded-2xl p-5"><div className="flex items-center justify-between"><p className="metric-label">Pipeline pulse</p><Activity className="h-4 w-4 text-spectral-amber" /></div><div className="mt-5 flex items-end gap-1.5" aria-label="Recent matching activity"><div className="activity-bar h-8" /><div className="activity-bar h-12" /><div className="activity-bar h-10" /><div className="activity-bar h-16" /><div className="activity-bar h-12" /><div className="activity-bar h-20" /><div className="activity-bar h-24 active" /><div className="activity-bar h-16" /><div className="activity-bar h-28 active" /><div className="activity-bar h-20" /><div className="activity-bar h-32 active" /></div><div className="mt-4 flex justify-between font-mono text-[10px] text-white/30"><span>09:00</span><span>now</span></div></div>
          </section>

          <section className="relative grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_310px]">
            <div className="glass-panel rounded-2xl p-3"><div className="flex items-center justify-between px-2 pb-3"><div><p className="metric-label">Candidate queue</p><p className="mt-1 text-xs text-white/35">Sorted by match index</p></div><button className="text-white/35 hover:text-white" aria-label="Filter candidates"><Settings2 className="h-4 w-4" /></button></div><div className="space-y-1">{candidates.map((candidate) => <button key={candidate.id} onClick={() => setSelectedCandidate(candidate)} className={`candidate-row ${selectedCandidate.id === candidate.id ? "selected" : ""}`}><span className={`avatar ${candidate.color}`}>{candidate.name.split(" ").map((part) => part[0]).join("")}</span><span className="min-w-0 flex-1 text-left"><strong className="block truncate text-xs font-medium text-white/85">{candidate.name}</strong><span className="block truncate text-[11px] text-white/35">{candidate.role}</span></span><span className="text-right"><strong className="block font-mono text-xs text-spectral-emerald">{candidate.score.toFixed(1)}%</strong><span className="block text-[9px] uppercase text-white/25">{candidate.state}</span></span></button>)}</div><button className="mt-3 w-full rounded-lg border border-dashed border-white/10 py-2 text-xs text-white/35 hover:border-spectral-emerald/40 hover:text-spectral-emerald">View all 24 profiles</button></div>

            <div className="glass-panel wave-primary rounded-2xl p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="metric-label">Selected match / {selectedCandidate.id}</p><div className="mt-2 flex items-center gap-3"><span className={`avatar ${selectedCandidate.color}`}>{selectedCandidate.name.split(" ").map((part) => part[0]).join("")}</span><div><h2 className="text-xl font-semibold text-white">{selectedCandidate.name}</h2><p className="text-xs text-white/40">{selectedCandidate.role} · {demoCandidate.location}</p></div></div></div><div className="text-right"><p className="metric-label">Final match index</p><p className="font-mono text-4xl font-semibold text-spectral-emerald">{selectedCandidate.score.toFixed(1)}<span className="text-xl">%</span></p><span className="status-chip semantic mt-1">high confidence</span></div></div>
              <div className="mt-7 grid gap-6 lg:grid-cols-[1fr_210px]"><div className="space-y-5"><div><div className="mb-3 flex items-center justify-between"><p className="section-label semantic-label"><Sparkles className="h-3.5 w-3.5" />Semantic & graph signals</p><span className="font-mono text-[10px] text-white/30">TIER 2 / 03</span></div><div className="space-y-4"><ScoreRow label="Semantic fit / BERT" value={demoMatch.subScores[0].value} tone="emerald" icon={Sparkles} /><ScoreRow label="Skill graph overlap" value={demoMatch.subScores[1].value} tone="emerald" icon={GitBranch} /><ScoreRow label="Growth trajectory" value={demoMatch.subScores[2].value} tone="violet" icon={Activity} /></div></div><div className="border-t border-white/10 pt-4"><p className="section-label compliance-label"><ShieldCheck className="h-3.5 w-3.5" />Deterministic rule gate</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{demoMatch.hardFilters.map((filter) => <div key={filter.label} className="flex items-center gap-2 text-xs text-white/60"><Check className="h-3.5 w-3.5 text-spectral-amber" />{filter.label}</div>)}</div></div></div><div className="rounded-xl border border-white/10 bg-black/15 p-4"><div className="flex items-center justify-between"><p className="section-label">Skill gap</p><FileSearch className="h-4 w-4 text-spectral-violet" /></div><p className="mt-4 text-3xl font-mono text-white">{demoMatch.matchedSkills.length}<span className="text-white/25">/{demoRole.requiredSkills.length}</span></p><p className="mt-1 text-xs text-white/40">required skills matched</p><div className="mt-4 space-y-2">{demoMatch.matchedSkills.map((skill) => <div key={skill} className="flex items-center gap-2 text-[11px] text-white/60"><Check className="h-3 w-3 text-spectral-emerald" />{skill}</div>)}{demoMatch.missingSkills.map((skill) => <div key={skill} className="flex items-center gap-2 text-[11px] text-spectral-amber"><CircleDot className="h-3 w-3" />{skill} <span className="ml-auto text-[9px] uppercase text-white/25">gap</span></div>)}</div></div></div>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4"><div className="flex items-center gap-2 font-mono text-[10px] text-white/35"><Clock3 className="h-3.5 w-3.5" />Scored 42 sec ago <span className="text-spectral-emerald">· live</span></div><div className="flex gap-2"><button className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 hover:border-white/25 hover:text-white">Compare</button><button className="rounded-lg bg-spectral-emerald px-3 py-2 text-xs font-semibold text-obsidian shadow-glow-emerald hover:bg-spectral-mint">Advance candidate</button></div></div>
            </div>

            <aside className="space-y-5"><div className="glass-panel wave-violet rounded-2xl p-4"><div className="flex items-center justify-between"><p className="section-label latent-label"><Network className="h-3.5 w-3.5" />Graph neighborhood</p><span className="font-mono text-[10px] text-white/30">2-HOP</span></div><div className="relative mt-5 h-40 overflow-hidden rounded-xl border border-white/8 bg-black/15"><div className="graph-line line-a" /><div className="graph-line line-b" /><div className="graph-line line-c" /><span className="graph-node node-main">K8S</span><span className="graph-node node-one">Docker</span><span className="graph-node node-two">AWS</span><span className="graph-node node-three">Linux</span><span className="graph-node node-four">CI/CD</span></div><p className="mt-3 text-xs leading-relaxed text-white/40">4 direct matches · 2 related skill paths surfaced through the ontology.</p></div><div className="glass-panel rounded-2xl p-4"><div className="flex items-center justify-between"><p className="section-label">Role constraints</p><BriefcaseBusiness className="h-4 w-4 text-spectral-amber" /></div><dl className="mt-4 space-y-3 text-xs"><div className="flex justify-between gap-3"><dt className="text-white/40">Experience floor</dt><dd className="font-mono text-white/75">{demoRole.requiredExperience}+ years</dd></div><div className="flex justify-between gap-3"><dt className="text-white/40">Salary ceiling</dt><dd className="font-mono text-white/75">KES 250,000</dd></div><div className="flex justify-between gap-3"><dt className="text-white/40">Work location</dt><dd className="font-mono text-white/75">Nairobi / hybrid</dd></div><div className="flex justify-between gap-3"><dt className="text-white/40">Certification</dt><dd className="font-mono text-spectral-emerald">AWS / verified</dd></div></dl></div></aside>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
