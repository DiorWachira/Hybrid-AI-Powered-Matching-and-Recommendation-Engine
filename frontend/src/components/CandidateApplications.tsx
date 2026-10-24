import { useEffect, useState } from "react";
import { BadgeCheck, ClipboardList, RefreshCw, RotateCcw, Undo2 } from "lucide-react";
import { api, type CandidateApplication } from "../lib/api";
import { ADMIN_PAGE_SIZE as PAGE_SIZE, ListPagination } from "./ListPagination";
import { PIPELINE_STAGES, STAGE_LABELS } from "./Insights";

// Stages a candidate can still opt out of; hired and rejected outcomes are final.
const withdrawable = new Set(["submitted", "reviewing", "shortlisted", "interviewed"]);

function ApplicationProgress({ status }: { status: CandidateApplication["status"] }) {
  const reached = PIPELINE_STAGES.indexOf(status as typeof PIPELINE_STAGES[number]);
  const ended = status === "rejected" || status === "withdrawn";
  return <ol className={`application-progress ${ended ? "is-ended" : ""}`} aria-label={`Application progress: ${STAGE_LABELS[status]}`}>
    {PIPELINE_STAGES.map((stage, index) => <li key={stage} className={!ended && index < reached ? "is-done" : !ended && index === reached ? "is-current" : ""} aria-current={!ended && index === reached ? "step" : undefined}><i aria-hidden="true" /><span>{stage === "submitted" ? "Applied" : STAGE_LABELS[stage]}</span></li>)}
    {ended && <li className="is-exit"><i aria-hidden="true" /><span>{STAGE_LABELS[status]}</span></li>}
  </ol>;
}

export function CandidateApplications() {
  const [applications, setApplications] = useState<CandidateApplication[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.myApplications(localStorage.getItem("jobbridge_token") ?? "", offset, PAGE_SIZE + 1)
      .then((data) => { if (active) setApplications(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setApplications([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, refresh]);
  const withdraw = async (application: CandidateApplication) => {
    if (busy || !window.confirm(`Withdraw your application for ${application.job_title} at ${application.company_name}? You can register interest again later while the posting is open.`)) return;
    setBusy(application.application_id); setError(null); setNotice(null);
    try {
      const updated = await api.withdrawApplication(application.application_id, localStorage.getItem("jobbridge_token") ?? "");
      setApplications((items) => items.map((item) => item.application_id === updated.application_id ? { ...item, ...updated } : item));
      setNotice(`Application for ${application.job_title} withdrawn.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not withdraw the application."); }
    finally { setBusy(null); }
  };
  // Registering interest again resubmits a withdrawn application while the posting is open.
  const reapply = async (application: CandidateApplication) => {
    if (busy) return;
    setBusy(application.application_id); setError(null); setNotice(null);
    try {
      await api.updateOpportunityStatus(application.job_id, "applied", localStorage.getItem("jobbridge_token") ?? "");
      setNotice(`Application for ${application.job_title} submitted again.`);
      setRefresh((value) => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not apply again."); }
    finally { setBusy(null); }
  };
  return <section className="data-section" aria-label="My applications">
    <div className="page-heading"><h2 className="section-heading"><ClipboardList size={19} />My applications</h2><button className="secondary-button" disabled={loading || busy !== null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Refresh applications</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {loading ? <p role="status">Loading applications...</p> : <div className="workflow-list">{applications.slice(0, PAGE_SIZE).map((application) => <article className="workflow-row" key={application.application_id} aria-label={application.job_title}>
      <div className="workflow-identity"><h3>{application.job_title}</h3><p>{application.company_name} / {application.job_location || "Location not specified"}</p><p>Applied {new Date(application.created_at).toLocaleDateString()} / Updated {new Date(application.updated_at).toLocaleString()}</p><p>Job posting: {application.job_status}</p><ApplicationProgress status={application.status} /></div>{application.status === "hired" ? <strong className="workflow-status-label hired"><BadgeCheck size={16} aria-hidden="true" />Hired</strong> : <strong className={`workflow-status-label ${application.status}`}>{application.status === "interviewed" ? "Interview completed" : application.status}</strong>}{withdrawable.has(application.status) && <button className="secondary-button" disabled={busy !== null} onClick={() => void withdraw(application)}><Undo2 size={16} />Withdraw application</button>}{application.status === "withdrawn" && application.job_status === "open" && <button className="secondary-button" disabled={busy !== null} onClick={() => void reapply(application)}><RotateCcw size={16} />Apply again</button>}
    </article>)}{!applications.length && <p role="status">{error ? "Applications unavailable" : "No applications yet"}</p>}</div>}
    <ListPagination label="applications" offset={offset} hasNext={applications.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </section>;
}