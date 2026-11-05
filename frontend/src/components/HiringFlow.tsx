import { useEffect, useMemo, useRef, useState } from "react";
import { BadgeCheck, CircleAlert, FlaskConical, Play, RotateCcw, Trophy, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { api, type HiringApplicant, type HiringFlow as Flow, type HiringSimulationStep, type RecruiterStatus } from "../lib/api";

const percent = (score: number | null) => score === null ? "—" : `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`;
const TOP_PRESETS = [3, 5, 10];
const INTERVIEW_SLOTS = 3;
const STEP_MS = 950;

type Stage = "select" | "shortlist" | "interview" | "hire" | "filled";
const STAGES: Array<{ key: Stage; label: string; status: string; caption: string }> = [
  { key: "select", label: "Select top", status: "submitted", caption: "waiting" },
  { key: "shortlist", label: "Shortlist", status: "reviewing", caption: "selected" },
  { key: "interview", label: "Interview", status: "shortlisted", caption: "shortlisted" },
  { key: "hire", label: "Hire", status: "interviewed", caption: "interviewed" },
  { key: "filled", label: "Filled", status: "hired", caption: "hired" },
];

/** The furthest stage anyone has reached, so the panel always opens on the next thing to do. */
export function currentStage(flow: Flow): Stage {
  const has = (status: string) => flow.applicants.some((item) => item.status === status);
  return has("hired") ? "filled" : has("interviewed") ? "hire" : has("shortlisted") ? "interview" : has("reviewing") ? "shortlist" : "select";
}

/** What the step counters read part-way through a simulated run, so they tick along with the replay. */
function replayView(steps: HiringSimulationStep[], shown: number, applicants: number): { stage: Stage; counts: Record<string, number> } {
  const size = (stage: string) => steps.find((step) => step.stage === stage)?.candidates.length ?? 0;
  const top = size("selected"), interviews = size("shortlisted"), latest = steps[shown - 1]?.stage;
  const waiting = applicants - top;
  if (latest === "selected") return { stage: "shortlist", counts: { submitted: waiting, reviewing: top, shortlisted: 0, interviewed: 0, hired: 0 } };
  if (latest === "shortlisted") return { stage: "interview", counts: { submitted: waiting, reviewing: top - interviews, shortlisted: interviews, interviewed: 0, hired: 0 } };
  if (latest === "interviewed") return { stage: "hire", counts: { submitted: waiting, reviewing: top - interviews, shortlisted: 0, interviewed: interviews, hired: 0 } };
  return { stage: "filled", counts: { submitted: waiting, reviewing: top - interviews, shortlisted: 0, interviewed: interviews - 1, hired: 1 } };
}

/** Applicants who can be picked for the next stage: scored, eligible and still waiting, best first. */
export function selectablePool(flow: Flow): HiringApplicant[] {
  return flow.applicants.filter((item) => item.status === "submitted" && item.hard_rule_passed && item.final_score !== null);
}

export function HiringFlow({ jobId, flow, onFlow, topN, onTopN }: { jobId: string; flow: Flow; onFlow: (flow: Flow) => void; topN: number; onTopN: (value: number) => void }) {
  const [viewing, setViewing] = useState<Stage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replay, setReplay] = useState<{ steps: HiringSimulationStep[]; shown: number; result: Flow } | null>(null);
  const [kept, setKept] = useState(false);
  const token = () => localStorage.getItem("jobbridge_token") ?? "";
  const replaying = !!replay && replay.shown < replay.steps.length;
  const live = replay && replaying ? replayView(replay.steps, replay.shown, flow.applicants.length) : null;
  const stage = live?.stage ?? viewing ?? currentStage(flow);
  const realCounts = useMemo(() => Object.fromEntries(STAGES.map((item) => [item.status, flow.applicants.filter((applicant) => applicant.status === item.status).length])), [flow]);
  const counts: Record<string, number> = live?.counts ?? realCounts;
  const pool = selectablePool(flow);
  const unscored = flow.applicants.filter((item) => item.final_score === null && item.status === "submitted").length;
  const ineligible = flow.applicants.filter((item) => item.status === "submitted" && item.hard_rule_passed === false).length;
  const hired = flow.applicants.filter((item) => item.status === "hired");
  const waiting = flow.applicants.filter((item) => ["submitted", "reviewing", "shortlisted", "interviewed"].includes(item.status)).length;
  const canSimulate = !!flow.evaluated_at && flow.job_status === "open" && !hired.length && flow.applicants.some((item) => item.hard_rule_passed && item.final_score !== null && ["submitted", "reviewing", "shortlisted", "interviewed"].includes(item.status));

  useEffect(() => {
    if (!replay || replay.shown >= replay.steps.length) return;
    // Viewers who asked for less motion get the whole result at once.
    const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : STEP_MS;
    const timer = window.setTimeout(() => setReplay((current) => current && { ...current, shown: current.shown + 1 }), delay);
    return () => window.clearTimeout(timer);
  }, [replay]);
  const replayDone = !!replay && !replaying;
  const shownResult = useRef<Flow | null>(null);
  useEffect(() => {
    if (replayDone && replay && shownResult.current !== replay.result) { shownResult.current = replay.result; onFlow(replay.result); setViewing(null); }
  }, [replayDone, replay, onFlow]);

  const run = async (action: () => Promise<Flow>) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { onFlow(await action()); setViewing(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "That step could not be completed."); }
    finally { setBusy(false); }
  };
  const advance = (ids: string[], status: RecruiterStatus) => run(() => api.advanceApplications(jobId, ids, status, token()));
  const simulate = async () => {
    if (busy || !window.confirm(`Simulate hiring for this role? The top ${topN} demo applicants move on, ${INTERVIEW_SLOTS} interview and the highest match score is hired. Real applicants are left alone, and you can undo it.`)) return;
    setBusy(true); setError(null); setReplay(null); setKept(false);
    try {
      const response = await api.simulateHiring(jobId, topN, INTERVIEW_SLOTS, token());
      setReplay({ steps: response.steps, shown: 1, result: response.flow });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The simulation could not run."); }
    finally { setBusy(false); }
  };
  const undo = async () => {
    if (!window.confirm("Undo the simulation? Applicants go back to where they were and the posting reopens.")) return;
    setReplay(null); setKept(false);
    await run(() => api.undoHiringSimulation(jobId, token()));
  };
  const complete = async () => {
    if (!window.confirm(`Close this posting and release ${waiting} remaining ${waiting === 1 ? "applicant" : "applicants"}?`)) return;
    await run(() => api.completeHiring(jobId, true, token()));
  };

  return <section className="hiring-flow" aria-label="Hiring flow">
    <header className="hiring-flow-head">
      <div><p className="eyebrow">Hiring flow</p><h2>From ranking to hire, on one page.</h2></div>
      <button className="secondary-button" disabled={busy || !canSimulate || replaying} title={canSimulate ? undefined : "Available after an evaluation, on an open role with no hire yet"} onClick={() => void simulate()}><FlaskConical size={16} />Simulate hiring</button>
    </header>
    <ol className="hiring-steps">{STAGES.map((item, index) => <li key={item.key}>
      <button aria-current={stage === item.key ? "step" : undefined} className={counts[item.status] ? "has-people" : ""} disabled={replaying} onClick={() => setViewing(item.key)}>
        <span className="hiring-step-number">{String(index + 1).padStart(2, "0")}</span>
        <strong>{item.label}</strong>
        <small><b>{counts[item.status]}</b> {item.caption}</small>
      </button>
    </li>)}</ol>
    {error && <p className="notice error" role="alert"><CircleAlert size={18} />{error}</p>}
    {!replaying && <>
      {!flow.evaluated_at ? <p className="hiring-empty">Evaluate candidates first. The match scores decide who moves on.</p>
        : !flow.applicants.length ? <p className="hiring-empty"><Users size={17} />Nobody has applied to this role yet. The ranking below shows who could fit.</p>
        : stage === "select" ? <SelectStage pool={pool} topN={topN} onTopN={onTopN} busy={busy} unscored={unscored} ineligible={ineligible} onMove={(ids) => void advance(ids, "reviewing")} />
        : stage === "shortlist" ? <PickStage key={`shortlist-${counts.reviewing}`} people={flow.applicants.filter((item) => item.status === "reviewing")} preselect={INTERVIEW_SLOTS} busy={busy} empty="Nobody is waiting here. Select your top candidates first." action={(count) => `Shortlist ${count} for interview`} hint="Those you leave unticked stay under review." onConfirm={(ids) => void advance(ids, "shortlisted")} />
        : stage === "interview" ? <PickStage key={`interview-${counts.shortlisted}`} people={flow.applicants.filter((item) => item.status === "shortlisted")} preselect={counts.shortlisted} busy={busy} empty="Nobody is shortlisted yet." action={(count) => `Mark ${count} ${count === 1 ? "interview" : "interviews"} complete`} hint="Tick each person once their interview has happened." onConfirm={(ids) => void advance(ids, "interviewed")} />
        : stage === "hire" ? <HireStage key={`hire-${counts.interviewed}`} people={flow.applicants.filter((item) => item.status === "interviewed")} busy={busy} onHire={(person) => { if (window.confirm(`Hire ${person.candidate_name}? This cannot be reversed.`)) void advance([person.application_id], "hired"); }} />
        : hired.length ? <FilledStage flow={flow} hired={hired} waiting={waiting} busy={busy} kept={kept} onComplete={() => void complete()} onKeep={() => setKept(true)} onUndo={() => void undo()} />
        : <p className="hiring-empty">Nobody has been hired for this role yet.</p>}
    </>}
    {replay && <SimulationReplay steps={replay.steps} shown={replay.shown} onSkip={replaying ? () => setReplay({ ...replay, shown: replay.steps.length }) : undefined} />}
  </section>;
}

function Person({ person, rank }: { person: HiringApplicant; rank: number }) {
  return <><span className="rank-number">{String(rank).padStart(2, "0")}</span><span className="hiring-person"><strong>{person.candidate_name}</strong><small>{person.candidate_location || "Location not specified"} / {person.years_experience} years{person.recommended ? " / Recommended" : ""}</small></span><b className="hiring-score">{percent(person.final_score)}</b></>;
}

function SelectStage({ pool, topN, onTopN, busy, unscored, ineligible, onMove }: { pool: HiringApplicant[]; topN: number; onTopN: (value: number) => void; busy: boolean; unscored: number; ineligible: number; onMove: (ids: string[]) => void }) {
  const picked = pool.slice(0, topN);
  return <div className="hiring-panel">
    <div className="hiring-panel-controls">
      <div className="top-picker" role="group" aria-label="How many candidates move on">
        <span>Move on the top</span>
        {TOP_PRESETS.map((value) => <button key={value} aria-pressed={topN === value} onClick={() => onTopN(value)}>{value}</button>)}
        <label>Other<input type="number" min={1} max={100} value={topN} onChange={(event) => onTopN(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label>
      </div>
      <button className="primary-button" disabled={busy || !picked.length} onClick={() => onMove(picked.map((item) => item.application_id))}><Play size={15} />Move {picked.length ? `top ${picked.length}` : "candidates"} to review</button>
    </div>
    {picked.length ? <ol className="hiring-people">{picked.map((person, index) => <li key={person.application_id}><Person person={person} rank={index + 1} /></li>)}</ol> : <p className="hiring-empty">No eligible applicants are waiting.</p>}
    <p className="hiring-note">{pool.length} eligible {pool.length === 1 ? "applicant" : "applicants"} waiting.{ineligible ? ` ${ineligible} did not meet the requirements.` : ""}{unscored ? ` ${unscored} applied after this evaluation; evaluate again to include them.` : ""} Those not picked stay waiting until you finish the role.</p>
  </div>;
}

function PickStage({ people, preselect, busy, empty, action, hint, onConfirm }: { people: HiringApplicant[]; preselect: number; busy: boolean; empty: string; action: (count: number) => string; hint: string; onConfirm: (ids: string[]) => void }) {
  const [picked, setPicked] = useState(() => new Set(people.slice(0, preselect).map((item) => item.application_id)));
  if (!people.length) return <p className="hiring-empty">{empty}</p>;
  const toggle = (id: string) => setPicked((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  return <div className="hiring-panel">
    <ol className="hiring-people is-pickable">{people.map((person, index) => <li key={person.application_id}><label><input type="checkbox" checked={picked.has(person.application_id)} onChange={() => toggle(person.application_id)} /><Person person={person} rank={index + 1} /></label></li>)}</ol>
    <div className="hiring-panel-controls"><p className="hiring-note">{hint}</p><button className="primary-button" disabled={busy || !picked.size} onClick={() => onConfirm([...picked])}><Play size={15} />{action(picked.size)}</button></div>
  </div>;
}

function HireStage({ people, busy, onHire }: { people: HiringApplicant[]; busy: boolean; onHire: (person: HiringApplicant) => void }) {
  const [choice, setChoice] = useState(people[0]?.application_id ?? "");
  const person = people.find((item) => item.application_id === choice);
  if (!people.length) return <p className="hiring-empty">Nobody has finished an interview yet.</p>;
  return <div className="hiring-panel">
    <ol className="hiring-people is-pickable">{people.map((item, index) => <li key={item.application_id}><label><input type="radio" name="hire-choice" checked={choice === item.application_id} onChange={() => setChoice(item.application_id)} /><Person person={item} rank={index + 1} /></label></li>)}</ol>
    <div className="hiring-panel-controls"><p className="hiring-note">The highest match score is ticked first. Your interview decides.</p><button className="primary-button" disabled={busy || !person} onClick={() => person && onHire(person)}><BadgeCheck size={16} />Hire {person?.candidate_name}</button></div>
  </div>;
}

function FilledStage({ flow, hired, waiting, busy, kept, onComplete, onKeep, onUndo }: { flow: Flow; hired: HiringApplicant[]; waiting: number; busy: boolean; kept: boolean; onComplete: () => void; onKeep: () => void; onUndo: () => void }) {
  const needsDecision = !kept && (waiting > 0 || flow.job_status === "open");
  return <div className="hiring-panel hiring-filled">
    <div className="hiring-filled-card"><Trophy size={22} /><div><h3>{hired.map((item) => item.candidate_name).join(", ")} hired</h3><p>{hired.length === 1 ? `Match score ${percent(hired[0].final_score)}.` : `${hired.length} people hired for this role.`} Posting {flow.job_status}.{flow.simulation ? " This hire was simulated, so no interview took place." : ""}</p></div>{flow.simulation && <span className="simulated-tag">Simulated</span>}</div>
    {needsDecision && <p className="hiring-note">{waiting ? `${waiting} ${waiting === 1 ? "applicant is" : "applicants are"} still waiting. ` : ""}Finish the role, or keep the posting open to hire again.</p>}
    <div className="workflow-actions">
      {needsDecision && <button className="primary-button" disabled={busy} onClick={onComplete}>Close posting{waiting ? ` and release ${waiting}` : ""}</button>}
      {needsDecision && <button className="secondary-button" disabled={busy} onClick={onKeep}>Keep open</button>}
      <Link className="secondary-button" to="/filled-roles"><BadgeCheck size={16} />See filled roles</Link>
      {flow.simulation && <button className="secondary-button" disabled={busy} onClick={onUndo}><RotateCcw size={16} />Undo simulation</button>}
    </div>
  </div>;
}

function SimulationReplay({ steps, shown, onSkip }: { steps: HiringSimulationStep[]; shown: number; onSkip?: () => void }) {
  return <div className="simulation-replay">
    <div className="simulation-replay-head"><span className="simulated-tag">Simulated run</span>{onSkip && <button className="secondary-button" onClick={onSkip}>Skip to result</button>}</div>
    <ol aria-live="polite">{steps.slice(0, shown).map((step) => <li key={step.stage} className={`is-${step.stage}`}>
      <strong>{step.title}</strong>
      <p>{step.detail}</p>
      {step.candidates.length > 0 && step.stage !== "hired" && <ul className="skill-tags">{step.candidates.map((name) => <li key={name}><span>{name}</span></li>)}</ul>}
    </li>)}</ol>
  </div>;
}
