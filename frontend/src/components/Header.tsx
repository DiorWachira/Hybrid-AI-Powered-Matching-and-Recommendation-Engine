import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Menu, Network, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { getSessionRole } from "../lib/session";

const links = [
  { label: "The approach", href: "/#approach" },
  { label: "About us", href: "/#about" },
  { label: "Questions", href: "/#questions" },
  { label: "Contact", href: "/#contact" },
];

export function Header() {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  const role = getSessionRole();
  const workspace = role === "admin" ? "/admin" : role === "candidate" ? "/candidate" : "/recruiter";
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
      else window.scrollTo(0, 0);
    });
    return () => cancelAnimationFrame(frame);
  }, [location.pathname, location.hash, location.key]);
  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); toggle.current?.focus(); } };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [open]);

  return <header className="public-header">
    <nav className="public-container public-nav" aria-label="Public navigation">
      <Link to="/" className="brand-lockup" onClick={() => setOpen(false)} aria-label="JobBridge home"><span className="brand-symbol"><Network size={22} /></span><span>JobBridge<span className="brand-dot">.</span></span></Link>
      <div className="public-desktop-nav">{links.map((link) => <Link key={link.href} to={link.href}>{link.label}</Link>)}</div>
      <div className="public-header-actions"><Link className="public-signin" to={role ? workspace : "/auth"}>{role ? "Workspace" : "Sign in"}</Link><Link className="public-button public-header-start" to="/#join">Get started<ArrowUpRight size={16} /></Link><button ref={toggle} type="button" className="public-menu-toggle" aria-expanded={open} aria-controls="public-mobile-nav" aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen((value) => !value)}>{open ? <X size={22} /> : <Menu size={22} />}</button></div>
    </nav>
    {open && <nav id="public-mobile-nav" className="public-mobile-nav public-container" aria-label="Mobile public navigation">{links.map((link) => <Link key={link.href} to={link.href} onClick={() => setOpen(false)}>{link.label}<ArrowUpRight size={16} /></Link>)}<Link to="/auth?mode=register&role=candidate" onClick={() => setOpen(false)}>Join as a candidate<ArrowUpRight size={16} /></Link><Link to="/auth?mode=register&role=recruiter" onClick={() => setOpen(false)}>Join as a recruiter<ArrowUpRight size={16} /></Link></nav>}
  </header>;
}
