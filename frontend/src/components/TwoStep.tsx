import { useState } from "react";
import { Check, Copy, Download, ShieldCheck } from "lucide-react";
import { api, type MfaSetup, type Session } from "../lib/api";

/** Scan-and-confirm step. `token` is a session or the enrolment token from a required-MFA login. */
export function MfaEnrollment({ token, setup, onEnabled }: { token: string; setup: MfaSetup; onEnabled: (session: Session, recoveryCodes: string[]) => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const confirm = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const result = await api.enableMfa(token, code);
      onEnabled({ access_token: result.access_token, role: result.role }, result.recovery_codes);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not confirm the code."); setCode(""); }
    finally { setBusy(false); }
  };
  return <div className="mfa-enrol">
    <ol className="mfa-steps">
      <li>Open an authenticator app such as Google Authenticator, Microsoft Authenticator or Authy.</li>
      <li>Scan this QR code, or enter the setup key by hand.</li>
      <li>Type the 6-digit code the app shows.</li>
    </ol>
    <img className="mfa-qr" src={setup.qr_svg} alt="QR code for adding JobBridge to an authenticator app" width={200} height={200} />
    <div className="mfa-secret"><span>Setup key</span><code>{setup.secret.match(/.{1,4}/g)?.join(" ")}</code>
      <button type="button" className="text-button" onClick={() => { void navigator.clipboard.writeText(setup.secret).then(() => setCopied(true)).catch(() => setError("Could not copy. Select the key to copy it.")); }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Copied" : "Copy"}</button></div>
    <form onSubmit={confirm} className="mfa-form">
      <OneTimeCodeField value={code} onChange={setCode} label="6-digit code" />
      {error && <p className="notice error" role="alert">{error}</p>}
      <button className="primary-button" disabled={busy || code.length !== 6}><ShieldCheck size={16} />{busy ? "Checking..." : "Turn on two-step verification"}</button>
    </form>
  </div>;
}

/** "either" accepts an authenticator code or a recovery code in one field. */
export function OneTimeCodeField({ value, onChange, label, kind = "totp" }: { value: string; onChange: (value: string) => void; label: string; kind?: "totp" | "recovery" | "either" }) {
  return <label className="studio-field">{label}
    {kind === "totp"
      ? <input className="mfa-code-input" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" placeholder="123456" maxLength={6} value={value} onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))} required autoFocus />
      : <input className="mfa-code-input" autoComplete={kind === "either" ? "one-time-code" : "off"} autoCapitalize="none" spellCheck={false} placeholder={kind === "either" ? "123456 or xxxxx-xxxxx" : "xxxxx-xxxxx"} maxLength={11} value={value} onChange={(event) => onChange(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))} required autoFocus />}
  </label>;
}

/** Shows freshly issued recovery codes once; the server keeps only their hashes. */
export function RecoveryCodes({ codes, email, onDone, doneLabel = "Continue" }: { codes: string[]; email?: string | null; onDone: () => void; doneLabel?: string }) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = `JobBridge recovery codes${email ? ` for ${email}` : ""}\nEach code works once. Keep them private.\n\n${codes.join("\n")}\n`;
  const download = () => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    link.download = "jobbridge-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(link.href);
    setSaved(true);
  };
  return <div className="mfa-recovery">
    <p className="notice">Save these recovery codes somewhere safe. Each one signs you in once if you lose your phone. They will not be shown again.</p>
    <ul className="recovery-codes" aria-label="Recovery codes">{codes.map((code) => <li key={code}><code>{code}</code></li>)}</ul>
    <div className="workflow-actions">
      <button type="button" className="secondary-button" onClick={download}><Download size={16} />Download</button>
      <button type="button" className="secondary-button" onClick={() => { void navigator.clipboard.writeText(text).then(() => { setCopied(true); setSaved(true); }).catch(() => undefined); }}>{copied ? <Check size={16} /> : <Copy size={16} />}{copied ? "Copied" : "Copy"}</button>
    </div>
    <label className="mfa-confirm"><input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} />I have saved my recovery codes</label>
    <button type="button" className="primary-button" disabled={!saved} onClick={onDone}>{doneLabel}</button>
  </div>;
}
