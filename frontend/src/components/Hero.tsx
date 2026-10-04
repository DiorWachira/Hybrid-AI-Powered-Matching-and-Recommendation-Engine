import { ArrowDown, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

export function Hero() {
  return <section id="top" className="public-hero" aria-labelledby="home-title">
    <img src="/media/workspace.jpg" className="public-hero-image" alt="A sunlit shared workspace with desks and plants" fetchPriority="high" />
    <div className="public-hero-shade" aria-hidden="true" />
    <div className="public-container public-hero-content"><p className="public-kicker">People. Potential. Possibility.</p><h1 id="home-title">JobBridge<span>.</span></h1><p className="public-hero-statement">A better connection<br />starts with your skills.</p><p className="public-hero-copy">For people finding their next role.<br />For teams finding their next great addition.</p><div className="public-hero-actions"><Link to="/auth?mode=register&role=candidate" className="public-button">Find my next role<ArrowRight size={18} /></Link><Link to="/auth?mode=register&role=recruiter" className="public-button ghost">Find the right talent<ArrowRight size={18} /></Link></div><div className="public-hero-bottom"><span>Kenyan workforce focus / Research prototype</span><Link to="/#opportunities" aria-label="Explore candidate and recruiter paths"><ArrowDown size={20} /></Link></div></div>
  </section>;
}
