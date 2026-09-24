import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Plus, SlidersHorizontal } from "lucide-react";
import { PageTitle } from "../components/PageTitle";
import { api, type JobInput } from "../lib/api";

const initialJob: JobInput = { title: "Senior DevOps Engineer", description: "Own platform reliability, CI/CD delivery and cloud operations for a Nairobi fintech team.", location: "Nairobi", requiredExperienceYears: 5, salaryRangeMax: 250000, mandatoryCertifications: ["AWS Certified Cloud Practitioner"] };

export function RecruiterPage() {
  const navigate = useNavigate();
  const [job, setJob] = useState(initialJob);
  const [certText, setCertText] = useState(initialJob.mandatoryCertifications.join(", "));
  const [notice, setNotice] = useState<string | null>(null);

  const update = <K extends keyof JobInput>(key: K, value: JobInput[K]) => setJob((current) => ({ ...current, [key]: value }));
  const evaluate = () => {
    if (!job.title.trim() || !job.description.trim() || !job.location.trim()) {
      setNotice("Complete the role title, location, and description before evaluating candidates.");
      return;
    };

    const payload = { ...job, mandatoryCertifications: certText.split(",").map((item) => item.trim()).filter(Boolean) };
    localStorage.setItem("jobbridge_active_job", JSON.stringify(payload));
    navigate("/matches");
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const payload = { ...job, mandatoryCertifications: certText.split(",").map((item) => item.trim()).filter(Boolean) };
    const token = localStorage.getItem("jobbridge_token");
    if (!token) {
      localStorage.setItem("jobbridge_job_draft", JSON.stringify(payload));
      setNotice("Role draft saved on this device. Sign in to publish it to the database.");
      return;
    }
    try {
      await api.createJob(payload, token);
      setNotice("Job created successfully.");
    } catch {
      setNotice("The job could not be created. Please check your sign-in and try again.");
    }
  };

  return <main className="mx-auto max-w-[1500px] space-y-6 px-5 py-6 lg:px-8"><PageTitle eyebrow="Recruiter command center" title="Create a role, then let the engine explain the shortlist." detail="Hard constraints are processed first. Semantic, graph and growth signals only run for profiles that clear the rule gate." action={<button onClick={evaluate} className="inline-flex items-center gap-2 rounded-lg bg-spectral-emerald px-4 py-2.5 text-sm font-semibold text-obsidian shadow-glow-emerald"><Play className="h-4 w-4" />Evaluate candidates</button>} />{notice && <div className="rounded-xl border border-spectral-amber/35 bg-spectral-amber/10 px-4 py-3 text-sm text-spectral-amber">{notice}</div>}<div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px]"><form onSubmit={submit} className="glass-panel rounded-2xl p-5"><div className="flex items-center gap-2"><Plus className="h-4 w-4 text-spectral-emerald" /><h2 className="text-base font-semibold">Role specification</h2></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="field"><span>Role title</span><input value={job.title} onChange={(e) => update("title", e.target.value)} required /></label><label className="field"><span>Location</span><input value={job.location} onChange={(e) => update("location", e.target.value)} required /></label><label className="field"><span>Minimum experience</span><input type="number" min="0" value={job.requiredExperienceYears} onChange={(e) => update("requiredExperienceYears", Number(e.target.value))} /></label><label className="field"><span>Salary ceiling (KES)</span><input type="number" min="0" value={job.salaryRangeMax} onChange={(e) => update("salaryRangeMax", Number(e.target.value))} /></label></div><label className="field mt-4"><span>Role description</span><textarea rows={6} value={job.description} onChange={(e) => update("description", e.target.value)} required /></label><label className="field mt-4"><span>Mandatory certifications</span><input value={certText} onChange={(e) => setCertText(e.target.value)} placeholder="CPA, AWS Certified Cloud Practitioner" /><small>Comma-separated. These become Tier 1 hard filters.</small></label><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={() => { setJob(initialJob); setCertText(initialJob.mandatoryCertifications.join(", ")); }} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/60">Reset</button><button className="rounded-lg bg-spectral-emerald px-4 py-2 text-sm font-semibold text-obsidian">Save role draft</button></div></form><aside className="space-y-4"><div className="glass-panel wave-amber rounded-2xl p-5"><div className="flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-spectral-amber" /><h2 className="text-sm font-semibold">Tier 1 rule gate</h2></div><p className="mt-3 text-xs leading-relaxed text-white/45">Profiles failing any item below never consume model or graph computation.</p><ul className="mt-4 space-y-3 text-sm text-white/70"><li>Certification <strong className="float-right font-mono text-spectral-amber">required</strong></li><li>Experience <strong className="float-right font-mono text-spectral-amber">{job.requiredExperienceYears}+ yrs</strong></li><li>Location <strong className="float-right font-mono text-spectral-amber">{job.location}</strong></li><li>Salary <strong className="float-right font-mono text-spectral-amber">≤ KES {job.salaryRangeMax.toLocaleString()}</strong></li></ul></div><div className="glass-panel wave-primary rounded-2xl p-5"><p className="section-label semantic-label">Tier 2 after eligibility</p><div className="mt-4 space-y-3 text-xs text-white/60"><p><b className="text-spectral-emerald">S_bert</b> · semantic role/CV similarity</p><p><b className="text-spectral-emerald">S_graph</b> · direct + related skills</p><p><b className="text-spectral-violet">S_growth</b> · trajectory and certifications</p></div></div></aside></div></main>;
}
