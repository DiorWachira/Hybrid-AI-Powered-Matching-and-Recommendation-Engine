import { Layers, ShieldCheck, Sparkles, Terminal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "./ui/Badge";

type Step = {
  n: string;
  title: string;
  body: string;
  icon: LucideIcon;
  tag: string;
};

const steps: Step[] = [
  {
    n: "01",
    title: "Deep signal extraction",
    body: "CVs are parsed into structured skills, certifications and experience. Names, gender, age and contact details are stripped before anything is scored, so the engine never sees them.",
    icon: Terminal,
    tag: "parse + anonymise",
  },
  {
    n: "02",
    title: "Compliance gate",
    body: "Non-negotiables are settled deterministically: mandatory certifications, minimum experience, location and salary band. Anyone who fails is excluded before expensive scoring runs.",
    icon: ShieldCheck,
    tag: "tier 1 — rules",
  },
  {
    n: "03",
    title: "Bilateral alignment matrix",
    body: "Survivors are scored three ways: semantic similarity between résumé and role text, weighted overlap across the skill graph including related skills, and growth headroom from experience and certifications.",
    icon: Layers,
    tag: "tier 2 — hybrid",
  },
  {
    n: "04",
    title: "Explainable introductions",
    body: "Every shortlist arrives with its reasoning: which filters were verified, which skills matched, and which are missing. No opaque ranking, no cold recruiter spam.",
    icon: Sparkles,
    tag: "skill-gap output",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-6xl px-5 py-16 lg:py-24">
      <div className="max-w-2xl">
        <Badge tone="outline">How it works</Badge>
        <h2 className="mt-4 text-3xl font-bold text-fg sm:text-4xl">
          Four stages, and you can audit every one.
        </h2>
        <p className="mt-4 text-muted">
          The cheap deterministic work happens first so the expensive semantic
          work only ever runs on candidates who are genuinely eligible.
        </p>
      </div>

      <ol className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step) => (
          <li
            key={step.n}
            className="group flex flex-col rounded-card border border-line bg-surface p-5 transition-all duration-200 hover:-translate-y-1 hover:border-gold/50 hover:shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald text-fg transition-colors group-hover:bg-gold group-hover:text-ink">
                <step.icon className="h-5 w-5" aria-hidden />
              </span>
              <span className="font-mono text-2xl font-semibold text-fg/20">{step.n}</span>
            </div>
            <h3 className="mt-4 text-base font-semibold text-fg">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
            <p className="mt-auto pt-4 font-mono text-[10px] tracking-wide text-muted uppercase">
              {step.tag}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
