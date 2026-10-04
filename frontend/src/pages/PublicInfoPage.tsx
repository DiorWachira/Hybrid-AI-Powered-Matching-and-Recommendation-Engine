import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";

const content = {
  privacy: {
    title: "Data & privacy notes",
    intro: "A practical overview for this academic demonstration, not a claim of production privacy certification.",
    sections: [
      ["What the prototype stores", "Account email and password hash; profile details, skills and qualifications; job postings; applications and saved activity; matching results and selected audit events. Recruiter contact and company details are also stored."],
      ["Resumes and matching", "Uploaded PDF/DOCX documents are parsed by the backend. Extracted text and skills can be retained in the profile; the original upload is not retained by the application. Identifier redaction is best effort, not a guarantee of anonymity. Use fictional sample CVs without sensitive personal information for demonstrations."],
      ["Access and storage", "PostgreSQL holds account and workflow records. Neo4j holds projected skill and job relationships. Access is role-restricted, and administrators can oversee accounts and activity. Signing in stores a session token in your browser. It stops being valid when it expires; sign-out removes it and clears local account context."],
      ["Retention and limitations", "Automatic retention and self-service account deletion are not yet implemented. Records remain in the configured databases until removed through authorized maintenance. Do not treat this demonstration as a production service for confidential recruitment records."],
      ["External services", "Page fonts may load from Google Fonts. The embedding model is obtained from its public model repository, while inference runs in the backend. External project and feedback links take you to GitHub, which has its own policies. Do not post CVs, credentials or personal account information in public issues."],
    ],
  },
  terms: {
    title: "Prototype use notes",
    intro: "JobBridge is an academic research prototype for demonstrations and evaluation.",
    sections: [
      ["Demonstration, not a hiring decision", "Matching scores are experimental and are not employment guarantees, verified hiring probabilities or a replacement for human review. Training/serving parity and independent quality and fairness evaluation remain in progress."],
      ["Use data responsibly", "Only submit information you have permission to use. Prefer fictional records for demonstrations. Do not upload sensitive identity documents, credentials, malicious files or another person's private information."],
      ["Accounts and access", "Candidates and recruiters have separate permissions. Administrator access is provisioned separately. Do not bypass role restrictions or use shared demonstration accounts for real recruitment activity."],
      ["Scope and availability", "JobBridge does not act as a recruitment agency, process payments, create employment contracts or guarantee continuous availability. Features and demonstration records may change as the project develops."],
      ["Project feedback", "Questions and technical issues can be raised through the linked project repository. Keep public reports free of private information. These notes describe the current prototype and do not replace deployment-specific policies required before a public service is launched."],
    ],
  },
} as const;

export function PublicInfoPage({ kind }: { kind: keyof typeof content }) {
  const page = content[kind];
  return <div className="public-site"><a className="skip-link" href="#public-main">Skip to content</a><Header /><main id="public-main" className="public-container public-section public-information"><Link to="/" className="public-text-link"><ArrowLeft size={16} />Back to JobBridge</Link><p className="public-kicker">Project transparency / October 2026</p><h1>{page.title}</h1><p className="public-lead">{page.intro}</p>{page.sections.map(([title, text]) => <section key={title}><h2>{title}</h2><p>{text}</p></section>)}</main><Footer /></div>;
}