import { ArrowRight, ArrowUpRight, BriefcaseBusiness, Check, Fingerprint, GitBranch, HeartHandshake, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { Header } from "../components/Header";
import { Hero } from "../components/Hero";
import { Footer } from "../components/Footer";

const questions = [
  ["Who is JobBridge for?", "Candidates exploring their next role and recruiters looking for relevant skills. Each has a separate workspace and account type."],
  ["Is this a recruitment agency?", "No. JobBridge is an academic software prototype exploring workforce matching in a Kenyan context. It does not represent employers or guarantee employment."],
  ["What does a matching score mean?", "It is an experimental signal based on the current matching implementation, not a hiring probability. Training and serving features are still being validated. Human review remains essential."],
  ["Are the people and opportunities in the demo real?", "The demonstration includes fictional candidate profiles and sample jobs. Demo accounts are labelled in administration; sample names and scores are not testimonials or employment outcomes."],
  ["Can I upload a CV?", "The candidate workspace accepts readable PDF and DOCX files up to 10 MB. For this demonstration, use a sample CV without sensitive personal information. Scanned image-only documents may not contain extractable text."],
  ["Is JobBridge ready for public hiring decisions?", "Not yet. Independent model evaluation, fairness assessment and deployment safeguards are still in progress. This build is for exploration and project demonstrations, not automated hiring decisions."],
] as const;

export function HomePage() {
  return <div className="public-site">
    <a className="skip-link" href="#public-main">Skip to content</a>
    <Header />
    <main id="public-main">
      <Hero />
      <div className="public-principles"><div className="public-container"><span><Fingerprint size={18} />Skills before assumptions</span><span><GitBranch size={18} />Context beyond keywords</span><span><HeartHandshake size={18} />People make the decision</span></div></div>

      <section className="public-section public-container" id="opportunities" aria-labelledby="opportunities-title">
        <div className="public-section-heading"><p className="public-kicker">Two starting points</p><h2 id="opportunities-title">Your next chapter.<br />Someone else's missing piece.</h2><p>Good work starts when the right people find each other.</p></div>
        <div className="public-paths">
          <article className="public-path"><span className="public-path-icon"><UserRound size={26} /></span><p className="public-kicker">For candidates</p><h3>Bring more of<br />your potential.</h3><p>Your experience is more than a job title. Practical skills, professional qualifications and the things you are ready to learn all deserve context.</p><ul><li><Check size={16} />A profile built around your experience</li><li><Check size={16} />Opportunities and skill-level explanations</li><li><Check size={16} />Saved roles and application activity</li></ul><Link to="/auth?mode=register&role=candidate" className="public-text-link">Create a candidate account<ArrowRight size={18} /></Link></article>
          <article className="public-path"><span className="public-path-icon recruiter"><BriefcaseBusiness size={26} /></span><p className="public-kicker">For recruiters</p><h3>See the person<br />behind the profile.</h3><p>A useful shortlist makes its reasoning visible. Start with clear requirements, then consider the skills and experience behind each result.</p><ul><li><Check size={16} />Job requirements with clear boundaries</li><li><Check size={16} />Ranked candidates and skill gaps</li><li><Check size={16} />A starting point for human review</li></ul><Link to="/auth?mode=register&role=recruiter" className="public-text-link">Create a recruiter account<ArrowRight size={18} /></Link></article>
        </div>
      </section>

      <section className="public-approach" id="approach" aria-labelledby="approach-title"><div className="public-container public-section">
        <div className="public-section-heading"><p className="public-kicker">The approach</p><h2 id="approach-title">A match should come<br />with a reason.</h2><p>Clear requirements. Relevant signals. Room for human judgement.</p></div>
        <div className="public-steps">
          <article><div><span>01</span><ShieldCheck size={24} /></div><h3>Eligibility first</h3><p>Experience, location, salary and required qualifications establish the boundaries before a profile is scored.</p></article>
          <article><div><span>02</span><Sparkles size={24} /></div><h3>Relevance, considered</h3><p>Text similarity and structured skills add context to the comparison. Current scores are experimental, not predictions of success.</p></article>
          <article><div><span>03</span><GitBranch size={24} /></div><h3>Relationships, visible</h3><p>Skill connections and saved explanations make the result easier to inspect. The graph is context, not a substitute for a decision.</p></article>
        </div>
      </div></section>

      <section className="public-section public-container public-about" id="about" aria-labelledby="about-title">
        <div><p className="public-kicker">About JobBridge</p><h2 id="about-title">Built for a more<br />considered connection.</h2><div className="public-project-label"><span />Academic research prototype</div></div>
        <div className="public-about-copy"><p className="public-lead">Talent is everywhere.<br />The connection isn't always obvious.</p><p>JobBridge explores a simple question: can matching be more useful when it brings requirements, skills and context into the same conversation?</p><p>Developed as an academic project with a Kenyan workforce focus, it combines rule-based eligibility, machine-learning signals and knowledge-graph explanations. Local locations, salary expectations in Kenyan shillings and varied career paths shape the demonstration.</p><p>This is a work in progress. Demonstration data is fictional, model validation is ongoing, and the final judgement belongs to people.</p><Link className="public-text-link" to="/privacy">Our data and privacy notes<ArrowUpRight size={17} /></Link></div>
      </section>

      <section className="public-faq" id="questions" aria-labelledby="questions-title"><div className="public-container public-section public-faq-layout"><div><p className="public-kicker">Before you begin</p><h2 id="questions-title">A few good<br />questions.</h2></div><div>{questions.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></div></section>

      <section className="public-join" id="join"><div className="public-container"><div><p className="public-kicker">Make the connection</p><h2>Start with what<br />you bring.</h2></div><div className="public-join-actions"><Link className="public-button" to="/auth?mode=register&role=candidate">I'm looking for work<ArrowRight size={18} /></Link><Link className="public-button secondary" to="/auth?mode=register&role=recruiter">I'm looking for talent<ArrowRight size={18} /></Link><p>Already have an account? <Link to="/auth">Sign in</Link></p></div></div></section>
      <section className="public-contact public-container" id="contact"><div><h2>Help shape what comes next.</h2><p>Project questions, feedback or a problem to report?</p></div><a className="public-text-link" href="https://github.com/DiorWachira/Hybrid-AI-Powered-Matching-and-Recommendation-Engine/issues" target="_blank" rel="noopener noreferrer">Project &amp; feedback<ArrowUpRight size={18} /></a></section>
    </main>
    <Footer />
  </div>;
}