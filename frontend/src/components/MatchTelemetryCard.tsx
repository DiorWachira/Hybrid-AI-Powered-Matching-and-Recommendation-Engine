import { ArrowRight, CheckCircle2, Layers, ShieldCheck, Sparkles } from "lucide-react";
import { demoCandidate, demoMatch, demoRole } from "../lib/demoMatch";

const kes = new Intl.NumberFormat("en-KE", {
  style: "currency",
  currency: "KES",
  maximumFractionDigits: 0,
});

function ScoreBar({ label, value, blurb }: { label: string; value: number; blurb: string }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-fg/85">{label}</span>
        <span className="font-mono text-xs text-gold-bright">{value.toFixed(2)}</span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-fg/12"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${pct} out of 100`}
      >
        <div className="h-full rounded-full bg-gold" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{blurb}</p>
    </div>
  );
}

export function MatchTelemetryCard() {
  return (
    <article className="rounded-card border border-line bg-surface-strong p-5 text-fg shadow-xl sm:p-6">
      <header className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-muted uppercase">
          <Sparkles className="h-3.5 w-3.5 text-gold" aria-hidden />
          Live match preview
        </span>
        <span className="font-mono text-[10px] text-muted/70">demo data</span>
      </header>

      <div className="mt-5 grid items-stretch gap-3 sm:grid-cols-[1fr_auto_1fr]">
        {/* Candidate */}
        <section className="rounded-xl border border-line bg-canvas/60 p-4">
          <p className="font-mono text-[10px] text-muted/80">{demoCandidate.reference}</p>
          <h3 className="mt-1 text-sm font-semibold">{demoCandidate.role}</h3>
          <p className="text-xs text-muted">{demoCandidate.specialisation}</p>
          <dl className="mt-3 space-y-1.5 font-mono text-[11px] text-muted">
            <div className="flex justify-between gap-2">
              <dt>Experience</dt>
              <dd>{demoCandidate.yearsExperience} yrs</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Location</dt>
              <dd>{demoCandidate.location}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Expects</dt>
              <dd>{kes.format(demoCandidate.expectedSalaryKes)}</dd>
            </div>
          </dl>
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {demoCandidate.skills.slice(0, 4).map((skill) => (
              <li
                key={skill}
                className="rounded-md bg-fg/10 px-1.5 py-0.5 font-mono text-[10px] text-fg/80"
              >
                {skill}
              </li>
            ))}
          </ul>
        </section>

        {/* Pipeline */}
        <div className="flex items-center justify-center sm:flex-col sm:gap-2">
          <div className="animate-pipeline relative h-0.5 w-full overflow-hidden rounded-full bg-fg/15 sm:h-24 sm:w-0.5" />
          <span className="sr-only">matched to</span>
          <ArrowRight className="h-4 w-4 shrink-0 text-gold sm:rotate-90" aria-hidden />
        </div>

        {/* Role */}
        <section className="rounded-xl border border-gold/30 bg-canvas/60 p-4">
          <p className="font-mono text-[10px] text-muted/80">{demoRole.reference}</p>
          <h3 className="mt-1 text-sm font-semibold">{demoRole.title}</h3>
          <p className="text-xs text-muted">{demoRole.company}</p>
          <dl className="mt-3 space-y-1.5 font-mono text-[11px] text-muted">
            <div className="flex justify-between gap-2">
              <dt>Requires</dt>
              <dd>{demoRole.requiredExperience}+ yrs</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Location</dt>
              <dd>{demoRole.location}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Ceiling</dt>
              <dd>{kes.format(demoRole.salaryCeilingKes)}</dd>
            </div>
          </dl>
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {demoRole.requiredSkills.map((skill) => (
              <li
                key={skill}
                className={`rounded-md px-1.5 py-0.5 font-mono text-[10px] ${
                  demoMatch.missingSkills.includes(skill)
                    ? "bg-gold/20 text-gold-bright"
                    : "bg-fg/10 text-fg/80"
                }`}
              >
                {skill}
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* Match index */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gold px-4 py-3 text-ink">
        <span className="text-xs font-semibold tracking-wide uppercase">Match index</span>
        <span className="font-mono text-2xl font-semibold">
          {(demoMatch.index * 100).toFixed(1)}%
        </span>
      </div>

      {/* Sub-scores */}
      <div className="mt-5 space-y-4">
        <p className="flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-muted uppercase">
          <Layers className="h-3.5 w-3.5 text-gold" aria-hidden />
          Tier 2 — weighted sub-scores
        </p>
        {demoMatch.subScores.map((score) => (
          <ScoreBar
            key={score.key}
            label={score.label}
            value={score.value}
            blurb={score.blurb}
          />
        ))}
      </div>

      {/* Tier 1 + skill gap */}
      <div className="mt-5 grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
        <div>
          <p className="flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-muted uppercase">
            <ShieldCheck className="h-3.5 w-3.5 text-gold" aria-hidden />
            Tier 1 — hard filters
          </p>
          <ul className="mt-2.5 space-y-1.5">
            {demoMatch.hardFilters.map((filter) => (
              <li key={filter.label} className="flex items-center gap-2 text-[11px] text-fg/80">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-gold" aria-hidden />
                {filter.label}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-mono text-[10px] tracking-wide text-muted uppercase">Skill gap</p>
          <p className="mt-2.5 text-[11px] text-fg/80">
            <span className="font-mono text-gold-bright">
              {demoMatch.matchedSkills.length}/{demoRole.requiredSkills.length}
            </span>{" "}
            required skills matched.
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {demoMatch.missingSkills.map((skill) => (
              <li
                key={skill}
                className="rounded-md border border-gold/40 px-1.5 py-0.5 font-mono text-[10px] text-gold-bright"
              >
                missing: {skill}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}
