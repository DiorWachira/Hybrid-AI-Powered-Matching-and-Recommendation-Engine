import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, BriefcaseBusiness, Building2, MapPin, RefreshCw, Search, ShieldCheck, UserRoundSearch, Users, X } from "lucide-react";
import { api, type AdminJob, type AdminRecruiter, type Applicant, type MatchCandidate, type OversightSummary } from "../lib/api";
import { ADMIN_PAGE_SIZE, ListPagination } from "../components/ListPagination";

const DEFAULT_STALE_DAYS = 14;
const DAY_MS = 86_400_000;
const applicantLabel = (value: string) => value.replaceAll("_", " ");
const daysSince = (value: string | null) => value ? Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / DAY_MS)) : null;
const ageLabel = (value: string | null) => { const days = daysSince(value); return days == null ? "Unknown" : days === 0 ? "Today" : days === 1 ? "1 day ago" : `${days} days ago`; };
const token = () => localStorage.getItem("jobbridge_token");

export function RecruiterOversightPage() {
  const [params] = useSearchParams();
  const jobsSection = useRef<HTMLElement>(null);
  const [summary, setSummary] = useState<OversightSummary | null>(null);
  const [recruiters, setRecruiters] = useState<AdminRecruiter[]>([]);
  const [recruiterSearchText, setRecruiterSearchText] = useState("");
  const [recruiterSearch, setRecruiterSearch] = useState("");
  const [recruiterOffset, setRecruiterOffset] = useState(0);
  const [recruitersLoading, setRecruitersLoading] = useState(true);
  const [recruiterError, setRecruiterError] = useState<string | null>(null);
  const [recruiter, setRecruiter] = useState<AdminRecruiter | null>(null);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<AdminJob | null>(null);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | "open" | "closed">("");
  const [attention, setAttention] = useState(params.get("attention") === "1");
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const staleDays = summary?.stale_after_days ?? DEFAULT_STALE_DAYS;

  useEffect(() => {
    let active = true;
    const session = token();
    if (!session) return;
    void api.oversightSummary(session).then((data) => { if (active) setSummary(data); }).catch(() => { if (active) setSummary(null); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    const session = token();
    if (!session) { setRecruitersLoading(false); setRecruiterError("Sign in again to view recruiters."); return; }
    setRecruitersLoading(true);
    setRecruiterError(null);
    void api.adminRecruiters(session, recruiterSearch, recruiterOffset, ADMIN_PAGE_SIZE + 1)
      .then((data) => { if (active) setRecruiters(data); })
      .catch((reason: Error) => { if (active) { setRecruiterError(reason.message); setRecruiters([]); } })
      .finally(() => { if (active) setRecruitersLoading(false); });
    return () => { active = false; };
  }, [recruiterSearch, recruiterOffset, refresh]);

  useEffect(() => {
    let active = true;
    const session = token();
    if (!session) { setLoading(false); setError("Sign in again to view job oversight."); return; }
    setLoading(true);
    setError(null);
    void api.adminJobs(session, { search, status, employerId: recruiter?.employer_id, attention }, offset, ADMIN_PAGE_SIZE + 1)
      .then((data) => { if (active) { setJobs(data.slice(0, ADMIN_PAGE_SIZE)); setHasNext(data.length > ADMIN_PAGE_SIZE); } })
      .catch((reason: Error) => { if (active) { setError(reason.message); setJobs([]); setHasNext(false); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, status, attention, recruiter?.employer_id, offset, refresh]);

  const focusRecruiter = (next: AdminRecruiter | null) => {
    setRecruiter(next); setSelectedJob(null); setOffset(0);
    jobsSection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const toggleAttention = () => { setAttention((value) => !value); setSelectedJob(null); setOffset(0); };
  const jobUpdated = (updated: AdminJob) => {
    setSelectedJob(updated);
    setJobs((items) => items.map((item) => item.job_id === updated.job_id ? updated : item));
    setRefresh((value) => value + 1);
  };

  const stats: Array<[string, string | number, string?]> = [
    ["Recruiters", summary ? `${summary.active_recruiters_count} / ${summary.recruiters_count}` : "—", "active / total"],
    ["Open postings", summary?.jobs_open ?? "—"],
    ["Closed postings", summary?.jobs_closed ?? "—"],
    ["Applications", summary?.applications_total ?? "—"],
    ["Hires", summary?.hired_total ?? "—"],
  ];

  return <main className="studio-page admin-jobs-page">
    <div className="page-heading"><div><p className="eyebrow">Administration / recruiter oversight</p><h1>Every recruiter. Every posting.</h1><p>See who is hiring, what they have posted and which roles need an administrator's attention.</p></div><button className="secondary-button" disabled={loading || recruitersLoading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading || recruitersLoading ? "Refreshing..." : "Refresh"}</button></div>

    <section className="oversight-stats" aria-label="Recruitment totals">
      {stats.map(([label, value, hint]) => <div key={label}><span>{label}</span><strong>{value}</strong>{hint && <small>{hint}</small>}</div>)}
      <button type="button" className={`oversight-attention ${summary?.attention_jobs ? "has-items" : ""}`} aria-pressed={attention} onClick={toggleAttention}>
        <span><AlertTriangle size={14} />Needs attention</span><strong>{summary?.attention_jobs ?? "—"}</strong>
        <small>{summary ? `${summary.stale_open_jobs} without applicants after ${staleDays} days · ${summary.suspended_open_jobs} from suspended recruiters` : "Open roles to review"}</small>
      </button>
    </section>

    <section className="data-section" aria-labelledby="recruiter-roster-heading">
      <div className="admin-jobs-toolbar"><h2 id="recruiter-roster-heading" className="section-heading"><UserRoundSearch size={18} />Recruiters</h2><form className="admin-jobs-filters" role="search" onSubmit={(event) => { event.preventDefault(); setRecruiterOffset(0); setRecruiterSearch(recruiterSearchText.trim()); }}>
        <label className="search-field"><Search size={16} /><span className="sr-only">Search recruiters by company, contact or email</span><input type="search" value={recruiterSearchText} maxLength={120} placeholder="Company, contact or email" onChange={(event) => setRecruiterSearchText(event.target.value)} /></label>
        <button className="secondary-button" type="submit" disabled={recruitersLoading}><Search size={16} />Search</button>
      </form></div>
      {recruiterError && <p className="notice error" role="alert">{recruiterError}</p>}
      <div className="data-table-wrap" aria-busy={recruitersLoading}><table className="data-table"><thead><tr><th scope="col">Recruiter</th><th scope="col">Open / total</th><th scope="col">Applicants</th><th scope="col">Hires</th><th scope="col">Last posted</th><th scope="col"><span className="sr-only">Postings</span></th></tr></thead><tbody>
        {recruiters.slice(0, ADMIN_PAGE_SIZE).map((item) => <tr key={item.employer_id} className={recruiter?.employer_id === item.employer_id ? "is-selected" : undefined}>
          <td><strong>{item.company_name}</strong><div className="admin-job-employer">{item.contact_name ? `${item.contact_name} · ` : ""}{item.email}</div><div className="oversight-flags">{!item.is_active && <span className="oversight-flag warn">Suspended</span>}{item.is_demo && <span className="oversight-flag">Demo</span>}{item.stale_open_jobs > 0 && <span className="oversight-flag warn">{item.stale_open_jobs} without applicants</span>}</div></td>
          <td>{item.jobs_open} / {item.jobs_total}</td><td>{item.applications_total}</td><td>{item.hired_total}</td><td>{ageLabel(item.last_posted_at)}</td>
          <td><button className="text-button" disabled={!item.jobs_total} onClick={() => focusRecruiter(item)} aria-label={`View postings by ${item.company_name}`}><BriefcaseBusiness size={15} />Postings</button></td>
        </tr>)}
        {!recruiters.length && <tr><td colSpan={6}>{recruitersLoading ? "Loading recruiters..." : recruiterError ? "Recruiters unavailable" : "No matching recruiters"}</td></tr>}
      </tbody></table></div>
      <ListPagination label="recruiters" offset={recruiterOffset} hasNext={recruiters.length > ADMIN_PAGE_SIZE} disabled={recruitersLoading} onChange={setRecruiterOffset} />
    </section>

    <section ref={jobsSection} className="data-section" aria-labelledby="admin-job-list-heading">
      <div className="admin-jobs-toolbar"><h2 id="admin-job-list-heading" className="section-heading"><BriefcaseBusiness size={18} />{recruiter ? `Postings by ${recruiter.company_name}` : "All postings"}</h2><form className="admin-jobs-filters" role="search" onSubmit={(event) => { event.preventDefault(); setOffset(0); setSearch(searchText.trim()); }}>
        <label className="search-field"><Search size={16} /><span className="sr-only">Search roles, employers, recruiter emails or skills</span><input type="search" value={searchText} maxLength={120} placeholder="Role, employer, recruiter or skill" onChange={(event) => setSearchText(event.target.value)} /></label>
        <label className="sort-control"><span className="sr-only">Filter job status</span><select value={status} onChange={(event) => { setOffset(0); setStatus(event.target.value as "" | "open" | "closed"); }}><option value="">All statuses</option><option value="open">Open</option><option value="closed">Closed</option></select></label>
        <label className="sort-control"><input type="checkbox" checked={attention} onChange={toggleAttention} />Needs attention</label>
        <button className="secondary-button" type="submit" disabled={loading}><Search size={16} />Search</button>
      </form></div>
      {recruiter && <p className="oversight-scope"><span>Showing postings by <strong>{recruiter.company_name}</strong> ({recruiter.email})</span><button className="text-button" onClick={() => focusRecruiter(null)}><X size={14} />Show all recruiters</button></p>}
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="data-table-wrap" aria-busy={loading}><table className="data-table"><thead><tr><th scope="col">Role and employer</th><th scope="col">Location</th><th scope="col">Posted</th><th scope="col">Applicants</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Open job</span></th></tr></thead><tbody>
        {jobs.map((job) => {
          const stale = job.status === "open" && job.applicant_count === 0 && (daysSince(job.posted_at) ?? 0) >= staleDays;
          return <tr key={job.job_id}><td><strong>{job.title}</strong><div className="admin-job-employer">{job.company_name} · {job.recruiter_email}</div>{job.status === "open" && (!job.recruiter_active || stale) && <div className="oversight-flags">{!job.recruiter_active && <span className="oversight-flag warn">Recruiter suspended</span>}{stale && <span className="oversight-flag warn">No applicants yet</span>}</div>}</td><td>{job.location || "Not specified"}</td><td>{ageLabel(job.posted_at)}</td><td>{job.applicant_count}</td><td><span className={`admin-job-status ${job.status}`}>{job.status}</span></td><td><button className="text-button" onClick={() => setSelectedJob(job)} aria-label={`Open applicants for ${job.title}`}><Users size={15} />Open</button></td></tr>;
        })}
        {!jobs.length && <tr><td colSpan={6}>{loading ? "Loading job postings..." : error ? "Job postings unavailable" : attention ? "Nothing needs attention right now" : "No matching job postings"}</td></tr>}
      </tbody></table></div>
      <ListPagination label="job postings" offset={offset} hasNext={hasNext} disabled={loading} onChange={setOffset} />
    </section>

    {selectedJob && <JobOversightDetail key={selectedJob.job_id} job={selectedJob} onBack={() => setSelectedJob(null)} onUpdated={jobUpdated} />}
  </main>;
}

function JobOversightDetail({ job, onBack, onUpdated }: { job: AdminJob; onBack: () => void; onUpdated: (job: AdminJob) => void }) {
  const [applicantOffset, setApplicantOffset] = useState(0);
  const [applicantHasNext, setApplicantHasNext] = useState(false);
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [scores, setScores] = useState<Map<string, MatchCandidate>>(new Map());
  const [evaluatedAt, setEvaluatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    const session = token();
    if (!session) { setError("Sign in again to view applicants."); return; }
    setLoading(true);
    setError(null);
    setApplicants([]);
    setApplicantHasNext(false);
    setScores(new Map());
    setEvaluatedAt(null);
    void Promise.allSettled([
      api.jobApplications(job.job_id, session, applicantOffset, ADMIN_PAGE_SIZE + 1),
      api.savedMatches(job.job_id, session),
    ]).then(([applicationResult, evaluationResult]) => {
      if (!active) return;
      if (applicationResult.status === "fulfilled") {
        setApplicants(applicationResult.value.slice(0, ADMIN_PAGE_SIZE));
        setApplicantHasNext(applicationResult.value.length > ADMIN_PAGE_SIZE);
      }
      if (evaluationResult.status === "fulfilled") {
        setScores(new Map(evaluationResult.value.candidates.map((candidate) => [candidate.candidate_id, candidate])));
        setEvaluatedAt(evaluationResult.value.evaluated_at);
      }
      const failures = [applicationResult, evaluationResult].filter((result) => result.status === "rejected");
      if (failures.length) setError(failures.map((result) => result.status === "rejected" ? result.reason.message : "").join(" "));
    })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [job.job_id, applicantOffset, refresh]);

  const changeJobStatus = async () => {
    const nextStatus: "open" | "closed" = job.status === "open" ? "closed" : "open";
    if (!window.confirm(`Set ${job.title} to ${nextStatus}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.setJobStatus(token() ?? "", job.job_id, nextStatus);
      onUpdated({ ...job, status: nextStatus });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Job status could not be changed."); }
    finally { setBusy(false); }
  };

  const evaluateAllCandidates = async () => {
    if (!window.confirm("This evaluates every active candidate in the system for this job, not only applicants. Continue?")) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.evaluateMatches(job.job_id, token() ?? "");
      setScores(new Map(result.candidates.map((candidate) => [candidate.candidate_id, candidate])));
      setEvaluatedAt(result.evaluated_at);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Candidates could not be evaluated."); }
    finally { setBusy(false); }
  };

  const selectedScoreCount = applicants.filter((applicant) => scores.has(applicant.candidate_id)).length;

  return <section className="admin-job-detail data-section" aria-labelledby="admin-job-detail-heading" aria-busy={loading}>
    <div className="admin-job-detail-heading"><div><button className="text-button" onClick={onBack}><ArrowLeft size={15} />All jobs</button><p className="eyebrow">{job.company_name}</p><h2 id="admin-job-detail-heading">{job.title}</h2><div className="admin-job-facts"><span><MapPin size={15} />{job.location || "Location not specified"}</span><span><Building2 size={15} />{job.recruiter_email}{!job.recruiter_active && " (suspended)"}</span><span><Users size={15} />{job.applicant_count} applicants</span><span><ShieldCheck size={15} />{job.status}</span></div></div><div className="admin-job-detail-actions"><button className="secondary-button" disabled={busy} onClick={changeJobStatus}>{job.status === "open" ? "Close job" : "Reopen job"}</button><button className="secondary-button" disabled={loading || busy} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={15} />Refresh details</button></div></div>
    {job.status === "open" && !job.recruiter_active && <p className="notice error" role="status"><AlertTriangle size={16} />This recruiter is suspended but the role is still open to candidates. Consider closing it.</p>}
    <div className="admin-applicant-heading"><div><h3>Applicants</h3><p>{evaluatedAt ? `Scores from ${new Date(evaluatedAt).toLocaleString()}` : "No saved evaluation for this job."}</p></div><button className="primary-button" disabled={busy || loading} onClick={() => void evaluateAllCandidates()}>Evaluate all candidates</button></div>
    <p className="admin-score-scope">Evaluation includes every active candidate, not only applicants. Viewing this page never starts an evaluation.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="admin-applicant-list">
      {applicants.map((applicant) => {
        const score = scores.get(applicant.candidate_id);
        return <article className="admin-applicant-row" key={applicant.application_id}>
          <div className="admin-applicant-identity"><h4>{applicant.candidate_name}</h4><p>{applicant.candidate_location || "Location not specified"} · {applicant.years_experience} years experience</p><div className="skill-tags">{applicant.skills.map((skill) => <span key={skill}>{skill}</span>)}{applicant.certifications.map((certification) => <span key={certification}>{certification}</span>)}</div></div>
          <div className="admin-applicant-meta"><span>Applied {new Date(applicant.created_at).toLocaleDateString()}</span><span className={`admin-application-status ${applicant.status}`}>{applicantLabel(applicant.status)}</span></div>
          <div className="admin-applicant-score">{score ? <><strong>{Math.round(score.final_score * 100)}%</strong><span>{score.hard_rule_passed ? "Eligible" : "Does not meet criteria"}</span></> : <><strong>—</strong><span>Not scored</span></>}</div>
        </article>;
      })}
      {!applicants.length && <p className="admin-applicant-empty" role="status">{loading ? "Loading applicants..." : error ? "Applicants could not be loaded." : "No applicants have applied to this job."}</p>}
    </div>
    {scores.size > 0 && selectedScoreCount < applicants.length && <p className="admin-score-scope">Some applicants do not have a saved score in the latest evaluation.</p>}
    <ListPagination label="applicants" offset={applicantOffset} hasNext={applicantHasNext} disabled={loading || busy} onChange={setApplicantOffset} />
  </section>;
}
