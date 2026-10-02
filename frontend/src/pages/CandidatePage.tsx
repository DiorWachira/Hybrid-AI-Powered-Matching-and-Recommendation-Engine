import { useEffect, useRef, useState, type CSSProperties } from "react";
import { ArrowUpRight, Bookmark, BriefcaseBusiness, Check, CircleAlert, Clock3, FileText, MapPin, RefreshCw, Search, SlidersHorizontal, Sparkles, UploadCloud } from "lucide-react";
import { api, type CandidateDashboard, type Opportunity } from "../lib/api";

const tabs = [
  { id: "for-you", label: "For you", icon: Sparkles },
  { id: "all", label: "All opportunities", icon: BriefcaseBusiness },
  { id: "history", label: "My activity", icon: Clock3 },
  { id: "resume", label: "My resume", icon: FileText },
] as const;
type Tab = typeof tabs[number]["id"];
const percentage = (score: number) => Math.round(Math.max(0, Math.min(1, score)) * 100);

export function CandidatePage() {
  const input = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<Tab>("for-you");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("match");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dashboard, setDashboard] = useState<CandidateDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { setLoading(false); setError("Sign in again to load your opportunities."); return; }
    void api.candidateDashboard(token).then((data) => { if (active) setDashboard(data); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);

  const selectFile = (next: File | undefined) => {
    if (!next) return;
    setFile(null);
    if (!/\.(pdf|docx)$/i.test(next.name) || next.size > 10 * 1024 * 1024 || next.size === 0) {
      setMessage("Choose a non-empty PDF or DOCX file under 10 MB."); return;
    }
    setFile(next); setMessage(null);
  };

  const upload = async () => {
    const token = localStorage.getItem("jobbridge_token");
    if (!file || !token || uploading) return;
    setUploading(true); setMessage(null);
    try {
      const profile = await api.uploadResume(file, token);
      setMessage(`Resume saved. ${profile.skills.length} skills identified.`);
      setReload((value) => value + 1);
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Upload failed. Please try again."); }
    finally { setUploading(false); }
  };

  const updateOpportunity = async (jobId: string, status: "saved" | "applied") => {
    const token = localStorage.getItem("jobbridge_token");
    if (!token || busyId) return;
    setBusyId(jobId); setError(null);
    try {
      const updated = await api.updateOpportunityStatus(jobId, status, token);
      setDashboard((current) => current ? {
        available_opportunities: current.available_opportunities.map((job) => job.job_id === jobId ? updated : job),
        for_you: current.for_you.map((job) => job.job_id === jobId ? updated : job),
        history: [updated, ...current.history.filter((job) => job.job_id !== jobId)],
      } : current);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save your activity."); }
    finally { setBusyId(null); }
  };

  const collection = tab === "history" ? dashboard?.history : tab === "all" ? dashboard?.available_opportunities : dashboard?.for_you;
  const filtered = (collection ?? []).filter((job) => `${job.title} ${job.company_name} ${job.location ?? ""} ${job.required_skills.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  const visible = [...filtered].sort((first, second) => sort === "salary" ? Number(second.salary_range_max ?? 0) - Number(first.salary_range_max ?? 0) : sort === "title" ? first.title.localeCompare(second.title) : second.match_score - first.match_score);
  const saved = dashboard?.history.filter((job) => job.status === "saved").length;
  const applied = dashboard?.history.filter((job) => job.status === "applied").length;

  return (
    <main className="studio-page">
      <div className="page-heading"><div><p className="eyebrow">Your next chapter</p><h1>Opportunity, with direction.</h1><p>A closer look at the roles that could come next.</p></div><button className="secondary-button" onClick={() => setTab("resume")}><UploadCloud size={16} />Update resume</button></div>
      <section className="opportunity-banner" aria-label="Career workspace">
        <img src="/media/workspace.jpg" alt="A sunlit shared workspace with desks and greenery" />
        <div><span className="eyebrow">JobBridge / Discover</span><h2>Find your place.<br />Build what comes next.</h2><p>Your skills. A new perspective on opportunity.</p></div>
      </section>
      <div className="dashboard-stats"><div><span>Open roles in your feed</span><strong>{loading ? "..." : dashboard?.available_opportunities.length ?? "—"}</strong></div><div><span>Saved opportunities</span><strong>{loading ? "..." : saved ?? "—"}</strong></div><div><span>Interest registered</span><strong>{loading ? "..." : applied ?? "—"}</strong></div></div>
      <div className="tab-bar" role="tablist" aria-label="Candidate views">
        {tabs.map(({ id, label, icon: Icon }) => <button key={id} role="tab" id={`tab-${id}`} aria-selected={tab === id} aria-controls="candidate-panel" onClick={() => { setTab(id); setQuery(""); }}><Icon size={15} />{label}</button>)}
      </div>
      <div id="candidate-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "resume" ? <section className="resume-section">
          <h2 className="section-heading"><FileText size={19} />Your experience, in one place</h2>
          <input ref={input} type="file" accept=".pdf,.docx" aria-label="Select resume file" className="sr-only" disabled={uploading} onChange={(event) => selectFile(event.target.files?.[0])} />
          <button type="button" disabled={uploading} className="upload-zone" onClick={() => input.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); if (!uploading) selectFile(event.dataTransfer.files[0]); }}><UploadCloud size={32} /><strong>{file ? file.name : "Choose or drop your resume"}</strong><span>PDF or DOCX / up to 10 MB</span></button>
          <div className="upload-actions"><button className="primary-button" onClick={upload} disabled={!file || uploading}><UploadCloud size={16} />{uploading ? "Uploading..." : "Upload resume"}</button>{file && <span>{(file.size / 1024).toFixed(0)} KB / {file.name}</span>}</div>
          {message && <p className="notice mt-5" role="status">{message}</p>}
        </section> : <>
          <div className="results-toolbar"><label className="search-field"><Search size={18} /><input aria-label="Search opportunities" placeholder="Search roles, skills or locations" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="sort-control"><SlidersHorizontal size={15} /><span>Sort by</span><select aria-label="Sort opportunities" value={sort} onChange={(event) => setSort(event.target.value)}><option value="match">Match score</option><option value="salary">Salary ceiling</option><option value="title">Role title</option></select></label></div>
          {error && <div className="notice error" role="alert"><CircleAlert size={18} /><span>{error}</span><button className="secondary-button" onClick={() => setReload((value) => value + 1)}><RefreshCw size={14} />Retry</button></div>}
          {loading ? <div className="opportunity-grid" aria-busy="true" aria-label="Loading opportunities">{[1, 2, 3, 4].map((key) => <div key={key} className="skeleton" />)}</div> : <>
            <p className="results-meta">{visible.length} {visible.length === 1 ? "opportunity" : "opportunities"}{tab === "for-you" ? " / ordered by your match score" : ""}</p>
            {visible.length ? <div className="opportunity-grid">{visible.map((job, index) => <OpportunityCard key={job.job_id} opportunity={job} rank={tab === "for-you" && sort === "match" && !query ? index + 1 : undefined} onAction={updateOpportunity} busy={busyId !== null} />)}</div> : !error && <div className="empty-state"><BriefcaseBusiness size={30} /><h2>{query ? "No matching opportunities" : tab === "history" ? "Your next step starts here" : "No opportunities yet"}</h2><p>{query ? "Try another role, location or skill." : tab === "history" ? "Your saved roles and registered interests will appear here." : "New opportunities will appear as employers publish roles."}</p>{tab === "history" && <button className="secondary-button" onClick={() => setTab("all")}>Browse opportunities<ArrowUpRight size={16} /></button>}</div>}
          </>}
        </>}
      </div>
    </main>
  );
}

function OpportunityCard({ opportunity, rank, onAction, busy }: { opportunity: Opportunity; rank?: number; onAction: (id: string, status: "saved" | "applied") => void; busy: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const applied = opportunity.status === "applied";
  const saved = opportunity.status === "saved";
  return <article className="job-card" style={{ animationDelay: `${Math.min(rank ?? 0, 5) * 50}ms` } as CSSProperties}>
    <div className="job-card-top"><div className="company-mark" aria-hidden="true">{opportunity.company_name.slice(0, 2).toUpperCase()}</div><div className="match-badge"><strong>{percentage(opportunity.match_score)}%</strong><span>Match score</span></div></div>
    <h3>{opportunity.title}</h3><p className="company-name">{opportunity.company_name}</p>
    <div className="job-facts"><span><MapPin size={13} />{opportunity.location || "Location not specified"}</span><span><BriefcaseBusiness size={13} />{opportunity.required_experience_years}+ years</span></div>
    <p className="job-description" style={expanded ? { display: "block" } : undefined}>{opportunity.description}</p>
    <div className="skill-tags">{(expanded ? opportunity.required_skills : opportunity.required_skills.slice(0, 4)).map((skill) => <span key={skill}>{skill}</span>)}</div>
    {expanded && <div className="company-name">Certifications: {opportunity.mandatory_certifications.join(", ") || "None specified"}</div>}
    <button className="text-button mb-4" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Less detail" : "View role"}<ArrowUpRight size={14} /></button>
    <div className="job-card-bottom"><span>{opportunity.salary_range_max != null ? `Up to KES ${Number(opportunity.salary_range_max).toLocaleString()}` : "Salary not disclosed"}</span><div className="flex gap-2"><button className="icon-button" title={applied ? "Interest already registered" : saved ? "Opportunity saved" : "Save opportunity"} aria-label={saved ? `Saved ${opportunity.title}` : `Save ${opportunity.title}`} disabled={busy || saved || applied} onClick={() => onAction(opportunity.job_id, "saved")}><Bookmark size={16} fill={saved ? "currentColor" : "none"} /></button><button className="secondary-button" disabled={busy || applied} onClick={() => onAction(opportunity.job_id, "applied")}>{applied ? <Check size={14} /> : <ArrowUpRight size={14} />}{applied ? "Interest sent" : "Register interest"}</button></div></div>
    {rank && <span className="company-name mt-3">{String(rank).padStart(2, "0")} / In your recommendations</span>}
  </article>;
}