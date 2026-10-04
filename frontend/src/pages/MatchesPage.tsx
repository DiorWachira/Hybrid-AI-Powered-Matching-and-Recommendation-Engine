import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, CircleAlert, RefreshCw, Search, Target } from "lucide-react";
import { Link } from "react-router-dom";
import { api, type MatchCandidate } from "../lib/api";
import { MatchGraphView } from "../components/MatchGraphView";

const percent = (score: number) => Math.round(Math.max(0, Math.min(1, score)) * 100);

export function MatchesPage() {
  const [results, setResults] = useState<MatchCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState("");
  const [eligibleOnly, setEligibleOnly] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evaluatedAt, setEvaluatedAt] = useState<string | null>(null);
  const evaluationPending = useRef(false);
  const jobId = localStorage.getItem("jobbridge_job_id");

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token || !jobId) { setLoading(false); return; }
    setLoading(true); setError(null);
    void api.savedMatches(jobId, token).then((response) => { if (active) { setResults(response.candidates); setEvaluatedAt(response.evaluated_at); setSelectedId(response.candidates[0]?.candidate_id ?? null); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [jobId, retry]);

  const evaluate = async () => {
    const token = localStorage.getItem("jobbridge_token");
    if (!jobId || !token || evaluationPending.current || loading) return;
    evaluationPending.current = true; setEvaluating(true); setError(null);
    try {
      const response = await api.evaluateMatches(jobId, token);
      setResults(response.candidates); setEvaluatedAt(response.evaluated_at); setSelectedId(response.candidates[0]?.candidate_id ?? null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Evaluation failed."); }
    finally { evaluationPending.current = false; setEvaluating(false); }
  };

  const visible = results.filter((candidate) => (!eligibleOnly || candidate.hard_rule_passed) && candidate.full_name.toLowerCase().includes(query.toLowerCase()));
  const current = visible.find((candidate) => candidate.candidate_id === selectedId) ?? visible[0];
  return <main className="studio-page">
    <div className="page-heading"><div><p className="eyebrow">Match analysis</p><h1>A shortlist with a reason.</h1><p>{evaluatedAt ? `Evaluated ${new Date(evaluatedAt).toLocaleString()}` : "No saved evaluation"}</p></div><div className="match-actions"><Link to="/recruiter" className="secondary-button"><ArrowLeft size={16} />Role workspace</Link><button className="icon-button" aria-label="Refresh saved results" title="Refresh saved results" disabled={!jobId || loading || evaluating} onClick={() => setRetry((value) => value + 1)}><RefreshCw size={16} /></button><button className="primary-button" disabled={!jobId || loading || evaluating} onClick={() => void evaluate()}><Target size={16} />{evaluating ? "Evaluating..." : "Evaluate candidates"}</button></div></div>
    {error && <div className="notice error" role="alert"><CircleAlert size={18} />{error}</div>}
    {evaluating && <p className="notice" role="status">Evaluation in progress</p>}
    {loading ? <div className="empty-state" role="status"><RefreshCw size={26} className="animate-spin" /><h2>Loading saved results</h2></div> : !jobId ? <div className="empty-state"><Target size={30} /><h2>Your next shortlist starts with a role.</h2><Link to="/recruiter" className="primary-button">Create a role</Link></div> : <>
      <div className="dashboard-stats"><div><span>Candidates evaluated</span><strong>{results.length}</strong></div><div><span>Passed eligibility</span><strong>{results.filter((item) => item.hard_rule_passed).length}</strong></div><div><span>Highest score</span><strong>{results.length ? `${Math.max(...results.map((item) => percent(item.final_score)))}%` : "—"}</strong></div></div>
      <div className="results-toolbar"><label className="search-field"><Search size={17} /><input aria-label="Search candidates" placeholder="Search candidate names" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="sort-control"><input type="checkbox" checked={eligibleOnly} onChange={(event) => setEligibleOnly(event.target.checked)} />Eligible candidates only</label></div>
      {current ? <div className="rank-layout"><section aria-label="Ranked candidates" className="rank-list">{visible.map((candidate) => <button className="rank-item" key={candidate.candidate_id} aria-pressed={current.candidate_id === candidate.candidate_id} onClick={() => setSelectedId(candidate.candidate_id)}><span className="rank-number">{String(results.indexOf(candidate) + 1).padStart(2, "0")}</span><div><strong>{candidate.full_name}</strong><small>{candidate.hard_rule_passed ? "Eligible" : "Requirements not met"}</small></div><b>{percent(candidate.final_score)}%</b></button>)}</section><section className="score-detail" aria-label="Selected candidate scores"><p className="eyebrow">Individual breakdown</p><h2>{current.full_name}</h2><div className="final-score">{percent(current.final_score)}%<small>Overall match score</small></div><p className="notice">Experimental calibration / not a hiring probability</p><Metric label="Semantic relevance" value={current.semantic_score} /><Metric label="Skill alignment" value={current.skill_overlap} tone="blue" /><Metric label="Growth potential" value={current.growth_score} tone="copper" /><div className={`rule-outcome ${current.hard_rule_passed ? "" : "fail"}`}><div>{current.hard_rule_passed ? <Check size={18} /> : <CircleAlert size={18} />}{current.hard_rule_passed ? "All eligibility requirements passed" : "Eligibility requirements not met"}</div>{!current.hard_rule_passed && <ul>{current.rule_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}</div><SkillBreakdown title="Matched skills" skills={current.matched_skills} /><SkillBreakdown title="Missing skills" skills={current.missing_skills} /><p className="match-provenance">Model: {current.model_version ?? "Unrecorded"}</p></section></div> : <div className="empty-state"><Search size={28} /><h2>{error ? "Results unavailable" : evaluatedAt ? "No candidates to show" : "No saved evaluation"}</h2></div>}
      {current?.match_id && <MatchGraphView key={current.match_id} matchId={current.match_id} />}
    </>}
  </main>;
}

function Metric({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  const score = percent(value);
  return <div className={`score-row ${tone}`}><div><span>{label}</span><strong>{score}%</strong></div><div className="score-track" role="meter" aria-label={label} aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${score}%` }} /></div></div>;
}

function SkillBreakdown({ title, skills }: { title: string; skills?: string[] | null }) {
  return <section className="skill-breakdown" aria-label={title}><h3>{title}</h3>{skills == null ? <p>Not recorded for this evaluation</p> : skills.length ? <ul className="skill-tags">{skills.map((skill) => <li key={skill}><span>{skill}</span></li>)}</ul> : <p>None</p>}</section>;
}