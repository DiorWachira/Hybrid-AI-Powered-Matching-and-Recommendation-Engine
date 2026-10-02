# Public Demo Deployment

Status (2026-10-01): **not deployed**. The user permits Oracle Always Free only
if no payment is required. No provider account, VM, hostname or credentials have
been configured here. This guide is a preparation plan, not deployment evidence.

## Recommended Host

Oracle Cloud Always Free Ampere A1, subject to capacity and account eligibility.
Current documentation lists 1,500 OCPU-hours and 9,000 GB-hours monthly, equivalent
to a total of 2 OCPUs and 12 GB RAM for Always Free tenancies. Verify the console
allowance before selecting a shape; older 4-OCPU/24-GB tutorials are not the basis
for this plan. Python/ML dependencies on Linux ARM still need an installation and
memory test. Do not silently fall back to a paid or undersized instance.

Use an eligible Ubuntu image in the home region, an Always Free-labelled boot
volume within the total storage allowance, and only resources explicitly shown
as free. Oracle may require card verification; enter it only on Oracle's site.
Capacity is not guaranteed and idle VMs may be reclaimed.

Cost guardrails:

- Do not upgrade to Pay As You Go, select paid shapes or rely on trial credits.
- Stop if provisioning shows a charge or free eligibility is unclear.
- Check all resources, including storage/networking, against current allowances.
- Do not add paid load balancers, GPUs, backups or paid DNS/domain purchases.
- A budget alert is not a hard spending cap. Never promise unconditional zero cost.
- Back up demo data; Always Free is not an uptime or durability guarantee.

A single VM can host Caddy, the built React app, FastAPI and private PostgreSQL/
Neo4j containers, subject to memory benchmarking. This preserves the existing
architecture and avoids extra accounts. Native PostgreSQL on the user's PC need
not be changed or migrated. Start with new, isolated synthetic demo data.

Optional managed stores, only after a separate choice: Neon Free PostgreSQL and
Neo4j AuraDB Free. They have quotas, inactivity policies and different operational
requirements; set SSL/TLS connection URLs and do not assume existing local data
has been transferred.

## Why Not the Other Free Hosts?

- Hugging Face docs currently require a paid plan to create Docker Spaces despite
  zero-hourly-cost CPU Basic; outbound port restrictions also conflict with direct
  PostgreSQL/Bolt access. It is not a no-payment recommendation for this app.
- Render Free provides 512 MB RAM and sleeps after inactivity. The current
  sentence-transformers/PyTorch stack is not verified to fit. Free Render Postgres
  expires after 30 days. Do not label a static frontend-only deployment a live engine.

## Public Request Path

```text
Browser -> HTTPS Caddy -> built frontend files
                      -> /api/* -> FastAPI on 127.0.0.1:8000
                                     -> PostgreSQL on loopback 5433
                                     -> Neo4j on loopback 7687
```

Use one origin so the current frontend `/api` calls work without code changes.
Vite's development proxy is not a production server. Database/viewer ports and
the API's internal port must not be internet-accessible. Allow public 80/443 only;
restrict SSH to the administrator's source IP in both the cloud and OS firewall.

Example Caddy configuration below is **not yet validated on a provisioned host**.
It assumes Caddy installed on the VM, a hostname pointing to it, readable frontend
build output, and a supervised backend listening only on loopback:

```caddyfile
{$APP_DOMAIN} {
    encode gzip
    request_body {
        max_size 11MB
    }
    @api path /api /api/*
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        root * /srv/jobbridge/frontend/dist
        try_files {path} /index.html
        file_server
    }
}
```

The `/api` prefix is preserved. Unknown API paths remain API errors rather than
HTML. Client-side routes fall back to the frontend entry point. Configure
`APP_DOMAIN` in the Caddy service environment, validate with `caddy validate`,
then verify certificate issuance and route behavior externally. A hostname/DNS
choice is still needed; no domain purchase is authorized.

## Provisioning Gates

1. User creates/verifies the Oracle account directly and confirms an Always
   Free-eligible VM is available with no paid resources. Do not send card details,
   passwords, SSH private keys or tokens through chat.
2. Resolve the high-priority public-release findings in
   [IMPLEMENTATION_AUDIT.md](IMPLEMENTATION_AUDIT.md). Until then, keep the instance
   private or limited to approved testers; do not collect real CVs.
3. On the VM, install supported Python 3.12, Node.js, Caddy and Docker using their
   official installation instructions. Confirm ARM wheels/install and resource
   usage before treating the host as suitable. No container build was tested here.
4. Deploy a reviewed feature-branch commit only. Do not merge/push main. Exclude
   local `.env`, Chapter 5 notes, notebook working changes, raw CVs and review
   checkpoints. There is no authorized deployment commit yet.
5. Configure a root `.env` privately, readable only by the backend service user.
   Set `ENVIRONMENT=production`, an independently generated `JWT_SECRET` of at
   least 32 characters, and `CORS_ORIGINS=["https://your-hostname"]`. Use unique
   DB/Neo4j credentials with matching connection URLs. Settings guards cover JWT
   and browser origins, NOT all deployment safety requirements.
6. Start only PostgreSQL/Neo4j from Compose; do not launch public DB viewers.
   Port mappings are now loopback. Validate Neo4j startup rather than relying on
   the existing disabled-strict-validation workaround. Check resource use.
7. Install backend requirements in the host venv and run `alembic upgrade head`
   from `backend/` as a controlled deployment step, before starting API workers.
   Back up before future migrations; do not run concurrent automatic migrations.
8. Build with `npm --prefix frontend run build`. Run FastAPI under a dedicated
   non-root supervisor/service, one worker initially, no reload, bound to
   `127.0.0.1:8000`. Verify model download/cache permissions. No training is needed.
9. Configure Caddy/DNS/HTTPS and complete the acceptance checks below. Add abuse
   throttling and upload resource controls before unrestricted exposure. Avoid
   deploying shared seed passwords; create independent synthetic demo accounts.

## Acceptance Checklist

- [ ] Host bills/limits show only Always Free resources; no paid upgrade.
- [ ] Reviewed commit recorded; Linux ARM install/build succeeds within RAM/disk.
- [ ] HTTPS works from another device; `/auth` reloads and assets render.
- [ ] `/api/health` returns `status: ok` and BOTH databases `ok`. HTTP 200 alone
      is insufficient because the current endpoint also returns 200 when degraded.
- [ ] Candidate/recruiter signup and login work with real tokens; unauthorized,
      expired-token and wrong-owner requests fail without data disclosure.
- [ ] Synthetic CV upload creates the expected PostgreSQL data and Neo4j links;
      malformed/oversized uploads fail safely.
- [ ] Recruiter creates a job and evaluates it; results persist. Another recruiter
      cannot evaluate it. Hard-rule failures do not appear in candidate For You.
- [ ] Save/history survive reload and sign-in; no data crosses account boundaries.
- [ ] Model parity and measured latency are recorded; scores are labelled as
      experimental until independently validated, not certified probabilities.
- [ ] VM/service restart preserves records and reloads artifacts correctly.
- [ ] Backup/restore tested; admin/DB ports closed externally; logs omit tokens/CVs.

Only after these checks may a real public URL be reported as working. A public
health endpoint or frontend build alone is not a completed deployment.

## Provider References

Terms change; recheck when provisioning:

- [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Free Tier and verification](https://www.oracle.com/cloud/free/)
- [Neon plans](https://neon.com/pricing)
- [Aura instance creation](https://neo4j.com/docs/aura/getting-started/create-instance/)
- [Hugging Face Spaces limits](https://huggingface.co/docs/hub/spaces-overview)
- [Render Free limitations](https://render.com/docs/free)