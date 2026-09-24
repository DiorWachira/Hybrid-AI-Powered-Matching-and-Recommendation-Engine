import { useEffect, useState } from "react";
import { Check, CircleAlert, FileSearch } from "lucide-react";
import { PageTitle } from "../components/PageTitle";
import { api, type MatchCandidate } from "../lib/api";

export function MatchesPage() {
  const [results, setResults] = useState<MatchCandidate[]>([]);
  const [selected, setSelected] = useState(0);
  const [status, setStatus] = useState("Loading live evaluation...");

  useEffect(() => {
    const token = localStorage.getItem("jobbridge_token");
    const jobId = localStorage.getItem("jobbridge_job_id");
    if (!token || !jobId) {
      setStatus("Publish a job from the recruiter workspace to see live candidates.");
      return;
    }
    void api.evaluateMatches(jobId, token).then((response) => {
      setResults(response.candidates);
      setStatus(response.candidates.length ? "Live PostgreSQL evaluation" : "No candidate profiles are available yet.");
    }).catch((error: Error) => setStatus(error.message));
  }, []);

  const current = results[selected];
  return <main className="mx-auto max-w-[1400px] space-y-6 px-5 py-6 lg:px-8"><PageTitle eyebrow="FR-05 / live explainable results" title="Ranked matches, with the working shown." detail="Scores come from the persisted candidate profiles, job requirements, and Tier 1 rule gate." />{status && <p className={`rounded-xl border px-4 py-3 text-sm ${results.length ? "border-spectral-emerald/25 bg-spectral-emerald/5 text-spectral-emerald" : "border-spectral-amber/35 bg-spectral-amber/10 text-spectral-amber"}`}>{status}</p>}{results.length > 0 && current && <div className="grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]"><section className="glass-panel rounded-2xl p-4"><div className="flex items-center justify-between"><p className="section-label">Ranked candidates</p><span className="font-mono text-xs text-white/35">{results.length} live</span></div><div className="mt-4 space-y-2">{results.map((result, index) => <button key={result.candidate_id} onClick={() => setSelected(index)} className={`w-full rounded-xl border p-4 text-left transition ${index === selected ? "border-spectral-emerald/45 bg-spectral-emerald/8" : "border-white/8 bg-white/[0.02] hover:border-white/20"}`}><div className="flex items-start justify-between gap-4"><div><p className="font-mono text-[10px] text-white/30">RANK 0{index + 1}</p><strong className="mt-1 block text-sm">{result.full_name}</strong><span className="text-xs text-white/40">{result.hard_rule_passed ? "Eligible" : "Rule gate failed"}</span></div><strong className="font-mono text-xl text-spectral-emerald">{Math.round(result.final_score * 100)}%</strong></div><div className="mt-4 grid grid-cols-3 gap-2 font-mono text-[10px] text-white/45"><span>SKILLS {Math.round(result.skill_overlap * 100)}</span><span>TEXT {Math.round(result.semantic_score * 100)}</span><span>GROWTH {Math.round(result.growth_score * 100)}</span></div></button>)}</div></section><section className="glass-panel wave-primary rounded-2xl p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="section-label semantic-label">Selected explanation</p><h2 className="mt-2 text-2xl font-semibold">{current.full_name}</h2><p className="mt-1 text-sm text-white/40">Live candidate evaluation</p></div><div className="rounded-xl border border-spectral-emerald/35 bg-spectral-emerald/10 px-4 py-3 text-right"><p className="font-mono text-[10px] uppercase text-white/40">Final score</p><p className="font-mono text-2xl text-spectral-emerald">{Math.round(current.final_score * 100)}%</p></div></div><div className="mt-6 grid gap-3 sm:grid-cols-3"><Metric label="Skill overlap" value={current.skill_overlap} /><Metric label="Text similarity" value={current.semantic_score} /><Metric label="Growth score" value={current.growth_score} /></div><div className="mt-6 rounded-xl border border-white/10 bg-black/10 p-4"><p className="section-label">Tier 1 rule gate</p>{current.hard_rule_passed ? <p className="mt-3 flex items-center gap-2 text-sm text-spectral-emerald"><Check className="h-4 w-4" />All hard constraints passed</p> : <p className="mt-3 flex items-center gap-2 text-sm text-spectral-coral"><CircleAlert className="h-4 w-4" />{current.rule_reasons.join("; ")}</p>}</div><div className="mt-4 flex items-center gap-3 text-sm text-white/45"><FileSearch className="h-4 w-4 text-spectral-violet" />Scores are calculated by the local matching API.</div></section></div>}</main>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl border border-white/10 bg-black/10 p-4"><p className="text-xs text-white/40">{label}</p><p className="mt-2 font-mono text-xl text-white">{Math.round(value * 100)}%</p></div>;
}
