# Mode-B Fresh-Checkout Demo

This guide runs the synthetic Phase-1 path only. It uses local PostgreSQL, temporary Git
repositories, recorded mining output, and the generated Java application path. It does not
connect to customer repositories, shared AWS resources, or external LLM providers.

Architecture context: [architecture design](../architecture.md), [implementation
plan](../IMPLEMENTATION_PLAN.md), and [product requirements](../prd.md).

## Prerequisites

- Git 2.40 or newer.
- Docker Desktop/Engine with Compose.
- `uv` and CPython 3.12.
- JDK 17 (`JAVA_HOME` must identify it).
- Node.js 24 and pnpm 9.
- One launcher shell: Bash on Linux/macOS, or PowerShell 7 (`pwsh`) on Windows.
- Local ports `55432` (PostgreSQL), `8100` (API), and `5173` (UI) available.

No credentials are required. Copying `.env.example` is optional; it contains local-only
defaults. Never put production credentials in site YAML or commit `.env`.

## Bootstrap

From the repository root:

```bash
docker compose -p brp -f docker/docker-compose.yml up -d postgres
uv sync --project platform --frozen
uv sync --project mcp-db-connector --frozen
pnpm --dir ui install --frozen-lockfile
```

On Windows, confirm the side-by-side JDK before running the demo:

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

## Run

Linux/macOS:

```bash
bash scripts/demo-mode-b.sh
```

Windows PowerShell 7:

```powershell
pwsh -File scripts/demo-mode-b.ps1
```

The two launchers call the same `scripts/demo_mode_b.py` workflow. It migrates the local
repository database, ingests a traced candidate and dispositions its unmappable fragment,
approves lookup and golden evidence, applies maker-checker with `maker-a`/`checker-b`, creates
the seam baseline, executes the pre-change application, approves the `<19` revision, gates and
pushes a local review branch, then executes a fresh clone of that branch.

Expected output includes these lines (hashes and the run-specific key vary):

```text
BEFORE: ELIGIBLE
AFTER: REJECTED(UNDER_AGE)
EXECUTOR: GENERATED_JAVA
REVISION: demo_enrollment_<run>@2
SUITE: r2 <sha256>
LOOKUP: <sha256>
MANIFEST: <sha256>
BRANCH: rules/gen-demo_enrollment_<run>-r2
DELIVERY COMMIT: <git-sha>
```

## Authority and security boundaries

Zen preview is always `ADVISORY` in Mode B. Only generated Java compiled and tested inside the
target application is `AUTHORITATIVE`; the demo's `EXECUTOR: GENERATED_JAVA` line comes from a
fresh delivered-branch clone. Database discovery is bounded and read-only, dynamic identifiers
are catalog-allowlisted, generated delivery copies only manifest-listed files, and no delivery
branch is created until generated and target regression tests pass.

The Phase-1 demo uses development actor headers only when
`BRP_LOCAL_DEVELOPMENT_HEADERS=true`; the production/default API rejects those headers. Phase 2
validates OIDC JWT signature, issuer, audience, issued-at, expiry, and subject against configured
JWKS, then enforces `maker`, `checker`, `reviewer`, and `deployer` roles. Customer IdP metadata,
role/group mapping, provider policy, and real repository/schema inputs remain human-gated.

## Troubleshooting

- `pwsh` not found: install PowerShell 7; legacy `powershell.exe` can validate the script on
  Windows but is not the documented cross-platform command.
- `/bin/bash` not found on Windows: install a WSL distribution or use PowerShell 7.
- PostgreSQL connection refused: rerun the Compose command and wait for
  `docker compose -p brp -f docker/docker-compose.yml ps` to show `healthy`.
- Java toolchain mismatch: ensure `java -version` reports 17 and reset `JAVA_HOME`.
- A delivery gate failure intentionally leaves a detached evidence workspace and a
  `.failure.md` report; it creates neither a branch nor a commit.
- To validate this guide without running the multi-minute demo:

```bash
uv run --project platform python scripts/verify_fresh_checkout.py --guide docs/demo.md
```
