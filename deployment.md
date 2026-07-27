# Rule Platform EC2 Deployment Record

> Authoritative as-built record for the public pilot deployed on 2026-07-27.
> This document records what is actually running, what was verified, operational
> decisions, rollback evidence, and remaining work. It supersedes stale
> pre-cutover statements for this deployment, but it does not redefine product
> acceptance in [prd.md](prd.md).

## 1. Current live state

| Item | As-built state |
| --- | --- |
| Public URL | `https://rule.13.251.6.169.nip.io` |
| EC2 instance | `i-07af453b12aa01ff2` |
| Elastic IP | `13.251.6.169` |
| Instance type | `t3.medium` (resized from `t3.small`) |
| Root volume | 32 GiB gp3; 5.4 GiB free after the build |
| Release commit | `e571628da7fb3d625687ca373f0d3e31bcf288ca` |
| Release directory | `/opt/brp/releases/e571628da7fb3d625687ca373f0d3e31bcf288ca` |
| Application database | Existing Cloud PostgreSQL database `brp`, PostgreSQL 17.9 |
| Alembic revision | `0009_candidate_package_promotion` |
| Authentication | Local production auth for a public pilot |
| TLS | Let's Encrypt certificate for `rule.13.251.6.169.nip.io`, expires 2026-10-25 |
| Deployment status | Live and verified; public pilot, not enterprise production |

The deployed stack contains only Rule API, worker, and UI. It does not contain
Joern or a Docker PostgreSQL service. The stack uses
[docker/compose.ec2.yml](docker/compose.ec2.yml) and the existing Cloud
PostgreSQL database.

## 2. Scope and boundaries

This deployment is intentionally separate from the existing Knowledge
application and its data:

- Rule Platform has a dedicated hostname-specific nginx virtual host.
- Rule UI listens only on `127.0.0.1:8180`; host nginx is the public TLS
  endpoint.
- `knowledge-api`, `knowledge-api-worker`, `knowledge-demo`, nginx, and Graph
  Explorer remain in place.
- Database migration and database rollback apply only to `brp`. They must never
  be run against or restored over `rag_utils`.
- No Joern service is deployed. The current lightweight analysis workload does
  not require it.

Related operational references are
[architecture.md](architecture.md) and
[docs/production-operations.md](docs/production-operations.md). This file is
the deployment-specific record; the operations document remains the generic
runbook.

## 3. Deployed architecture

Traffic follows this path:

```text
Internet
  -> EC2 security group :80/:443
  -> host nginx (TLS, redirect, security headers, login rate limit)
  -> 127.0.0.1:8180 (Rule UI/reverse proxy)
  -> Rule API
  -> Cloud PostgreSQL database brp

Rule worker
  -> Cloud PostgreSQL database brp
  -> persistent artifact volume brp-ec2_artifacts
```

Runtime images are tagged to the deployed commit:

- `brp-ec2-app:e571628`
- `brp-ec2-ui:e571628`

Running services after cutover:

- `brp-ec2-api-1`: healthy
- `brp-ec2-worker-1`: healthy
- `brp-ec2-ui-1`: healthy, bound only to `127.0.0.1:8180`

Migration is a one-shot Compose job run before API and worker startup. API and
worker do not race to run Alembic during startup. The artifact volume is
persistent across container recreation.

## 4. Work completed

### 4.1 Application and authentication

- Added local production authentication endpoints:
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
  - `POST /api/v1/auth/logout`
- Configured an eight-hour signed session cookie with `HttpOnly`, `Secure`, and
  `SameSite=Lax`.
- Required a per-session CSRF token and allowed-origin check for unsafe
  requests.
- Stored passwords only as Argon2id hashes.
- Configured the pilot identities:
  - `maker`: role `maker`
  - `approver`: roles `checker`, `reviewer`, and `deployer`
- Disabled development identity headers in the public deployment. Browser
  supplied `X-BRP-Actor` and `X-BRP-Roles` values fail closed.
- Preserved the rule that an approver must differ from the creator/submitter.
- Added login, route guards, logout, and session-expired behavior to the UI.
- Protected business APIs; only health and authentication endpoints are
  intentionally unauthenticated. Public `/metrics` is not exposed.

Secret files are outside the repository:

| File | Ownership | Mode |
| --- | --- | --- |
| `/opt/brp/secrets/users.json` | `0:10001` | `0440` |
| `/opt/brp/secrets/session-secret` | `0:10001` | `0440` |

Passwords and secret values are deliberately absent from this document.
Credentials were handed over separately. After a deployment test artifact
exposed the first generated maker password, both passwords were rotated,
`sessionVersion` was increased to `2`, the session secret was rotated, API and
worker were restarted, and local temporary credential/runtime files were
deleted. All earlier sessions were thereby revoked.

### 4.2 Container and host runtime

- Added the EC2/external-RDS Compose runtime with no PostgreSQL or Joern
  service.
- Added `.dockerignore`.
- Built the worker image with Git, GitHub CLI, OpenJDK 17 JDK, and the Java
  toolchain.
- Configured a persistent artifact volume shared by API and worker.
- Added readiness checks for database connectivity, Alembic revision, artifact
  storage, and recent worker heartbeat.
- Resized the instance from `t3.small` to `t3.medium`.
- Retained the 32 GiB gp3 root volume because the post-build free space was
  5.4 GiB, above the 5 GiB expansion threshold.
- Opened security-group port 443 publicly and kept port 80 for redirect and
  ACME.
- Removed the temporary deployment SSH rule for `14.191.164.153/32` after the
  deployment completed.

### 4.3 TLS and nginx

- Added a hostname-specific Rule virtual host without changing existing
  Knowledge routes.
- Verified HTTP-to-HTTPS redirect and public security headers.
- Issued the production Let's Encrypt certificate after an ACME staging
  dry-run.
- Verified a production renewal dry-run.
- Enabled `brp-certbot-renew.timer`, scheduled twice daily.

The host Python 3.9 runtime cannot install the required Certbot 5.x cleanly.
Certbot 5.7.0 therefore runs through the official
`certbot/certbot:v5.7.0` container using the wrapper at
`/opt/certbot/bin/certbot`. The `nip.io` certificate succeeded, so the
short-lived IP-certificate fallback was not needed.

### 4.4 Data protection and rollback preparation

- Recorded the pre-migration Alembic revision:
  `0009_candidate_package_promotion`.
- Created and verified the database-specific custom-format dump:
  `/opt/brp/backups/brp-pre-73c91d3-20260727-070750.dump`.
- Stored its checksum beside it:
  `/opt/brp/backups/brp-pre-73c91d3-20260727-070750.dump.sha256`.
- Verified SHA-256:
  `f4a56a689a5945f02a55e19d9722e4d9fa88dd9d36ec2381d4749895c864335b`.
- Created the RDS manual snapshot
  `csax-rag-utils-pre-brp-20260727-070359` and verified it reached
  `available`.
- Preserved nginx backups under `/opt/brp/nginx-backups`.
- Preserved earlier release directories for application rollback.

The RDS snapshot covers the RDS instance. A database-only rollback for Rule
Platform must use the `brp` dump so that unrelated databases are not affected.

## 5. Verification evidence

### 5.1 Pre-deployment gates

All destructive tests used the isolated local PostgreSQL database `brp_test`,
never the shared Cloud `brp` database.

| Gate | Result |
| --- | --- |
| Backend tests | 251 passed; one Starlette deprecation warning |
| Ruff | Clean |
| Strict mypy | Clean across 75 source files |
| UI unit tests | 85 passed in 13 files |
| Playwright E2E | 20 passed; 10 live-only tests skipped |
| UI production build | Passed |
| Container builds | Passed |
| Worker toolchain | Git 2.39.5, GitHub CLI 2.93.0, OpenJDK/Javac 17.0.19, Gradle 8.7 |

### 5.2 Live security and availability

- HTTP redirects to HTTPS with status 301.
- Public HTTPS and readiness return 200.
- Unauthenticated business API requests return 401.
- Public `/metrics` returns 404.
- Responses include HSTS, `X-Content-Type-Options`, `X-Frame-Options`, and
  `Referrer-Policy`.
- Incorrect passwords return a generic 401.
- Burst login attempts are rate-limited at nginx.
- Missing CSRF, forged development headers, tampered cookies, and expired or
  logged-out sessions are rejected.
- Logout succeeds and a subsequent `/auth/me` request is unauthorized.

### 5.3 Governance smoke

Decision `deploy_smoke_20260727072803` completed this workflow:

1. `maker` created the decision.
2. `maker` submitted it.
3. `maker` self-approval was rejected with 403.
4. `approver` rejected it.
5. Final state became `REJECTED`.
6. Audit actors were recorded as `maker`, `maker`, and `approver`.

### 5.4 Product smoke

The following pages rendered live data through the public deployment:

- Overview
- Imports
- Studio
- Reviews
- Test Suites
- Releases
- Sites
- Operations

Existing failed rows/jobs shown in Overview and Operations are real existing
records, not page-load failures. They require product/operations triage but do
not indicate that the deployed pages failed to load.

### 5.5 Existing service preservation

After resize and Rule cutover:

- `knowledge-api`, `knowledge-api-worker`, `knowledge-demo`, and nginx remained
  active.
- Knowledge direct health on port 8080 returned 200.
- The Knowledge default nginx path followed redirects to 200.
- `/demo/` followed redirects to 200.
- Graph Explorer container `csax-graph-explorer` remained up and
  `/graph-explorer/` followed redirects to 200.
- Knowledge health reported S3, PostgreSQL, and Neptune as healthy, at revision
  `51b7276c...`.

## 6. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-001 | Do not deploy Joern | Current workload is lightweight; heavy analysis is evidence-triggered, not a prerequisite. |
| D-002 | Use existing Cloud PostgreSQL `brp` | Avoid a second source of truth and avoid operating a duplicate PostgreSQL container. |
| D-003 | Resize to `t3.medium` | 4 GiB RAM is sufficient for the current API, worker, UI, and build workload. |
| D-004 | Keep the 32 GiB gp3 volume for now | 5.4 GiB remained after build, above the agreed 5 GiB threshold. |
| D-005 | Use local auth only for the public pilot | It closes the public anonymous-access gap while remaining compatible with a later OIDC upgrade. |
| D-006 | Terminate TLS at host nginx | It preserves current host routing and keeps UI inaccessible directly from the internet. |
| D-007 | Run migration as a one-shot job | It prevents concurrent Alembic execution by API and worker containers. |
| D-008 | Keep Rule and Knowledge stacks isolated | A dedicated vhost, release path, Compose project, and database rollback scope reduce blast radius. |
| D-009 | Do not tighten the shared RDS security group in this change | Port 5432 exposure is a shared infrastructure risk; changing it could break existing local/shared workflows. |
| D-010 | Fail closed for identity and browser state | The server owns identity and roles; a browser cannot nominate its actor or privileges. |
| D-011 | Deploy exact commits and immutable image tags | This makes application rollback deterministic. |
| D-012 | Run Certbot 5.7.0 in Docker | The host Python version is incompatible; changing the host Python would add avoidable risk. |
| D-013 | Never document deployment passwords | Passwords are delivered once and rotated independently of Git history. |
| D-014 | Keep the `nip.io` certificate | ACME staging, production issuance, and renewal succeeded; direct IP fallback was unnecessary. |

## 7. Work not completed and known limitations

### P0: required before calling Mode B full-function

- Provide a least-privilege GitHub token through a secret file or runtime
  environment.
- Verify a real remote branch push and real pull request from the deployed
  worker.
- Complete the product-level Java public repository to real PR acceptance flow.
  A healthy cloud deployment alone does not prove this full delivery path.

### P1: production hardening

- Replace local pilot auth with OIDC/SSO and enterprise identity lifecycle.
- Add HA/multi-AZ application topology and an external session store.
- Add WAF/CDN protection as appropriate.
- Add centralized logs, metrics, alerting, and an explicit on-call response
  path.
- Restrict the broadly accessible RDS port 5432 in a separately planned
  infrastructure change after all consumers are inventoried.
- Decide when to clear the intentional `productionBlocked` pilot signal after
  enterprise gates are met.

### P1: capacity and operations

- Monitor root-disk usage. Expand gp3 from 32 to 48 GiB and extend the
  filesystem if free space falls below 5 GiB. Do not delete CSAX data or
  containers to recover space.
- Triage existing failed imports/jobs visible in the live UI.
- Exercise the complete database restore procedure in a non-production
  environment.

### P2: additional acceptance coverage

- Prove the PostgreSQL-table full-flow acceptance path with populated evidence.
- Continue OIDC compatibility tests before enabling OIDC publicly.
- Revisit direct IP certificates only if `nip.io` becomes unavailable or ACME
  fails; it is not part of the current deployment.

The existing LLM key is supplied only at runtime. It is not included in images,
Git, or logs. Its presence does not substitute for the missing GitHub token or
Mode B verification.

## 8. Operational knowledge and gotchas

- Never run destructive pytest suites against shared database `brp`. Use an
  isolated `*_test` database.
- Before any deploy, confirm the active branch/worktree, exact release commit,
  current Alembic revision, free disk space, and listener/container ownership.
- Do not add PostgreSQL or Joern services to the EC2 Compose file without a new
  architecture decision.
- Run migration once and inspect its exit status before starting writers.
- The initial migration image failed before reaching the database because of an
  editable-build path/workdir mismatch. The working image uses a non-editable
  install and `/app` as the correct workdir.
- Keep Rule nginx changes hostname-specific. Do not modify the default Knowledge
  route when deploying or rolling back Rule.
- Certbot renewal depends on Docker and
  `/opt/certbot/bin/certbot`; verify both the timer and renewal dry-run after
  host maintenance.
- Rotate a local user by replacing its Argon2id hash, incrementing
  `sessionVersion`, and restarting API/worker as needed. Rotating the session
  secret revokes all sessions.
- Do not copy secret files into a release directory or container image.

## 9. Safe deployment checklist

Use placeholders for secrets and exact environment values; do not paste secret
contents into shell history or Git.

1. Confirm `dev` is clean and identify the exact commit.
2. Run backend and UI gates against an isolated `*_test` database.
3. Confirm Knowledge health and record EC2/RDS state.
4. Confirm at least 5 GiB projected post-build free space; otherwise expand gp3
   to 48 GiB and extend the filesystem.
5. Record the current Alembic revision.
6. Create a `pg_dump -Fc` of database `brp`, write a checksum, and verify it.
7. Create and wait for the RDS manual snapshot.
8. Copy the exact commit into `/opt/brp/releases/<commit>`.
9. Verify secret ownership `0:10001` and mode `0440`.
10. Build immutable images tagged with the commit.
11. Run the migration job once; stop if it fails.
12. Start API, worker, and UI; wait for healthy containers.
13. Verify public TLS, redirect, auth, CSRF, governance, product pages, and
    `/metrics` isolation.
14. Re-verify Knowledge API, Knowledge Demo, nginx, and Graph Explorer.
15. Remove any temporary SSH security-group rule.

## 10. Rollback

### Application-only rollback

1. Stop only the Rule Compose project.
2. Restore the previous Rule nginx vhost backup if routing changed.
3. Start the previous `/opt/brp/releases/<commit>` with its matching immutable
   image tags.
4. Verify Rule and all existing Knowledge routes.

### Data rollback

1. Stop Rule writers: API and worker.
2. Verify the selected backup checksum.
3. Restore only database `brp` from its custom-format dump.
4. Do not restore over `rag_utils` or other databases.
5. Start the matching application release and verify revision/readiness.

### Instance-size rollback

1. Stop the EC2 instance in a maintenance window.
2. Change it back to `t3.small`.
3. Start it and verify Knowledge health before Rule.
4. Start/verify Rule only if memory pressure remains acceptable.

Rollback completion always requires checking the preserved Knowledge services,
nginx routes, Graph Explorer, public Rule health, authentication, and worker
heartbeat.

## 11. Next handoff

The immediate next delivery milestone is Mode B proof: install a least-privilege
GitHub token as a runtime secret and demonstrate an auditable remote branch and
real pull request. In parallel, schedule the shared RDS security-group review
and monitor the EC2 root volume because the current 5.4 GiB margin is close to
the expansion threshold.
