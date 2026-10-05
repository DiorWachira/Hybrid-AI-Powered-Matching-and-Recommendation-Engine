import { useEffect, useState, type FormEvent } from "react";
import { RefreshCw, RotateCcw, Save, UserRound } from "lucide-react";
import { api, type CandidateProfileInput } from "../lib/api";

const toList = (value: string) => [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];

export function CandidateProfile({ onSaved, onDirtyChange }: { onSaved: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const [profile, setProfile] = useState<CandidateProfileInput | null>(null);
  const [saved, setSaved] = useState<CandidateProfileInput | null>(null);
  const [skills, setSkills] = useState("");
  const [certifications, setCertifications] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const dirty = profile !== saved || skills !== (saved?.skills.join(", ") ?? "") || certifications !== (saved?.certifications.join(", ") ?? "");

  const loadForm = (data: CandidateProfileInput) => {
    setProfile(data); setSaved(data);
    setSkills(data.skills.join(", ")); setCertifications(data.certifications.join(", "));
  };
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.getCandidateProfile(localStorage.getItem("jobbridge_token") ?? "")
      .then((data) => { if (active) loadForm(data); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  useEffect(() => {
    onDirtyChange(dirty);
    const preventUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    if (dirty) window.addEventListener("beforeunload", preventUnload);
    return () => { onDirtyChange(false); window.removeEventListener("beforeunload", preventUnload); };
  }, [dirty, onDirtyChange]);

  const update = <Key extends keyof CandidateProfileInput>(key: Key, value: CandidateProfileInput[Key]) => {
    setProfile((current) => current ? { ...current, [key]: value } : current); setNotice(null);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!profile || saving) return;
    const payload = { ...profile, full_name: profile.full_name.trim(), location: profile.location?.trim() || null, skills: toList(skills), certifications: toList(certifications) };
    setError(null); setNotice(null);
    if (payload.skills.length > 50 || payload.certifications.length > 20) { setError("Use at most 50 skills and 20 certifications."); return; }
    setSaving(true);
    try {
      loadForm(await api.updateCandidateProfile(payload, localStorage.getItem("jobbridge_token") ?? ""));
      setNotice("Profile saved."); onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save your profile."); }
    finally { setSaving(false); }
  };

  return <section className="data-section" aria-label="My profile">
    <h2 className="section-heading"><UserRound size={19} />My profile</h2>
    {error && <p className="notice error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {loading ? <p role="status">Loading profile...</p> : !profile ? <button className="secondary-button" onClick={() => setRevision((value) => value + 1)}><RefreshCw size={16} />Retry profile</button> : <form onSubmit={(event) => void submit(event)}>
      <fieldset disabled={saving} className="form-section"><legend className="sr-only">Profile details</legend><div className="form-grid">
        <label className="studio-field">Full name<input value={profile.full_name} minLength={2} maxLength={255} required autoComplete="name" onChange={(event) => update("full_name", event.target.value)} /></label>
        <label className="studio-field">Location<input value={profile.location ?? ""} maxLength={120} autoComplete="address-level2" onChange={(event) => update("location", event.target.value)} /></label>
        <label className="studio-field">Years of experience<input type="number" min={0} max={60} step={1} required value={profile.years_experience} onChange={(event) => update("years_experience", Number(event.target.value))} /></label>
        <label className="studio-field">Expected salary (KES)<input type="number" min={0} max="9999999999.99" step="0.01" value={profile.expected_salary ?? ""} onChange={(event) => update("expected_salary", event.target.value || null)} /></label>
        <label className="studio-field">Work authorization<select value={profile.work_authorized == null ? "" : String(profile.work_authorized)} onChange={(event) => update("work_authorized", event.target.value === "" ? null : event.target.value === "true")}><option value="">Not specified</option><option value="true">Authorized</option><option value="false">Not authorized</option></select></label>
        <label className="studio-field full">Skills (comma-separated)<textarea rows={3} value={skills} onChange={(event) => { setSkills(event.target.value); setNotice(null); }} /></label>
        <label className="studio-field full">Certifications (comma-separated)<textarea rows={3} value={certifications} onChange={(event) => { setCertifications(event.target.value); setNotice(null); }} /></label>
      </div></fieldset>
      <div className="form-actions"><button className="secondary-button" type="button" disabled={saving || !dirty} onClick={() => { if (saved && window.confirm("Discard unsaved profile changes?")) { loadForm(saved); setError(null); setNotice(null); } }}><RotateCcw size={16} />Discard changes</button><button className="primary-button" disabled={saving || !dirty}><Save size={16} />{saving ? "Saving..." : "Save profile"}</button></div>
    </form>}
  </section>;
}