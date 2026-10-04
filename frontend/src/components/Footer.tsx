import { ArrowUpRight, Network } from "lucide-react";
import { Link } from "react-router-dom";

const columns = [
  { title: "Make a connection", links: [["For candidates", "/auth?mode=register&role=candidate"], ["For recruiters", "/auth?mode=register&role=recruiter"], ["Sign in", "/auth"]] },
  { title: "Get to know us", links: [["About JobBridge", "/#about"], ["Our approach", "/#approach"], ["Common questions", "/#questions"]] },
  { title: "The details", links: [["Data & privacy", "/privacy"], ["Prototype use", "/terms"], ["Project & feedback", "/#contact"]] },
];

export function Footer() {
  return <footer className="public-footer"><div className="public-container">
    <div className="public-footer-grid"><div><Link to="/" className="brand-lockup"><span className="brand-symbol"><Network size={22} /></span><span>JobBridge<span className="brand-dot">.</span></span></Link><p>Better context.<br />More considered connections.</p><a className="public-footer-project" href="https://github.com/DiorWachira/Hybrid-AI-Powered-Matching-and-Recommendation-Engine" target="_blank" rel="noopener noreferrer">Explore the project<ArrowUpRight size={15} /></a></div>{columns.map((column) => <nav key={column.title} aria-label={column.title}><h3>{column.title}</h3><ul>{column.links.map(([label, href]) => <li key={href}><Link to={href}>{label}</Link></li>)}</ul></nav>)}</div>
    <div className="public-footer-bottom"><span>© {new Date().getFullYear()} JobBridge</span><span>Built with a Kenyan workforce perspective.</span><span>Academic project / Experimental matching</span></div>
  </div></footer>;
}
