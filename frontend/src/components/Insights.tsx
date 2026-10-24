import type { ApplicationStatus, AuditEvent } from "../lib/api";

// Hiring stages in pipeline order; rejected and withdrawn are exits, not stages.
export const PIPELINE_STAGES = ["submitted", "reviewing", "shortlisted", "interviewed", "hired"] as const;
export const STAGE_LABELS: Record<ApplicationStatus, string> = {
  submitted: "New", reviewing: "Reviewing", shortlisted: "Shortlisted", interviewed: "Interviewed", hired: "Hired", rejected: "Rejected", withdrawn: "Withdrawn",
};
type StageCounts = Partial<Record<ApplicationStatus, number>>;

const DAY_MS = 86_400_000;

export function relativeTime(value: string, now = Date.now()) {
  const seconds = Math.round((now - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  const days = Math.floor(seconds * 1000 / DAY_MS);
  return days === 1 ? "yesterday" : days < 30 ? `${days} days ago` : new Date(value).toLocaleDateString();
}

const eventDescriptions: Record<string, string> = {
  "account.registered": "registered an account",
  "account.login": "signed in",
  "account.suspended": "suspended an account",
  "account.reactivated": "reactivated an account",
  "account.reset_issued": "issued a password reset link",
  "account.password_reset": "reset their password",
  "account.mfa_enabled": "turned on two-step verification",
  "account.mfa_disabled": "turned off two-step verification",
  "account.mfa_failed": "entered a wrong verification code",
  "account.mfa_reset": "reset an account's two-step verification",
  "account.mfa_recovery_regenerated": "generated new recovery codes",
  "application.submitted": "registered interest in a role",
  "application.withdrawn": "withdrew an application",
  "job.created": "published a job posting",
  "job.updated": "edited a job posting",
  "job.open": "reopened a job posting",
  "job.closed": "closed a job posting",
  "matches.evaluated": "ran a match evaluation",
  "ontology.skill_updated": "updated a skill",
  "ontology.skill_requested": "requested a skill change",
  "ontology.relation_requested": "linked related skills",
  "ontology.relation_removed": "removed a related-skill link",
  "opportunity.unsaved": "removed a saved opportunity",
  "profile.updated": "updated their profile",
  "resume.parsed": "uploaded a resume",
};

/** A readable sentence for an audit event, e.g. "moved an application to Hired". */
export function describeEvent(event: AuditEvent) {
  if (event.action === "application.status_changed") {
    const status = event.details?.status;
    return typeof status === "string" && status in STAGE_LABELS ? `moved an application to ${STAGE_LABELS[status as ApplicationStatus]}` : "updated an application";
  }
  return eventDescriptions[event.action] ?? event.action.replaceAll(".", " / ").replaceAll("_", " ");
}

export const eventTone = (action: string) => action === "account.suspended" || action === "account.mfa_failed" ? "warn" : action.endsWith("hired") || action === "account.registered" ? "good" : action.split(".")[0];

export function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const width = 120, height = 32, peak = Math.max(1, ...values);
  const points = values.map((value, index) => [index * width / (values.length - 1), height - 2 - value / peak * (height - 4)]);
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`${label}: ${values.join(", ")} over ${values.length} days`}>
    <polygon points={`0,${height} ${line} ${width},${height}`} />
    <polyline points={line} />
  </svg>;
}

export function ActivityColumns({ days, values }: { days: string[]; values: number[] }) {
  const peak = Math.max(1, ...values);
  return <div className="activity-columns" role="img" aria-label={`Events per day: ${values.join(", ")}`}>
    {values.map((value, index) => <span key={days[index]} title={`${new Date(`${days[index]}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}: ${value} events`}><i style={{ height: `${Math.max(value ? 8 : 2, value / peak * 100)}%` }} /></span>)}
  </div>;
}

/** Hiring funnel: how many applications reached each stage, with stage-to-stage conversion. */
export function HiringFunnel({ counts }: { counts: StageCounts }) {
  // An application at a later stage has passed through every earlier one.
  const reached = PIPELINE_STAGES.map((_, index) => PIPELINE_STAGES.slice(index).reduce((total, stage) => total + (counts[stage] ?? 0), 0));
  const total = reached[0] + (counts.rejected ?? 0) + (counts.withdrawn ?? 0);
  const widest = Math.max(1, total);
  return <div className="funnel">
    <div className="funnel-row is-total"><span>All applications</span><div className="funnel-track"><i style={{ width: "100%" }} /></div><strong>{total}</strong><small /></div>
    {PIPELINE_STAGES.map((stage, index) => {
      const previous = index ? reached[index - 1] : total;
      return <div className={`funnel-row stage-${stage}`} key={stage}><span>{index ? `Reached ${STAGE_LABELS[stage].toLowerCase()}` : "Active pipeline"}</span><div className="funnel-track"><i style={{ width: `${reached[index] / widest * 100}%` }} /></div><strong>{reached[index]}</strong><small>{previous ? `${Math.round(reached[index] / previous * 100)}%` : "—"}</small></div>;
    })}
    <p className="funnel-exits"><span>{counts.rejected ?? 0} rejected</span><span>{counts.withdrawn ?? 0} withdrawn</span><small>Stages count applications by where they are now; rejected and withdrawn ones are listed separately.</small></p>
  </div>;
}

/** A compact stacked bar of where one posting's applicants currently are. */
export function StageBar({ counts }: { counts: StageCounts }) {
  const stages = [...PIPELINE_STAGES, "rejected", "withdrawn"] as const;
  const total = stages.reduce((sum, stage) => sum + (counts[stage] ?? 0), 0);
  if (!total) return <p className="stage-bar-empty">No applicants yet</p>;
  return <div className="stage-bar-wrap">
    <div className="stage-bar" role="img" aria-label={stages.filter((stage) => counts[stage]).map((stage) => `${counts[stage]} ${STAGE_LABELS[stage].toLowerCase()}`).join(", ")}>
      {stages.map((stage) => counts[stage] ? <i key={stage} className={`stage-${stage}`} style={{ flexGrow: counts[stage] }} /> : null)}
    </div>
    <div className="stage-bar-legend">{stages.filter((stage) => counts[stage]).map((stage) => <span key={stage}><i className={`stage-${stage}`} />{counts[stage]} {STAGE_LABELS[stage].toLowerCase()}</span>)}</div>
  </div>;
}
