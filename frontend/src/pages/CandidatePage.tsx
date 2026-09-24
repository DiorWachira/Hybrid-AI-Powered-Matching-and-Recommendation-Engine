import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUpRight, BadgeDollarSign, Bookmark, Check, Clock3, FileUp, MapPin, ShieldCheck, UploadCloud } from "lucide-react";
import { PageTitle } from "../components/PageTitle";
import { api, type CandidateDashboard, type Opportunity } from "../lib/api";

const supported = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];

export function CandidatePage() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dashboard, setDashboard] = useState<CandidateDashboard | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("jobbridge_token");
    if (!token) return;
    void api.candidateDashboard(token).then(setDashboard).catch((error: Error) => setDashboardError(error.message));
  }, []);

  const selectFile = (next: File | undefined) => {
    if (!next) return;
    if (!supported.includes(next.type) || next.size > 10 * 1024 * 1024) {
      setMessage("Use a PDF or DOCX file no larger than 10 MB.");
      return;
    }
    setFile(next);
    setMessage("Resume ready to upload.");
  };

  const upload = async () => {
    const token = localStorage.getItem("jobbridge_token");
    if (!file || !token) {
      setMessage("Select a resume and sign in before uploading.");
      return;
    }
    setUploading(true);
    try {
      const profile = await api.uploadResume(file, token);
      setMessage(`Resume uploaded. ${profile.skills.length} skills were detected and saved.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The resume could not be uploaded.");
    } finally {
      setUploading(false);
    }
  };

  const updateOpportunity = async (jobId: string, status: "saved" | "applied") => {
    const token = localStorage.getItem("jobbridge_token");
    if (!token) return;
    try {
      await api.updateOpportunityStatus(jobId, status, token);
      const refreshed = await api.candidateDashboard(token);
      setDashboard(refreshed);
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : "The opportunity could not be updated.");
    }
  };

  return <main className="mx-auto max-w-[1400px] space-y-7 px-5 py-6 lg:px-8"><PageTitle eyebrow="Candidate workspace" title="Find work that fits your trajectory." detail="Your profile, activity history, and trained match scores stay together so recommendations become useful over time." />{dashboardError && <p className="rounded-xl border border-spectral-coral/35 bg-spectral-coral/10 px-4 py-3 text-sm text-spectral-coral">{dashboardError}</p>}<section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px]"><div className="glass-panel wave-violet rounded-2xl p-5"><div className="flex items-center gap-2"><FileUp className="h-4 w-4 text-spectral-violet" /><h2 className="font-semibold">Resume ingestion</h2></div><button onClick={() => input.current?.click()} onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0]); }} onDragOver={(event) => event.preventDefault()} className="mt-5 flex min-h-44 w-full flex-col items-center justify-center rounded-xl border border-dashed border-spectral-violet/40 bg-spectral-violet/5 px-6 text-center transition hover:border-spectral-emerald/55 hover:bg-spectral-emerald/5"><UploadCloud className="h-8 w-8 text-spectral-violet" /><strong className="mt-3 text-sm">Drop your PDF or DOCX here</strong><span className="mt-1 text-xs text-white/40">or select it from your device · maximum 10 MB</span><input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="hidden" onChange={(event) => selectFile(event.target.files?.[0])} /></button>{message && <p className="mt-4 rounded-lg border border-spectral-emerald/25 bg-spectral-emerald/5 px-3 py-2 text-xs text-spectral-emerald">{message}</p>}{file && <div className="mt-4 flex items-center justify-between rounded-lg border border-white/10 bg-black/15 px-3 py-3 text-sm"><span className="truncate">{file.name}</span><span className="font-mono text-xs text-white/35">{(file.size / 1024 / 1024).toFixed(2)} MB</span></div>}<button type="button" onClick={upload} disabled={!file || uploading} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-spectral-emerald px-4 py-2.5 text-sm font-semibold text-obsidian disabled:cursor-not-allowed disabled:opacity-40"><UploadCloud className="h-4 w-4" />{uploading ? "Uploading..." : "Upload resume"}</button></div><aside className="space-y-4"><div className="glass-panel rounded-2xl p-5"><p className="section-label semantic-label">Profile protection</p><div className="mt-4 flex items-start gap-3 text-sm text-white/55"><ShieldCheck className="mt-0.5 h-4 w-4 flex-none text-spectral-emerald" /><p>Only experience, skills, certifications, and resume text are used by the matching API.</p></div></div><div className="glass-panel rounded-2xl p-5"><p className="section-label compliance-label">Your activity</p><ul className="mt-4 space-y-3 text-sm text-white/55"><li className="flex items-center gap-2"><Check className="h-4 w-4 text-spectral-emerald" />{dashboard?.history.length ?? 0} saved or applied</li><li className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-spectral-amber" />{dashboard?.available_opportunities.length ?? 0} open opportunities</li></ul></div></aside></section><section><SectionHeader icon={<Bookmark className="h-4 w-4" />} label="For you" detail="Highest current match scores" />{dashboard?.for_you.length ? <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{dashboard.for_you.map((opportunity) => <OpportunityCard key={opportunity.job_id} opportunity={opportunity} onAction={updateOpportunity} featured />)}</div> : <EmptyState text="Your personalized opportunities will appear after the database is seeded and your profile is available." />}</section><section><SectionHeader icon={<ArrowUpRight className="h-4 w-4" />} label="Available opportunities" detail="Open roles from the marketplace" />{dashboard?.available_opportunities.length ? <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{dashboard.available_opportunities.map((opportunity) => <OpportunityCard key={opportunity.job_id} opportunity={opportunity} onAction={updateOpportunity} />)}</div> : <EmptyState text="No open opportunities are available yet." />}</section><section><SectionHeader icon={<Clock3 className="h-4 w-4" />} label="Your opportunity history" detail="Saved and applied roles" />{dashboard?.history.length ? <div className="mt-4 grid gap-4 md:grid-cols-2">{dashboard.history.map((opportunity) => <OpportunityCard key={opportunity.job_id} opportunity={opportunity} onAction={updateOpportunity} history />)}</div> : <EmptyState text="Saved and applied opportunities will appear here." />}</section></main>;
}

function SectionHeader({ icon, label, detail }: { icon: ReactNode; label: string; detail: string }) {
  return <div className="flex items-end justify-between gap-4"><div className="flex items-center gap-2 text-spectral-emerald">{icon}<h2 className="text-sm font-semibold uppercase tracking-[0.14em]">{label}</h2></div><p className="text-xs text-white/35">{detail}</p></div>;
}

function OpportunityCard({ opportunity, onAction, featured = false, history = false }: { opportunity: Opportunity; onAction: (jobId: string, status: "saved" | "applied") => void; featured?: boolean; history?: boolean }) {
  return <article className={`glass-panel rounded-2xl p-5 ${featured ? "border-spectral-emerald/25" : ""}`}><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-[10px] uppercase tracking-[0.15em] text-white/35">{opportunity.company_name}</p><h3 className="mt-2 font-semibold text-white">{opportunity.title}</h3></div><span className="rounded-lg bg-spectral-emerald/10 px-2 py-1 font-mono text-xs text-spectral-emerald">{Math.round(opportunity.match_score * 100)}%</span></div><div className="mt-4 flex flex-wrap gap-3 text-xs text-white/45"><span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{opportunity.location || "Flexible"}</span><span className="inline-flex items-center gap-1"><BadgeDollarSign className="h-3.5 w-3.5" />KES {Number(opportunity.salary_range_max || 0).toLocaleString()}</span></div><p className="mt-4 line-clamp-3 text-sm leading-6 text-white/55">{opportunity.description}</p><div className="mt-4 flex flex-wrap gap-2">{opportunity.required_skills.slice(0, 4).map((skill) => <span key={skill} className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-white/45">{skill}</span>)}</div><div className="mt-5 flex gap-2">{history ? <span className="rounded-lg border border-white/10 px-3 py-2 text-xs uppercase text-white/45">{opportunity.status}</span> : <><button onClick={() => onAction(opportunity.job_id, "saved")} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/60 hover:border-spectral-emerald/40 hover:text-spectral-emerald">Save</button><button onClick={() => onAction(opportunity.job_id, "applied")} className="rounded-lg bg-spectral-emerald px-3 py-2 text-xs font-semibold text-obsidian">Apply interest</button></>}</div></article>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="mt-4 rounded-2xl border border-dashed border-white/10 px-5 py-8 text-center text-sm text-white/40">{text}</div>;
}
