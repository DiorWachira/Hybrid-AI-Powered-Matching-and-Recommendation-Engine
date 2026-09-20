import { Star } from "lucide-react";
import { testimonials } from "../lib/demoMatch";
import { Badge } from "./ui/Badge";

export function Testimonials() {
  return (
    <section id="roles" className="mx-auto max-w-6xl px-5 py-16 lg:py-24">
      <div className="max-w-2xl">
        <Badge tone="outline">Who it serves</Badge>
        <h2 className="mt-4 text-3xl font-bold text-emerald sm:text-4xl">
          Both sides of the table.
        </h2>
        <p className="mt-4 text-muted">
          Representative scenarios across the role families the engine covers.
        </p>
      </div>

      <div className="mt-12 grid gap-5 lg:grid-cols-3">
        {testimonials.map((t) => (
          <figure
            key={t.name}
            className="flex flex-col rounded-card border border-emerald/12 bg-canvas-sunk/70 p-6 transition-all duration-200 hover:-translate-y-1 hover:border-gold/50 hover:shadow-lg"
          >
            <div className="flex gap-0.5" aria-label={`${t.rating} out of 5`}>
              {Array.from({ length: t.rating }).map((_, i) => (
                <Star key={i} className="h-4 w-4 fill-gold text-gold" aria-hidden />
              ))}
            </div>
            <blockquote className="mt-4 flex-1 text-sm leading-relaxed text-emerald">
              “{t.quote}”
            </blockquote>
            <figcaption className="mt-5 border-t border-emerald/12 pt-4">
              <span className="block text-sm font-semibold text-emerald">{t.name}</span>
              <span className="mt-0.5 block font-mono text-[11px] text-muted">{t.context}</span>
            </figcaption>
          </figure>
        ))}
      </div>

      <p className="mt-6 font-mono text-[11px] text-muted">
        Illustrative scenarios for demonstration — not attributed customer quotes.
      </p>
    </section>
  );
}
