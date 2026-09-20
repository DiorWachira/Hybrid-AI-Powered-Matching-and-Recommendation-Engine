import { engineMetrics } from "../lib/demoMatch";
import { Badge } from "./ui/Badge";

export function EngineMetrics() {
  return (
    <section id="engine" className="bg-emerald py-16 text-canvas lg:py-20">
      <div className="mx-auto max-w-6xl px-5">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-xl">
            <Badge tone="gold">Engine telemetry</Badge>
            <h2 className="mt-4 text-3xl font-bold sm:text-4xl">
              Measured, not asserted.
            </h2>
            <p className="mt-4 text-canvas/70">
              Results are read against the achievable ceiling for the evaluation
              set, not against a perfect score. A label that a model could simply
              reconstruct would prove nothing.
            </p>
          </div>
        </div>

        <dl className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {engineMetrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-card border border-canvas/15 bg-emerald-deep/50 p-5 transition-colors hover:border-gold/45"
            >
              <dt className="font-mono text-3xl font-semibold text-gold">{metric.value}</dt>
              <dd className="mt-2">
                <span className="block text-sm font-semibold">{metric.label}</span>
                <span className="mt-1 block text-xs leading-relaxed text-canvas/60">
                  {metric.detail}
                </span>
                {metric.illustrative && (
                  <span className="mt-2 inline-block font-mono text-[10px] text-canvas/40 uppercase">
                    target, not yet measured
                  </span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
