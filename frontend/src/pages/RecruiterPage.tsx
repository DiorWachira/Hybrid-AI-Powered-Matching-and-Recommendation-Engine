import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Check, FileText, ListChecks, RotateCcw, Send, ShieldCheck } from "lucide-react";
import { api, type JobInput } from "../lib/api";

const initialJob: JobInput = { title: "Senior DevOps Engineer", description: "Own platform reliability, CI/CD delivery and cloud operations for a Nairobi fintech team.", location: "Nairobi", requiredExperienceYears: 5, salaryRangeMax: 250000, requiredSkills: ["CI/CD", "AWS", "Kubernetes", "Docker"], mandatoryCertifications: ["AWS Certified Cloud Practitioner"] };
const toList = (value: string) => [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];

export function RecruiterPage() {
  const navigate = useNavigate();
  const [job, setJob] = useState(initialJob);
  const [certText, setCertText] = useState(initialJob.mandatoryCertifications.join(", "));
  const [skillText, setSkillText] = useState(initialJob.requiredSkills.join(", "));
  const [notice, setNotice] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [published, setPublished] = useState<string | null>(null);
  const invalidate = () => { setPublished(null); setNotice(null); };
  const update = <Key extends keyof JobInput>(key: Key, value: JobInput[Key]) => { invalidate(); setJob((current) => ({ ...current, [key]: value })); };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || published) return;
    const token = localStorage.getItem("jobbridge_token");
    if (!token) { navigate("/auth"); return; }
    setBusy(true); setNotice(null); setFailed(false);
    const payload = { ...job, requiredSkills: toList(skillText), mandatoryCertifications: toList(certText) };
    try {
      const response = await api.createJob(payload, token);
      localStorage.setItem("jobbridge_job_id", response.job_id);
      localStorage.setItem("jobbridge_active_job", JSON.stringify(payload));
      setPublished(response.job_id); setNotice("Your role is published and ready for evaluation.");
    } catch (error) { setFailed(true); setNotice(error instanceof Error ? error.message : "Could not publish this role."); }
    finally { setBusy(false); }
  };
  const reset = () => { setJob(initialJob); setCertText(initialJob.mandatoryCertifications.join(", ")); setSkillText(initialJob.requiredSkills.join(", ")); invalidate(); };

  return <main className="studio-page">
    <div className="page-heading"><div><p className="eyebrow">Recruiter workspace</p><h1>Make room for the right talent.</h1><p>Create a role with clear requirements.</p></div><button className="primary-button" disabled={!published || busy} onClick={() => navigate("/matches")}>Match analysis<ArrowRight size={17} /></button></div>
    {notice && <p className={`notice ${failed ? "error" : ""}`} role="status">{!failed && <Check size={18} />}{notice}</p>}
    <div className="form-layout">
      <form onSubmit={submit} className="role-form">
        <fieldset disabled={busy} className="form-section"><legend className="section-heading"><FileText size={18} />01 / Role details</legend><div className="form-grid">
          <label className="studio-field">Role title<input value={job.title} minLength={2} maxLength={255} onChange={(event) => update("title", event.target.value)} required /></label>
          <label className="studio-field">Location<input value={job.location} maxLength={120} onChange={(event) => update("location", event.target.value)} required /></label>
          <label className="studio-field full">Role description<textarea rows={6} value={job.description} minLength={20} maxLength={20000} onChange={(event) => update("description", event.target.value)} required /></label>
          <label className="studio-field full">Required skills<input value={skillText} onChange={(event) => { invalidate(); setSkillText(event.target.value); }} /><small>Separate skills with commas</small></label>
        </div></fieldset>
        <fieldset disabled={busy} className="form-section"><legend className="section-heading"><ListChecks size={18} />02 / Eligibility criteria</legend><div className="form-grid">
          <label className="studio-field">Minimum experience (years)<input type="number" min={0} max={60} step={1} value={job.requiredExperienceYears} onChange={(event) => update("requiredExperienceYears", Number(event.target.value))} required /></label>
          <label className="studio-field">Salary ceiling (KES)<input type="number" min={0} max={9999999999} step="0.01" value={job.salaryRangeMax} onChange={(event) => update("salaryRangeMax", Number(event.target.value))} required /></label>
          <label className="studio-field full">Mandatory certifications<input value={certText} onChange={(event) => { invalidate(); setCertText(event.target.value); }} /><small>Optional / separate certifications with commas</small></label>
        </div></fieldset>
        <div className="form-actions"><button className="secondary-button" type="button" disabled={busy} onClick={reset}><RotateCcw size={15} />Reset</button><button className="primary-button" disabled={busy || !!published}>{published ? <Check size={16} /> : <Send size={16} />}{busy ? "Publishing..." : published ? "Published" : "Publish role"}</button></div>
      </form>
      <aside className="role-summary"><p className="eyebrow">Role at a glance</p><h2>{job.title || "Untitled role"}</h2><p>{job.location || "Location not specified"}</p><div className="skill-tags">{toList(skillText).map((skill) => <span key={skill}>{skill}</span>)}</div><h3 className="section-heading mt-8"><ShieldCheck size={17} />Eligibility</h3><div className="summary-line"><span>Experience</span><strong>{job.requiredExperienceYears}+ years</strong></div><div className="summary-line"><span>Salary ceiling</span><strong>KES {job.salaryRangeMax.toLocaleString()}</strong></div><div className="summary-line"><span>Certifications</span><strong>{toList(certText).length} required</strong></div><div className="score-legend"><p className="eyebrow">Matching signals</p><span><i />Semantic relevance</span><span><i />Skill alignment</span><span><i />Growth potential</span></div></aside>
    </div>
  </main>;
}