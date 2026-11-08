import { useEffect, useRef, useState } from "react";
import { CircleAlert, X } from "lucide-react";

/** Must match MIN_REASON_LENGTH in backend/app/core/overrides.py, which enforces it. */
export const MIN_REASON_LENGTH = 10;

export type OverridePerson = { id: string; name: string; final_score: number | null; hard_rule_passed: boolean | null; recommended: boolean | null; rule_reasons: string[] };
export type Flag = { id: string; name: string; score: number | null; kind: "hard_rule" | "below_threshold"; reasons: string[] };
export type OverrideRequest = { action: string; flagged: Flag[]; onConfirm: (reason?: string) => void };

/** People this move would advance against the evaluation's advice. Unscored applicants are not flagged. */
export function overrideFlags(people: OverridePerson[]): Flag[] {
  return people.flatMap((person): Flag[] => person.hard_rule_passed === false ? [{ id: person.id, name: person.name, score: person.final_score, kind: "hard_rule", reasons: person.rule_reasons }]
    : person.hard_rule_passed && person.recommended === false ? [{ id: person.id, name: person.name, score: person.final_score, kind: "below_threshold", reasons: [] }] : []);
}

const percent = (score: number | null) => score === null ? "—" : `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`;

/** Warn and record, never block: the recruiter can go ahead, but a failed eligibility rule needs a written reason. */
export function OverrideDialog({ request, onClose }: { request: OverrideRequest | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (request) { setReason(""); dialog.current?.showModal(); } else dialog.current?.close();
  }, [request]);
  const needsReason = !!request?.flagged.some((item) => item.kind === "hard_rule");
  const ready = !needsReason || reason.trim().length >= MIN_REASON_LENGTH;
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!request || !ready) return;
    const confirm = request.onConfirm;
    onClose();
    confirm(needsReason ? reason.trim() : undefined);
  };
  return <dialog className="admin-dialog override-dialog" ref={dialog} onCancel={onClose} aria-labelledby="override-title">
    {request && <form onSubmit={submit}>
      <div className="page-heading"><h2 id="override-title"><CircleAlert size={19} />Against the evaluation's advice</h2><button type="button" className="icon-button" aria-label="Cancel" title="Cancel" onClick={onClose}><X size={18} /></button></div>
      <p className="override-lead">You are about to {request.action}. {request.flagged.length === 1 ? "This person was" : "These people were"} not recommended:</p>
      <ul className="override-list">{request.flagged.map((item) => <li key={item.id}>
        <strong>{item.name}</strong>
        <span className={`override-kind ${item.kind}`}>{item.kind === "hard_rule" ? "Failed an eligibility rule" : `Below the threshold, ${percent(item.score)}`}</span>
        {item.reasons.length > 0 && <small>{item.reasons.join("; ")}</small>}
      </li>)}</ul>
      <p className="override-note">You keep the final say: the model is tested only on synthetic data and a rule can rest on an out-of-date profile. The move is recorded with the score and rule result{needsReason ? ", and your reason," : ""} for the administrator to review.</p>
      {needsReason && <label className="studio-field">Why move them forward? (required, at least {MIN_REASON_LENGTH} characters)<textarea rows={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="For example: earned the certificate last month, confirmed by email" required autoFocus /><small>{reason.trim().length < MIN_REASON_LENGTH ? `${MIN_REASON_LENGTH - reason.trim().length} more characters needed` : "Saved with this move in the activity log"}</small></label>}
      <div className="workflow-actions"><button type="submit" className="primary-button" disabled={!ready}>Go ahead and record it</button><button type="button" className="secondary-button" onClick={onClose}>Cancel</button></div>
    </form>}
  </dialog>;
}
