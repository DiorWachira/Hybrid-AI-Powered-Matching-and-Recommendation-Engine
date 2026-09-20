import { ArrowRight } from "lucide-react";
import { Button } from "./ui/Button";

export function FinalCta() {
  return (
    <section id="enterprise" className="mx-auto max-w-6xl px-5 pb-16 lg:pb-24">
      <div className="relative overflow-hidden rounded-card bg-emerald px-6 py-14 text-center text-canvas sm:px-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(50%_60%_at_50%_0%,rgba(212,175,55,0.22),transparent_70%)]"
        />
        <div className="relative mx-auto max-w-2xl">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Stop screening on keywords.
          </h2>
          <p className="mt-4 text-canvas/70">
            Whether you are looking for the next role or the next hire, the
            matching runs the same way — and shows you why.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button variant="gold">
              Find Your Next Role
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
            <Button variant="onEmerald">Request Team Access</Button>
          </div>
        </div>
      </div>
    </section>
  );
}
