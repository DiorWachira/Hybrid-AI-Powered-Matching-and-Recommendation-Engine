import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, BriefcaseBusiness, Pencil, RefreshCw, Target, Users } from "lucide-react";
import { api, type Applicant, type ApplicationStatus, type JobPosting, type RecruiterStatus } from "../lib/api";
import { ADMIN_PAGE_SIZE as PAGE_SIZE, ListPagination } from "./ListPagination";

const transitions: Record<ApplicationStatus, RecruiterStatus[]> = {
  submitted: ["reviewing", "shortlisted", "rejected"], reviewing: ["shortlisted", "rejected"],
  shortlisted: ["hired", "rejected"], rejected: [], hired: [], withdrawn: [],
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
  if (selected) return <ApplicationPipeline key={selected.job_id} job={selected} onBack={() => setSelected(null)} />;
  return <section className="data-section" aria-label="My postings">
    <div className="page-heading"><h2 className="section-heading"><BriefcaseBusiness size={19} />My postings</h2><button className="secondary-button" disabled={loading || busy !== null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Refresh postings</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Loading postings...</p> : <div className="workflow-list">{jobs.slice(0, PAGE_SIZE).map((job) => <article className="workflow-row" key={job.job_id} aria-label={job.title}>
      <div className="workflow-identity"><h3>{job.title}</h3><p>{job.location || "Location not specified"} / {job.required_experience_years}+ years</p><p>{job.posted_at ? `Posted ${new Date(job.posted_at).toLocaleDateString()}` : "Posting date unavailable"}</p></div>
      <div className="workflow-actions"><label className="studio-field">Status<select aria-label={`Job status for ${job.title}`} value={job.status} disabled={busy !== null} onChange={(event) => void changeStatus(job, event.target.value as "open" | "closed")}><option value="open">Open</option><option value="closed">Closed</option></select></label><button className="secondary-button" disabled={busy !== null} onClick={() => onEdit(job)}><Pencil size={16} />Edit</button><button className="secondary-button" disabled={busy !== null} onClick={() => setSelected(job)}><Users size={16} />Applicants</button><button className="icon-button" title={`Match analysis for ${job.title}`} aria-label={`Match analysis for ${job.title}`} disabled={busy !== null} onClick={() => { localStorage.setItem("jobbridge_job_id", job.job_id); localStorage.removeItem("jobbridge_active_job"); navigate("/matches"); }}><Target size={17} /></button></div>
    </article>)}{!jobs.length && <p role="status">{error ? "Postings unavailable" : "No job postings yet"}</p>}</div>}
    <ListPagination label="postings" offset={offset} hasNext={jobs.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </section>;
}

function ApplicationPipeline({ job, onBack }: { job: JobPosting; onBack: () => void }) {
  const [applications, setApplications] = useState<Applicant[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
    if (busy || !window.confirm(`Move ${application.candidate_name}'s application to ${status}?`)) return;
    setBusy(application.application_id); setError(null); setNotice(null);
    try {
      const updated = await api.changeApplicationStatus(job.job_id, application.application_id, status, localStorage.getItem("jobbridge_token") ?? "");
      setApplications((items) => items.map((item) => item.application_id === updated.application_id ? { ...item, ...updated } : item));
      setNotice(`Application updated to ${updated.status}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update application."); }
    finally { setBusy(null); }
  };
  return <section className="data-section" aria-label="Applicant pipeline">
    <div className="page-heading"><div><h2>{job.title}</h2><p>Applicant pipeline</p></div><div className="workflow-actions"><button className="secondary-button" disabled={busy !== null} onClick={onBack}><ArrowLeft size={16} />Back to postings</button><button className="icon-button" title="Refresh applicants" aria-label="Refresh applicants" disabled={loading || busy !== null} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button></div></div>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {loading ? <p role="status">Loading applicants...</p> : <div className="workflow-list">{applications.slice(0, PAGE_SIZE).map((application) => <article className="workflow-row" key={application.application_id} aria-label={application.candidate_name}>
      <div className="workflow-identity"><h3>{application.candidate_name}</h3><p>{application.candidate_location || "Location not specified"} / {application.years_experience} years experience</p><p>Applied {new Date(application.created_at).toLocaleDateString()} / Updated {new Date(application.updated_at).toLocaleString()}</p><details><summary>Skills and qualifications</summary><div className="skill-tags">{application.skills.length ? application.skills.map((skill) => <span key={skill}>{skill}</span>) : "No skills recorded"}</div><p>Certifications: {application.certifications.join(", ") || "None recorded"}</p></details></div>
      <label className="studio-field workflow-status">Application status<select aria-label={`Application status for ${application.candidate_name}`} value={application.status} disabled={busy !== null || !transitions[application.status].length} onChange={(event) => void changeStatus(application, event.target.value as RecruiterStatus)}><option value={application.status}>{application.status}</option>{transitions[application.status].map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
    </article>)}{!applications.length && <p role="status">{error ? "Applications unavailable" : "No applications for this role yet"}</p>}</div>}
    <ListPagination label="applicants" offset={offset} hasNext={applications.length > PAGE_SIZE} disabled={loading || busy !== null} onChange={setOffset} />
  </section>;
}