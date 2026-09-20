import { Terminal } from "lucide-react";

const columns = [
  {
    title: "Platform",
    links: ["Engine", "Roles", "How it Works", "Enterprise"],
  },
  {
    title: "Resources",
    links: ["Documentation", "Evaluation method", "Skill ontology", "Changelog"],
  },
  {
    title: "Company",
    links: ["About", "Privacy", "Terms", "Contact"],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-emerald/15 bg-canvas-sunk">
      <div className="mx-auto max-w-6xl px-5 py-12">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-emerald text-canvas">
                <Terminal className="h-4.5 w-4.5" aria-hidden />
              </span>
              <span className="text-lg font-bold text-emerald">JobBridge</span>
            </div>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
              A hybrid matching and recommendation engine for intelligent
              workforce placement.
            </p>
            <p className="mt-5 inline-flex items-center gap-2 font-mono text-[11px] text-muted">
              <span className="animate-status h-1.5 w-1.5 rounded-full bg-gold" aria-hidden />
              All Systems Operational
            </p>
          </div>

          {columns.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <h3 className="text-sm font-semibold text-emerald">{col.title}</h3>
              <ul className="mt-3 space-y-2">
                {col.links.map((link) => (
                  <li key={link}>
                    <a
                      href="#top"
                      className="text-sm text-muted transition-colors hover:text-emerald"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-emerald/12 pt-6">
          <p className="font-mono text-[11px] text-muted">
            © {new Date().getFullYear()} JobBridge — academic project build
          </p>
          <p className="font-mono text-[11px] text-muted">Nairobi, Kenya</p>
        </div>
      </div>
    </footer>
  );
}
