import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { getSessionRole } from "../lib/session";

const destinations = {
  candidate: { to: "/candidate", label: "Back to my opportunities" },
  recruiter: { to: "/recruiter", label: "Back to the recruiter workspace" },
  admin: { to: "/admin", label: "Back to the admin overview" },
} as const;

export function NotFoundPage() {
  const role = getSessionRole();
  const destination = role ? destinations[role] : { to: "/", label: "Back to JobBridge" };
  return <div className="public-site"><a className="skip-link" href="#public-main">Skip to content</a><Header /><main id="public-main" className="public-container public-section public-information"><p className="public-kicker">404 / Page not found</p><h1>This page does not exist.</h1><p className="public-lead">The link may be out of date, or the address may have a typo.</p><Link to={destination.to} className="public-text-link"><ArrowLeft size={16} />{destination.label}</Link></main><Footer /></div>;
}
