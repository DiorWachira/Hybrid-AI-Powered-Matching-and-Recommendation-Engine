import { useState } from "react";
import { Menu, Terminal, X } from "lucide-react";
import { Button } from "./ui/Button";

const links = [
  { label: "Engine", href: "#engine" },
  { label: "Roles", href: "#roles" },
  { label: "How it Works", href: "#how-it-works" },
  { label: "Enterprise", href: "#enterprise" },
];

export function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-surface/95 text-fg backdrop-blur">
      <nav
        aria-label="Primary"
        className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-5 py-3.5"
      >
        <a href="#top" className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-gold text-ink">
            <Terminal className="h-4.5 w-4.5" aria-hidden />
          </span>
          <span className="text-lg font-bold">JobBridge</span>
          <span className="ml-1 hidden items-center gap-1.5 rounded-full border border-line px-2.5 py-1 font-mono text-[10px] tracking-wide uppercase sm:inline-flex">
            <span className="animate-status h-1.5 w-1.5 rounded-full bg-gold" aria-hidden />
            System Live
          </span>
        </a>

        <ul className="hidden items-center gap-7 text-sm lg:flex">
          {links.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="whitespace-nowrap text-muted transition-colors hover:text-gold-bright"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-4 lg:flex">
          <a
            href="#signin"
            className="whitespace-nowrap text-sm text-muted transition-colors hover:text-gold-bright"
          >
            Sign In
          </a>
          <Button variant="gold">Launch Matching Engine</Button>
        </div>

        <button
          type="button"
          className="text-fg lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>

      {open && (
        <div id="mobile-nav" className="border-t border-line px-5 pb-5 lg:hidden">
          <ul className="flex flex-col gap-1 py-3 text-sm">
            {links.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="block rounded-lg px-2 py-2 text-muted hover:bg-fg/10"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
          <Button variant="gold" className="w-full">
            Launch Matching Engine
          </Button>
        </div>
      )}
    </header>
  );
}
