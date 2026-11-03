# Demo walkthrough

A rehearsed script for showing JobBridge end to end. Every step below was run in a browser on 2026-11-03 against the seeded demo data and the production bundle behind the real Caddy configuration, using freshly registered accounts. Sign in with the accounts below once before presenting.

## Before you present

1. **Check the network first.** A Fortinet firewall on the network used for the 2026-11-03 audit blocks `140-238-99-64.sslip.io` ("Application Control Violation", with a re-signed certificate). The server is not at fault, but the site will not open on that network, so test the room's network in advance. Use a phone hotspot, ask IT to allow the host, or run the local stack below.
2. **Open the site once before the session** so the page and model are warm. Check `/api/health` reports `ok` for both databases and `ready` for the model.
3. **Have the admin's authenticator app to hand.** Administrators must enter a 6-digit code.
4. **Sign in on one IP sparingly.** Sign-in is limited to 10 attempts a minute per IP address, and a whole room on shared Wi-Fi counts as one address.

**Local fallback:** `docker compose up -d --wait postgres neo4j`, then start the API and Vite as described in `docs/extras/startup.txt`.

## Accounts

| Role | Account | Password |
|---|---|---|
| Recruiter | `seed-recruiter@jobbridge.example.org` | `SEED_PASSWORD` from your private `.env` |
| Administrator | Your own admin account (`deploy/jb admin`) | Yours, plus an authenticator code |
| Candidate | Register a new one live (step 2) | Choose one with at least 12 characters |

Never put the demo password on a slide or in the repository.

## Sample CVs

Both are fictional and in `docs/demo/`:

- `sample-cv-security-analyst.docx`: Amina Otieno, 5 years, cybersecurity
- `sample-cv-devops.pdf`: Brian Mwangi, 6 years, DevOps

## The script (about 8 minutes)

### 1. The problem (1 minute)
Open the home page and scroll to **Kenya's labour market / In numbers**. Drag across Fig. 3 to show how reading time grows with applications. Point out that it is labelled as an estimate.

### 2. Candidate: from CV to profile (2 minutes)
1. **Create an account** as a candidate named Amina Otieno.
2. Open **Resume**, upload `sample-cv-security-analyst.docx`.
3. Open **Profile** and show the detected skills (SIEM, Incident Response, Network Security and others) and the 5 years of experience read from the CV.
4. Set the location to Nairobi, an expected salary and work authorization, then save.
5. Explain what happens to personal details: name, email and phone are removed from the stored text before scoring.

### 3. Recruiter: publish and rank (3 minutes)
1. Sign in as the recruiter and choose **New job**.
2. Publish a Security Operations Analyst role in Nairobi that requires `SIEM, Incident Response, Network Security, Linux` and 3 years of experience.
3. Open **Match analysis** and select **Evaluate candidates**.
4. Explain the **two tiers**:
   - **Tier 1, eligibility rules:** experience, location, salary, certifications and work authorization. Candidates who fail are excluded, with the reasons shown.
   - **Tier 2, hybrid score:** text relevance, skill alignment and experience readiness, combined by the trained model.
5. Search for Amina. Show her score, matched and missing skills, and the reason for the result.
6. Scroll to **Skill relationships** to show the Neo4j graph and its text equivalent.

### 4. The hiring pipeline (1 minute)
1. As the candidate, open **Browse**, find the role and select **Register interest**.
2. As the recruiter, open the applicants and move Amina to **Shortlisted**.
3. As the candidate, refresh **Applications** to show the new status.

### 5. Administrator (1 minute)
1. Sign in with the password and authenticator code.
2. Show the overview, **Recruiter oversight** and the **Skill ontology** tab.
3. Open **Simulation** and run the sandbox scenario. It uses isolated synthetic data and the same scoring engine.

## Questions to expect

**How accurate is it?** On synthetic held-out data, the hybrid model reaches ROC-AUC 0.807 (warm) and 0.847 (cold). Those labels are synthetic, so they are not evidence of hiring quality. The 150-pair hand-labelled gold slice exists to test that independently.

**Is it fair?** Identifiers are redacted before scoring, but redaction is not proof of anonymity or of the absence of bias. See `docs/BIAS_AND_EXPLAINABILITY.md`.

**How fast is it?** On the test laptop, re-ranking about 170 candidates takes 1 to 2 seconds. See `docs/ROADMAP.txt` for the measurements and where they were taken.
