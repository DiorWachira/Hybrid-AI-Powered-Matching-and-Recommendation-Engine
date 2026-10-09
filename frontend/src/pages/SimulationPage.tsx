import { useEffect, useRef, useState } from "react";
import { Activity, BriefcaseBusiness, Check, ChevronRight, Download, FlaskConical, LoaderCircle, Pause, Play, RotateCcw, ShieldCheck, SkipForward, Users, X } from "lucide-react";
import { api, type SimulationRun } from "../lib/api";

const labels: Record<string, string> = { candidate_joined: "Profile ready", application_attempted: "Applying", application_blocked: "Ineligible", application_submitted: "Submitted", match_scored: "Scored", reviewing: "Reviewing", shortlisted: "Shortlisted", review_required: "Review required" };

export function SimulationPage() {
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const eventList = useRef<HTMLOListElement>(null);
  const total = run?.events.length ?? 0;
  const complete = !!run && cursor === total;

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!playing || !run || cursor >= total) return;
    const timer = window.setTimeout(() => { setCursor((value) => value + 1); if (cursor + 1 === total) setPlaying(false); }, 1000 / speed);
    return () => window.clearTimeout(timer);
  }, [playing, cursor, speed, run, total]);
  useEffect(() => { const list = eventList.current; if (list) list.scrollTop = list.scrollHeight; }, [cursor]);

  const simulate = async () => {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setLoading(true); setPlaying(false); setError(null);
    try {
      const data = await api.simulate(localStorage.getItem("jobbridge_token") ?? "", request.signal);
      if (request.signal.aborted) return;
      setRun(data); setCursor(0); setSelected(null);
      setPlaying(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (reason) { if (!request.signal.aborted) setError(reason instanceof Error ? reason.message : "Simulation unavailable."); }
    finally { controller.current = null; if (!request.signal.aborted) setLoading(false); }
  };
  const events = run?.events.slice(0, cursor) ?? [];
  const posted = new Set(events.filter((event) => event.kind === "job_posted").map((event) => event.job_id));
  const scoreVisible = new Set(events.filter((event) => event.kind === "match_scored" || event.kind === "application_blocked").map((event) => event.candidate_id));
  const candidate = run?.candidates.find((item) => item.candidate_id === selected);
  const match = run?.matches.find((item) => item.candidate_id === selected);
  const exportRun = () => {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `jobbridge-sandbox-${run.run_id}.json`; link.click(); URL.revokeObjectURL(url);
  };

  return <main className="studio-page simulation-page">
    <div className="page-heading"><div><p className="eyebrow">Administration / Sandbox</p><h1>Recruitment simulation</h1><p>Fictional profiles. Real model scores. No live records changed.</p></div><button className="primary-button" disabled={loading || playing} onClick={() => void simulate()}>{loading ? <LoaderCircle size={17} className="simulation-spinner" /> : <FlaskConical size={17} />}{loading ? "Preparing scenario..." : run ? "New simulation" : "Simulate"}</button></div>
    <div className="simulation-banner"><img src="/media/workspace.jpg" alt="" /><div><span className="eyebrow">Demo employer</span><strong>Nairobi Parcel Lab</strong><span>Logistics / Data & engineering</span></div><span className="simulation-sandbox"><ShieldCheck size={16} />Isolated sandbox</span></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading && <p role="status" className="notice"><LoaderCircle size={16} />Preparing fictional profiles and computing model scores. Initial model loading may take a minute.</p>}
    <section className="simulation-window" aria-label="Simulation playback" aria-busy={loading}>
      <div className="simulation-toolbar"><div className="simulation-controls"><button className="icon-button" title={playing ? "Pause playback" : "Play playback"} aria-label={playing ? "Pause playback" : "Play playback"} disabled={!run || loading || complete} onClick={() => setPlaying((value) => !value)}>{playing ? <Pause size={17} /> : <Play size={17} />}</button><button className="icon-button" title="Next event" aria-label="Next event" disabled={!run || loading || playing || complete} onClick={() => setCursor((value) => Math.min(total, value + 1))}><SkipForward size={17} /></button><button className="icon-button" title="Replay scenario" aria-label="Replay scenario" disabled={!run || loading} onClick={() => { setCursor(0); setPlaying(false); setSelected(null); }}><RotateCcw size={17} /></button><label className="simulation-speed">Speed<select aria-label="Playback speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}><option value={1}>1x</option><option value={2}>2x</option><option value={4}>4x</option></select></label></div><span className="simulation-state">{loading ? "Computing" : complete ? "Complete" : playing ? "Playing" : run ? "Paused" : "Ready"} / {cursor} of {total}</span><button className="icon-button" title="Download simulation results" aria-label="Download simulation results" disabled={!run || !complete || loading} onClick={exportRun}><Download size={17} /></button></div>
      <progress className="simulation-progress" aria-label="Simulation progress" max={total || 1} value={cursor} />
      <div className="simulation-stats"><span><BriefcaseBusiness size={16} />{posted.size} postings</span><span><Users size={16} />{events.filter((event) => event.kind === "application_submitted").length} submitted</span><span><X size={16} />{events.filter((event) => event.kind === "application_blocked").length} blocked</span><span><Check size={16} />{events.filter((event) => event.kind === "shortlisted").length} shortlisted</span></div>
      <div className="simulation-stage"><div className="simulation-roster"><h2><Users size={17} />Candidate pipeline</h2>{!run ? <div className="simulation-empty"><FlaskConical size={30} /><strong>No scenario running</strong></div> : run.candidates.map((person) => {
        const latest = [...events].reverse().find((event) => event.candidate_id === person.candidate_id);
        const score = run.matches.find((item) => item.candidate_id === person.candidate_id);
        return <button key={person.candidate_id} className={`simulation-person ${selected === person.candidate_id ? "is-selected" : ""}`} onClick={() => setSelected(person.candidate_id)} aria-pressed={selected === person.candidate_id} aria-label={`Inspect ${person.full_name}`}><span className="identity-avatar" aria-hidden="true">{person.full_name.split(" ").map((name) => name[0]).join("")}</span><span><strong>{person.full_name}</strong><small>{person.years_experience} years / {person.location}</small></span><span className={`simulation-person-status ${latest?.kind === "application_blocked" ? "is-blocked" : ""}`}>{labels[latest?.kind ?? ""] ?? "Queued"}{scoreVisible.has(person.candidate_id) && score?.hard_rule_passed && <b>{Math.round(score.final_score * 100)}%</b>}</span><ChevronRight size={15} /></button>;
      })}</div><div className="simulation-feed"><h2><Activity size={17} />Activity timeline</h2><ol ref={eventList} aria-label="Simulation events">{events.map((event) => <li key={event.sequence} className={event.kind === "application_blocked" ? "is-blocked" : ""}><span>{String(event.sequence).padStart(2, "0")}</span><p>{event.message}</p></li>)}{!events.length && <li><span>00</span><p>Waiting for the first event.</p></li>}</ol><p className="sr-only" role="status">{events.at(-1)?.message ?? "Simulation ready."}</p></div></div>
    </section>
    {run && <section className="data-section" aria-label="Simulation postings"><h2 className="section-heading"><BriefcaseBusiness size={18} />Postings</h2><div className="simulation-jobs">{run.jobs.map((job) => <article key={job.job_id}><span className="eyebrow">{posted.has(job.job_id) ? "Posted" : "Queued"}</span><h3>{job.title}</h3><p>{job.location} / {job.required_experience_years}+ years / Up to KES {job.salary_range_max.toLocaleString()}</p><div className="skill-tags">{job.required_skills.map((skill) => <span key={skill}>{skill}</span>)}</div></article>)}</div></section>}
    {candidate && match && <section className="data-section simulation-inspection" aria-label="Candidate inspection"><h2>{candidate.full_name}</h2><p>{candidate.resume_text}</p><div className="skill-tags">{candidate.skills.map((skill) => <span key={skill}>{skill}</span>)}</div><p>Certifications: {candidate.certifications.join(", ") || "None"} / Salary: KES {candidate.expected_salary.toLocaleString()} / Authorization: {candidate.work_authorized ? "Yes" : "No"}</p>{scoreVisible.has(candidate.candidate_id) ? match.hard_rule_passed ? <><div className="simulation-metrics">{[["Semantic relevance", match.semantic_score], ["Skill overlap", match.skill_overlap], ["Growth signal", match.growth_score], ["Model score", match.final_score]].map(([label, value]) => <label key={String(label)}>{label}<meter min={0} max={1} value={Number(value)} /><strong>{Math.round(Number(value) * 100)}%</strong></label>)}</div><p>Matched skills: {match.matched_skills?.join(", ") || "None"}</p><p>Missing skills: {match.missing_skills?.join(", ") || "None"}</p></> : <div className="notice error"><ShieldCheck size={17} /><div>Eligibility failed<ul>{match.rule_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div></div> : <p>Assessment pending in playback.</p>}</section>}
    <footer className="simulation-provenance"><p>Sandbox playback / Scripted recruiter decisions / Experimental scores, not hiring probabilities</p>{run && <p>Model: {run.model_version} / Threshold: {run.decision_threshold.toFixed(2)} / Run: {run.run_id}</p>}</footer>
  </main>;
}