import { ArrowRight, ShieldCheck } from "lucide-react";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { MatchTelemetryCard } from "./MatchTelemetryCard";

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      {/* Warm canvas wash keeps the 60% neutral dominant while hinting at the gold accent. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_15%_0%,rgba(212,175,55,0.12),transparent_70%)]"
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 lg:grid-cols-[1.05fr_1fr] lg:py-24">
        <div>
          <Badge tone="outline">
            <ShieldCheck className="h-3 w-3" aria-hidden />
            Rule-based precision + machine learning
          </Badge>

          <h1 className="mt-5 text-4xl leading-[1.08] font-bold text-emerald sm:text-5xl lg:text-6xl">
            Talent matching that reads past the keywords.
          </h1>

          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
            Conventional applicant tracking throws away good people for missing a
            word. JobBridge clears non-negotiables first, then scores what is
            actually left: meaning, transferable skill, and room to grow — and
            shows its working both ways.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button variant="gold">
              Find Your Next Role
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
            <Button variant="emerald">Request Team Access</Button>
          </div>

          <dl className="mt-10 grid max-w-md grid-cols-3 gap-6 border-t border-emerald/15 pt-6">
            {[
              { v: "2", l: "tier pipeline" },
              { v: "5", l: "role families" },
              { v: "KES", l: "salary aware" },
            ].map((item) => (
              <div key={item.l}>
                <dt className="font-mono text-2xl font-semibold text-emerald">{item.v}</dt>
                <dd className="mt-0.5 text-xs text-muted">{item.l}</dd>
              </div>
            ))}
          </dl>
        </div>

        <MatchTelemetryCard />
      </div>
    </section>
  );
}
