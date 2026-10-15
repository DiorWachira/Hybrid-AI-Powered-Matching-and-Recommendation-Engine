import { useEffect, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, Building2, MapPin, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import { api, type AdminJob, type Applicant, type MatchCandidate } from "../lib/api";
import { ADMIN_PAGE_SIZE, ListPagination } from "../components/ListPagination";

const JOB_PAGE_SIZE = ADMIN_PAGE_SIZE;
const applicantLabel = (value: string) => value.replaceAll("_", " ");

export function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<AdminJob | null>(null);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | "open" | "closed">("");
  const [offset, setOffset] = useState(0);
  const [applicantOffset, setApplicantOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [applicantHasNext, setApplicantHasNext] = useState(false);
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [scores, setScores] = useState<Map<string, MatchCandidate>>(new Map());
  const [evaluatedAt, setEvaluatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [detailRefresh, setDetailRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setLoading(false); setError("Sign in again to view job oversight."); return; }
    setLoading(true);
    setError(null);
    void api.adminJobs(token, search, status, offset, JOB_PAGE_SIZE + 1)
      .then((data) => { if (active) { setJobs(data.slice(0, JOB_PAGE_SIZE)); setHasNext(data.length > JOB_PAGE_SIZE); } })
      .catch((reason: Error) => { if (active) { setError(reason.message); setJobs([]); setHasNext(false); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, status, offset, refresh]);

  useEffect(() => {
    let active = true;
    if (!selectedJob) { setApplicants([]); setScores(new Map()); setEvaluatedAt(null); return; }
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setDetailError("Sign in again to view applicants."); return; }
    setDetailLoading(true);
    setDetailError(null);
    setApplicants([]);
    setApplicantHasNext(false);
    setScores(new Map());
    setEvaluatedAt(null);
    void Promise.allSettled([
      api.jobApplications(selectedJob.job_id, token, applicantOffset, ADMIN_PAGE_SIZE + 1),
      api.savedMatches(selectedJob.job_id, token),
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
      if (failures.length) setDetailError(failures.map((result) => result.status === "rejected" ? result.reason.message : "").join(" "));
    })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedJob?.job_id, applicantOffset, detailRefresh]);

  const changeJobStatus = async () => {
    if (!selectedJob) return;
    const nextStatus: "open" | "closed" = selectedJob.status === "open" ? "closed" : "open";
    if (!window.confirm(`Set ${selectedJob.title} to ${nextStatus}?`)) return;
    setBusy(true);
    setDetailError(null);
    try {
      await api.setJobStatus(localStorage.getItem("jobbridge_token") ?? "", selectedJob.job_id, nextStatus);
      const updated = { ...selectedJob, status: nextStatus };
      setSelectedJob(updated);
      setJobs((items) => items.map((item) => item.job_id === updated.job_id ? updated : item));
      setRefresh((value) => value + 1);
    } catch (reason) { setDetailError(reason instanceof Error ? reason.message : "Job status could not be changed."); }
    finally { setBusy(false); }
  };

  const evaluateAllCandidates = async () => {
    if (!selectedJob) return;
    if (!window.confirm("This evaluates every active candidate in the system for this job, not only applicants. Continue?")) return;
    setBusy(true);
    setDetailError(null);
    try {
      const result = await api.evaluateMatches(selectedJob.job_id, localStorage.getItem("jobbridge_token") ?? "");
      setScores(new Map(result.candidates.map((candidate) => [candidate.candidate_id, candidate])));
      setEvaluatedAt(result.evaluated_at);
    } catch (reason) { setDetailError(reason instanceof Error ? reason.message : "Candidates could not be evaluated."); }
    finally { setBusy(false); }
  };

  const selectedScoreCount = applicants.filter((applicant) => scores.has(applicant.candidate_id)).length;

  return <main className="studio-page admin-jobs-page">
    <div className="page-heading"><div><p className="eyebrow">Administration / oversight</p><h1>Every job. Every applicant.</h1><p>Review postings across employers, then open a role to inspect its applicants and saved scores.</p></div><button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh jobs"}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <section className="data-section" aria-labelledby="admin-job-list-heading">
      <div className="admin-jobs-toolbar"><h2 id="admin-job-list-heading" className="section-heading"><BriefcaseBusiness size={18} />Job postings</h2><form className="admin-jobs-filters" role="search" onSubmit={(event) => { event.preventDefault(); setOffset(0); setSearch(searchText.trim()); }}>
        <label className="search-field"><Search size={16} /><span className="sr-only">Search roles, employers, recruiter emails or skills</span><input type="search" value={searchText} maxLength={120} placeholder="Role, employer, recruiter or skill" onChange={(event) => setSearchText(event.target.value)} /></label>
        <label className="sort-control"><span className="sr-only">Filter job status</span><select value={status} onChange={(event) => { setOffset(0); setStatus(event.target.value as "" | "open" | "closed"); }}><option value="">All statuses</option><option value="open">Open</option><option value="closed">Closed</option></select></label>
        <button className="secondary-button" type="submit" disabled={loading}><Search size={16} />Search</button>
      </form></div>
      <div className="data-table-wrap" aria-busy={loading}><table className="data-table"><thead><tr><th scope="col">Role and employer</th><th scope="col">Location</th><th scope="col">Applicants</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Open job</span></th></tr></thead><tbody>
        {jobs.map((job) => <tr key={job.job_id}><td><strong>{job.title}</strong><div className="admin-job-employer">{job.company_name} · {job.recruiter_email}</div></td><td>{job.location || "Not specified"}</td><td>{job.applicant_count}</td><td><span className={`admin-job-status ${job.status}`}>{job.status}</span></td><td><button className="text-button" onClick={() => { setApplicantOffset(0); setSelectedJob(job); }} aria-label={`Open applicants for ${job.title}`}><Users size={15} />Open</button></td></tr>)}
        {!jobs.length && <tr><td colSpan={5}>{loading ? "Loading job postings..." : error ? "Job postings unavailable" : "No matching job postings"}</td></tr>}
      </tbody></table></div>
      <ListPagination label="job postings" offset={offset} hasNext={hasNext} disabled={loading} onChange={setOffset} />
    </section>

    {selectedJob && <section className="admin-job-detail data-section" aria-labelledby="admin-job-detail-heading" aria-busy={detailLoading}>
      <div className="admin-job-detail-heading"><div><button className="text-button" onClick={() => setSelectedJob(null)}><ArrowLeft size={15} />All jobs</button><p className="eyebrow">{selectedJob.company_name}</p><h2 id="admin-job-detail-heading">{selectedJob.title}</h2><div className="admin-job-facts"><span><MapPin size={15} />{selectedJob.location || "Location not specified"}</span><span><Building2 size={15} />{selectedJob.recruiter_email}</span><span><Users size={15} />{selectedJob.applicant_count} applicants</span><span><ShieldCheck size={15} />{selectedJob.status}</span></div></div><div className="admin-job-detail-actions"><button className="secondary-button" disabled={busy} onClick={changeJobStatus}>{selectedJob.status === "open" ? "Close job" : "Reopen job"}</button><button className="secondary-button" disabled={detailLoading || busy} onClick={() => setDetailRefresh((value) => value + 1)}><RefreshCw size={15} />Refresh details</button></div></div>
      <div className="admin-applicant-heading"><div><h3>Applicants</h3><p>{evaluatedAt ? `Scores from ${new Date(evaluatedAt).toLocaleString()}` : "No saved evaluation for this job."}</p></div><button className="primary-button" disabled={busy || detailLoading} onClick={() => void evaluateAllCandidates()}>Evaluate all candidates</button></div>
      <p className="admin-score-scope">Evaluation includes every active candidate, not only applicants. Viewing this page never starts an evaluation.</p>
      {detailError && <p className="notice error" role="alert">{detailError}</p>}
      <div className="admin-applicant-list">
        {applicants.map((applicant) => {
          const score = scores.get(applicant.candidate_id);
          return <article className="admin-applicant-row" key={applicant.application_id}>
            <div className="admin-applicant-identity"><h4>{applicant.candidate_name}</h4><p>{applicant.candidate_location || "Location not specified"} · {applicant.years_experience} years experience</p><div className="skill-tags">{applicant.skills.map((skill) => <span key={skill}>{skill}</span>)}{applicant.certifications.map((certification) => <span key={certification}>{certification}</span>)}</div></div>
            <div className="admin-applicant-meta"><span>Applied {new Date(applicant.created_at).toLocaleDateString()}</span><span className={`admin-application-status ${applicant.status}`}>{applicantLabel(applicant.status)}</span></div>
            <div className="admin-applicant-score">{score ? <><strong>{Math.round(score.final_score * 100)}%</strong><span>{score.hard_rule_passed ? "Eligible" : "Does not meet criteria"}</span></> : <><strong>—</strong><span>Not scored</span></>}</div>
          </article>;
        })}
        {!applicants.length && <p className="admin-applicant-empty" role="status">{detailLoading ? "Loading applicants..." : detailError ? "Applicants could not be loaded." : "No applicants have applied to this job."}</p>}
      </div>
      {scores.size > 0 && selectedScoreCount < applicants.length && <p className="admin-score-scope">Some applicants do not have a saved score in the latest evaluation.</p>}
      <ListPagination label="applicants" offset={applicantOffset} hasNext={applicantHasNext} disabled={detailLoading || busy} onChange={setApplicantOffset} />
    </section>}
  </main>;
}