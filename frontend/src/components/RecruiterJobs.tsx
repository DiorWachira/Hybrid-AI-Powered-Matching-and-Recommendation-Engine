import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, BadgeCheck, BriefcaseBusiness, Inbox, Pencil, RefreshCw, Target, Users } from "lucide-react";
import { api, type Applicant, type ApplicationStatus, type JobPosting, type RecruiterPipeline, type RecruiterStatus } from "../lib/api";
import { ADMIN_PAGE_SIZE as PAGE_SIZE, ListPagination } from "./ListPagination";
import { StageBar } from "./Insights";

const transitions: Record<ApplicationStatus, RecruiterStatus[]> = {
  submitted: ["reviewing", "shortlisted", "rejected"], reviewing: ["shortlisted", "rejected"],
  shortlisted: ["interviewed", "rejected"], interviewed: ["hired", "rejected"], rejected: [], hired: [], withdrawn: [],
};
const statusLabels: Record<ApplicationStatus, string> = {
  submitted: "Submitted", reviewing: "Reviewing", shortlisted: "Shortlisted", interviewed: "Interview completed", rejected: "Rejected", hired: "Hired", withdrawn: "Withdrawn",
};
const actionLabels: Record<RecruiterStatus, string> = {
  reviewing: "Start review", shortlisted: "Shortlist for interview", interviewed: "Confirm interview completed", hired: "Confirm hire", rejected: "Reject",
};

export function RecruiterJobs({ onEdit }: { onEdit: (job: JobPosting) => void }) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<JobPosting | null>(null);
  const [pipeline, setPipeline] = useState<RecruiterPipeline | null>(null);
  useEffect(() => {
    let active = true;
    // The summary is supplementary: postings still list if it fails.
    void api.recruiterPipeline(localStorage.getItem("jobbridge_token") ?? "").then((data) => { if (active) setPipeline(data); }).catch(() => { if (active) setPipeline(null); });
    return () => { active = false; };
  }, [refresh]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.myJobs(localStorage.getItem("jobbridge_token") ?? "", offset, PAGE_SIZE + 1)
      .then((data) => { if (active) setJobs(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setJobs([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, refresh]);
  const changeStatus = async (job: JobPosting, status: "open" | "closed") => {
    if (busy || !window.confirm(`${status === "closed" ? "Close" : "Reopen"} ${job.title}?`)) return;
    setBusy(job.job_id); setError(null);
    try {
      const updated = await api.changeOwnJobStatus(job.job_id, status, localStorage.getItem("jobbridge_token") ?? "");
      setJobs((items) => items.map((item) => item.job_id === updated.job_id ? updated : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not change job status."); }
    finally { setBusy(null); }
  };
  const totals = pipeline?.applications_by_status ?? {};
  const inPlay = (totals.submitted ?? 0) + (totals.reviewing ?? 0) + (totals.shortlisted ?? 0) + (totals.interviewed ?? 0);
  const summary: Array<[string, number | string, string]> = [
    ["Open postings", pipeline?.jobs_open ?? "—", pipeline ? `${pipeline.jobs_closed} closed` : ""],
    ["Awaiting review", totals.submitted ?? 0, "new applications"],
    ["In progress", inPlay, `${(totals.shortlisted ?? 0) + (totals.interviewed ?? 0)} at interview stage`],
    ["Hired", totals.hired ?? 0, `${totals.rejected ?? 0} rejected · ${totals.withdrawn ?? 0} withdrawn`],
  ];
  if (selected) return <ApplicationPipeline key={selected.job_id} job={selected} counts={pipeline?.jobs[selected.job_id] ?? {}} onBack={() => { setSelected(null); setRefresh((value) => value + 1); }} onJobChanged={(updated) => { setSelected(updated); setJobs((items) => items.map((item) => item.job_id === updated.job_id ? updated : item)); }} />;
  return <section className="data-section" aria-label="My postings">
    <div className="kpi-grid recruiter-kpis" aria-label="Hiring summary">{summary.map(([label, value, detail]) => <article className={`kpi-tile ${label === "Awaiting review" && Number(value) > 0 ? "is-highlight" : ""}`} key={label}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>)}</div>
    <div className="page-heading"><h2 className="section-heading"><BriefcaseBusiness size={19} />My postings</h2><button className="secondary-button" disabled={loading || busy !== null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Refresh postings</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Loading postings...</p> : <div className="workflow-list">{jobs.slice(0, PAGE_SIZE).map((job) => <article className="workflow-row" key={job.job_id} aria-label={job.title}>
      <div className="workflow-identity"><h3>{job.title}</h3><p>{job.location || "Location not specified"} / {job.required_experience_years}+ years</p><p>{job.posted_at ? `Posted ${new Date(job.posted_at).toLocaleDateString()}` : "Posting date unavailable"} · <span className={`admin-job-status ${job.status}`}>{job.status}</span></p>{pipeline && <StageBar counts={pipeline.jobs[job.job_id] ?? {}} />}</div>
      <div className="workflow-actions"><label className="studio-field">Status<select aria-label={`Job status for ${job.title}`} value={job.status} disabled={busy !== null} onChange={(event) => void changeStatus(job, event.target.value as "open" | "closed")}><option value="open">Open</option><option value="closed">Closed</option></select></label><button className="secondary-button" disabled={busy !== null} onClick={() => onEdit(job)}><Pencil size={16} />Edit</button><button className="secondary-button" disabled={busy !== null} onClick={() => setSelected(job)}>{pipeline?.jobs[job.job_id]?.submitted ? <><Inbox size={16} />Review {pipeline.jobs[job.job_id].submitted} new</> : <><Users size={16} />Applicants</>}</button><button className="icon-button" title={`Match analysis for ${job.title}`} aria-label={`Match analysis for ${job.title}`} disabled={busy !== null} onClick={() => { localStorage.setItem("jobbridge_job_id", job.job_id); localStorage.removeItem("jobbridge_active_job"); navigate("/matches"); }}><Target size={17} /></button></div>
    </article>)}{!jobs.length && <p role="status">{error ? "Postings unavailable" : "No job postings yet"}</p>}</div>}
    <ListPagination label="postings" offset={offset} hasNext={jobs.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </section>;
}

function ApplicationPipeline({ job, counts: initialCounts, onBack, onJobChanged }: { job: JobPosting; counts: RecruiterPipeline["jobs"][string]; onBack: () => void; onJobChanged: (job: JobPosting) => void }) {
  const [applications, setApplications] = useState<Applicant[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Set after a hire on an open posting, so the recruiter decides whether to keep recruiting.
  const [hiredName, setHiredName] = useState<string | null>(null);
  const [counts, setCounts] = useState(initialCounts);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.jobApplications(job.job_id, localStorage.getItem("jobbridge_token") ?? "", offset, PAGE_SIZE + 1)
      .then((data) => { if (active) setApplications(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setApplications([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [job.job_id, offset, refresh]);
  const changeStatus = async (application: Applicant, status: RecruiterStatus) => {
    if (busy || !window.confirm(`${actionLabels[status]} for ${application.candidate_name}?`)) return;
    setBusy(application.application_id); setError(null); setNotice(null); setHiredName(null);
    try {
      const updated = await api.changeApplicationStatus(job.job_id, application.application_id, status, localStorage.getItem("jobbridge_token") ?? "");
      setApplications((items) => items.map((item) => item.application_id === updated.application_id ? { ...item, ...updated } : item));
      setCounts((current) => ({ ...current, [application.status]: Math.max(0, (current[application.status] ?? 0) - 1), [updated.status]: (current[updated.status] ?? 0) + 1 }));
      setNotice(`${application.candidate_name}: ${statusLabels[updated.status]}.`);
      if (updated.status === "hired" && job.status === "open") setHiredName(application.candidate_name);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update application."); }
    finally { setBusy(null); }
  };
  const decidePosting = async (close: boolean) => {
    if (busy) return;
    if (!close) { setHiredName(null); setNotice("Posting kept open for more candidates."); return; }
    setBusy(job.job_id); setError(null);
    try {
      onJobChanged(await api.changeOwnJobStatus(job.job_id, "closed", localStorage.getItem("jobbridge_token") ?? ""));
      setHiredName(null); setNotice("Posting closed. It no longer accepts applications.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not close the posting."); }
    finally { setBusy(null); }
  };
  return <section className="data-section" aria-label="Applicant pipeline">
    <div className="page-heading"><div><h2>{job.title}</h2><p>Applicant pipeline / Posting {job.status}</p></div><div className="workflow-actions"><button className="secondary-button" disabled={busy !== null} onClick={onBack}><ArrowLeft size={16} />Back to postings</button><button className="icon-button" title="Refresh applicants" aria-label="Refresh applicants" disabled={loading || busy !== null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button></div></div>
    <StageBar counts={counts} />
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {hiredName && <div className="hire-decision" role="region" aria-label="Posting decision"><BadgeCheck size={20} /><div><h3>{hiredName} hired</h3><p>Close this posting if you are not recruiting further, or keep it open to consider more candidates.</p></div><div className="workflow-actions"><button className="primary-button" disabled={busy !== null} onClick={() => void decidePosting(true)}>Close posting</button><button className="secondary-button" disabled={busy !== null} onClick={() => void decidePosting(false)}>Keep open</button></div></div>}
    {loading ? <p role="status">Loading applicants...</p> : <div className="workflow-list">{applications.slice(0, PAGE_SIZE).map((application) => <article className="workflow-row" key={application.application_id} aria-label={application.candidate_name}>
      <div className="workflow-identity"><h3>{application.candidate_name}</h3><p>{application.candidate_location || "Location not specified"} / {application.years_experience} years experience</p><p>Applied {new Date(application.created_at).toLocaleDateString()} / Updated {new Date(application.updated_at).toLocaleString()}</p><details><summary>Skills and qualifications</summary><div className="skill-tags">{application.skills.length ? application.skills.map((skill) => <span key={skill}>{skill}</span>) : "No skills recorded"}</div><p>Certifications: {application.certifications.join(", ") || "None recorded"}</p></details></div>
      <label className="studio-field workflow-status">Application status<select aria-label={`Application status for ${application.candidate_name}`} value={application.status} disabled={busy !== null || !transitions[application.status].length} onChange={(event) => void changeStatus(application, event.target.value as RecruiterStatus)}><option value={application.status}>{statusLabels[application.status]}</option>{transitions[application.status].map((status) => <option key={status} value={status}>{actionLabels[status]}</option>)}</select></label>
    </article>)}{!applications.length && <p role="status">{error ? "Applications unavailable" : "No applications for this role yet"}</p>}</div>}
    <ListPagination label="applicants" offset={offset} hasNext={applications.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </section>;
}