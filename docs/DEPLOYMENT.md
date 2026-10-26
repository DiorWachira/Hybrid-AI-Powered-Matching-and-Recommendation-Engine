# Public Demo Deployment

JobBridge deploys as one Docker Compose stack on one Linux VM:

```text
Browser --HTTPS--> Caddy (web)  -- built React app
                     |  /api/*
                     v
                  FastAPI (api, 1 worker, encoder baked into the image)
                     |-- PostgreSQL 16 (private network only)
                     '-- Neo4j 5      (private network only)
```

Only Caddy publishes ports (80/443). Caddy gets and renews a Let's Encrypt certificate
by itself. The API applies migrations on start, drains the graph outbox in-process and
serves the frontend and API from one origin, so no CORS or proxy changes are needed.

## Why Oracle Cloud Always Free

| Option | RAM | Verdict |
| --- | --- | --- |
| **Oracle Always Free Ampere A1** | up to 24 GB (4 OCPU) per tenancy | **Chosen.** Fits the encoder (~1 GB), Neo4j and PostgreSQL on one VM with room to spare; no expiry |
| Render / Koyeb free web services | 512 MB | PyTorch + MiniLM alone exceeds this; free Postgres expires |
| Fly.io, Railway | trial credit only | Not free beyond the trial |
| Hugging Face Spaces (CPU) | 16 GB | No persistent disk on free tier, no private PostgreSQL/Neo4j |
| Neon + AuraDB Free + a small host | split | Three accounts, quotas and pausing; the host still needs ~2 GB for the model |

A1 instances are ARM (aarch64). Every image used here (python:3.12-slim, the PyTorch CPU
wheels, postgres:16-alpine, neo4j:5-community, caddy:2.8-alpine, node:22-alpine) is
published for arm64, and the stack was tested locally on amd64 with the same files
(2026-10-26: about 1.6 GB RAM in use with demo data loaded).

Cost guardrails: choose only shapes and volumes labelled **Always Free-eligible**; a
student or trial credit balance must not be what pays for the VM. Do not add load
balancers, block-volume backups or paid DNS. Oracle may reclaim an Always Free VM it
considers idle (very low CPU, network and memory use over 7 days); a demo that is
used occasionally is normally fine, and upgrading the account to Pay As You Go removes
reclamation while Always Free resources stay free.

## 1. Create the VM (Oracle console, done by the account owner)

1. Sign in at <https://cloud.oracle.com>. Never share the password, MFA codes or keys in chat.
2. **Compute -> Instances -> Create instance**
   - Name: `jobbridge`
   - Image: **Canonical Ubuntu 24.04** (the aarch64 build is picked automatically for A1)
   - Shape: **Ampere -> VM.Standard.A1.Flex**, **2 OCPU / 12 GB** (or 4 / 24 if your
     Always Free allowance shows it). Check the "Always Free-eligible" label.
   - Networking: create a new VCN with a **public subnet**; **assign a public IPv4 address**.
   - SSH keys: **Generate a key pair** and download the private key (or paste your own
     public key). Keep the private key file private.
   - Boot volume: default (about 47 GB) is enough and within the 200 GB free total.
   - "Out of capacity" means the region has no free A1 right now: try another
     availability domain or retry later.
3. **Open the web ports** in the cloud firewall: Networking -> Virtual cloud networks ->
   the VCN -> the public subnet -> Default Security List -> **Add Ingress Rules**:
   source `0.0.0.0/0`, TCP, destination port `80`; again for `443`. Optionally restrict
   the existing port 22 rule to your own IP address.
4. Note the instance's **public IP address**.

## 2. Install and start (on the VM)

```bash
ssh -i path/to/private.key ubuntu@<public-ip>
git clone https://github.com/DiorWachira/Hybrid-AI-Powered-Matching-and-Recommendation-Engine.git jobbridge
cd jobbridge
deploy/jb setup <public-ip-with-dashes>.sslip.io     # e.g. 129-151-10-20.sslip.io
```

On an **Oracle Linux** image the user is `opc` instead of `ubuntu`; `deploy/jb setup` detects
it and installs Docker from Docker's RHEL repository and opens the ports in firewalld.

No domain needs to be bought: `sslip.io` resolves `129-151-10-20.sslip.io` to
`129.151.10.20`, and Let's Encrypt issues a certificate for it. A real domain works the
same way: point an A record at the VM and pass that name instead.

`deploy/jb setup` installs Docker from Ubuntu's packages, opens 80/443 in the VM's own
iptables firewall (Oracle images reject them by default), adds swap on small shapes,
writes `deploy/.env.production` with freshly generated secrets (mode 600), installs a
nightly backup job and builds and starts the stack. The first build takes 10-20 minutes
on A1. It finishes by waiting for `/api/health` to report both databases `ok`.

Then:

```bash
deploy/jb admin you@example.org   # create the administrator (prompts for a password)
deploy/jb seed                    # optional: synthetic IT demo data (150 candidates, 30 + 26 jobs)
```

Administrators must enrol an authenticator app on first sign-in. Demo accounts sign in
with the `SEED_PASSWORD` stored in `deploy/.env.production`, not the repository default.

## 3. Operate

| Task | Command |
| --- | --- |
| Status / logs | `deploy/jb status`, `deploy/jb logs api` |
| Deploy a new commit of `main` | `deploy/jb update` (pull, back up, rebuild, restart) |
| Manual backup | `deploy/jb backup` (PostgreSQL + env file), `deploy/jb backup --graph` (adds Neo4j, ~1 min offline) |
| Restore PostgreSQL | `sudo docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production exec -T postgres pg_restore -U jobbridge -d jobbridge --clean < /var/backups/jobbridge/postgres-<stamp>.dump` |

Backups run daily at 03:15 (Neo4j included on Sundays) into `/var/backups/jobbridge`,
keeping 14 days. They live on the same VM; copy them off occasionally
(`scp ubuntu@<ip>:/var/backups/jobbridge/* .`). The env file is backed up with them:
losing `MFA_ENCRYPTION_KEY` voids every two-step enrolment.

Containers restart automatically after a crash or VM reboot (`restart: unless-stopped`).

### Sign in with Google on the public host

Add `https://<APP_DOMAIN>` to the OAuth client's **Authorised JavaScript origins** in
Google Cloud Console, then set `GOOGLE_CLIENT_ID` and `GOOGLE_SIGNIN_EMAILS` in
`deploy/.env.production` and run `deploy/jb up`. The consent screen is in Testing mode,
so only its listed test users can use it.

## Acceptance checklist

- [ ] Oracle shows only Always Free-eligible resources; no charges in Billing.
- [ ] `https://<APP_DOMAIN>` loads with a valid certificate from another device; `/auth` reloads.
- [ ] `/api/health` returns `status: ok` with both databases `ok`.
- [ ] Candidate and recruiter sign-up/sign-in; admin sign-in with two-step verification.
- [ ] Resume upload extracts skills and experience; the skill graph renders within seconds.
- [ ] Recruiter publishes a job and evaluates candidates; results persist after reload.
- [ ] `sudo reboot`, then the site comes back with the same data.
- [ ] `deploy/jb backup` writes a dump; ports 5432/7474/7687/8000 are closed from outside
      (`nc -zv <ip> 5432` fails).

## Limits that remain

Scores come from a model trained on synthetic labels and are experimental, not hiring
probabilities. Rate limiting is per process (fine for one API worker). Use fictional CVs
on the public demo; there is no automatic data retention or self-service deletion.
