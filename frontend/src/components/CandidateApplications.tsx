import { useEffect, useState } from "react";
import { ClipboardList, RefreshCw } from "lucide-react";
import { api, type CandidateApplication } from "../lib/api";
import { ADMIN_PAGE_SIZE as PAGE_SIZE, ListPagination } from "./ListPagination";

export function CandidateApplications() {
  const [applications, setApplications] = useState<CandidateApplication[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.myApplications(localStorage.getItem("jobbridge_token") ?? "", offset, PAGE_SIZE + 1)
      .then((data) => { if (active) setApplications(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setApplications([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, refresh]);
  return <section className="data-section" aria-label="My applications">
    <div className="page-heading"><h2 className="section-heading"><ClipboardList size={19} />My applications</h2><button className="secondary-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Refresh applications</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Loading applications...</p> : <div className="workflow-list">{applications.slice(0, PAGE_SIZE).map((application) => <article className="workflow-row" key={application.application_id} aria-label={application.job_title}>
      <div className="workflow-identity"><h3>{application.job_title}</h3><p>{application.company_name} / {application.job_location || "Location not specified"}</p><p>Applied {new Date(application.created_at).toLocaleDateString()} / Updated {new Date(application.updated_at).toLocaleString()}</p><p>Job posting: {application.job_status}</p></div><strong className="workflow-status-label">{application.status}</strong>
    </article>)}{!applications.length && <p role="status">{error ? "Applications unavailable" : "No applications yet"}</p>}</div>}
    <ListPagination label="applications" offset={offset} hasNext={applications.length > PAGE_SIZE} disabled={loading} onChange={setOffset} />
  </section>;
}