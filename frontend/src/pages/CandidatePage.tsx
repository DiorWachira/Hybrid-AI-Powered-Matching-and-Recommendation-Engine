import { useRef, useState } from "react";
import { Check, FileUp, ShieldCheck, UploadCloud } from "lucide-react";
import { PageTitle } from "../components/PageTitle";
import { api } from "../lib/api";

const supported = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];

export function CandidatePage() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

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

  return (
    <main className="mx-auto max-w-[1200px] space-y-6 px-5 py-6 lg:px-8">
      <PageTitle eyebrow="Candidate workspace" title="Make your skills legible to the right roles." detail="Your resume is parsed locally, stored as structured profile data, and used for explainable matching." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
        <section className="glass-panel wave-violet rounded-2xl p-5">
          <div className="flex items-center gap-2"><FileUp className="h-4 w-4 text-spectral-violet" /><h2 className="font-semibold">Resume ingestion</h2></div>
          <button onClick={() => input.current?.click()} onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0]); }} onDragOver={(event) => event.preventDefault()} className="mt-5 flex min-h-56 w-full flex-col items-center justify-center rounded-xl border border-dashed border-spectral-violet/40 bg-spectral-violet/5 px-6 text-center transition hover:border-spectral-emerald/55 hover:bg-spectral-emerald/5">
            <UploadCloud className="h-8 w-8 text-spectral-violet" /><strong className="mt-3 text-sm">Drop your PDF or DOCX here</strong><span className="mt-1 text-xs text-white/40">or select it from your device · maximum 10 MB</span>
            <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="hidden" onChange={(event) => selectFile(event.target.files?.[0])} />
          </button>
          {message && <p className="mt-4 rounded-lg border border-spectral-emerald/25 bg-spectral-emerald/5 px-3 py-2 text-xs text-spectral-emerald">{message}</p>}
          {file && <div className="mt-4 flex items-center justify-between rounded-lg border border-white/10 bg-black/15 px-3 py-3 text-sm"><span className="truncate">{file.name}</span><span className="font-mono text-xs text-white/35">{(file.size / 1024 / 1024).toFixed(2)} MB</span></div>}
          <button type="button" onClick={upload} disabled={!file || uploading} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-spectral-emerald px-4 py-2.5 text-sm font-semibold text-obsidian disabled:cursor-not-allowed disabled:opacity-40"><UploadCloud className="h-4 w-4" />{uploading ? "Uploading..." : "Upload resume"}</button>
        </section>
        <aside className="space-y-4">
          <div className="glass-panel rounded-2xl p-5"><p className="section-label semantic-label">Profile protection</p><div className="mt-4 flex items-start gap-3 text-sm text-white/55"><ShieldCheck className="mt-0.5 h-4 w-4 flex-none text-spectral-emerald" /><p>Only experience, skills, certifications, and resume text are used by the matching API.</p></div></div>
          <div className="glass-panel rounded-2xl p-5"><p className="section-label compliance-label">Pipeline status</p><ul className="mt-4 space-y-3 text-sm text-white/55"><li className="flex items-center gap-2"><Check className="h-4 w-4 text-spectral-emerald" />File type and size checked</li><li className="flex items-center gap-2"><Check className="h-4 w-4 text-spectral-emerald" />Text extracted locally</li><li className="flex items-center gap-2"><Check className="h-4 w-4 text-spectral-emerald" />Skills saved to profile</li></ul></div>
        </aside>
      </div>
    </main>
  );
}
