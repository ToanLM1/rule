# Canonical Rules Platform — cloud-local orchestration

The console exposes the durable governed flow:

`source import → evidence-backed candidate → business edit → immutable revision → approval → deterministic Java/tests → Git delivery`.

The old inline Phase-3 workbench and Mode-A routes remain compatibility/historical
capabilities. New application work uses `/api/v1`, the durable worker, and the
active `F-*` roadmap in `IMPLEMENTATION_PLAN.md`.

## Start locally

This workstation uses the shared Singapore RDS instance for the application database. The
ignored repository-root `.env` contains `BRP_DATABASE_URL` and `BRP_PSQL_URL` for database
`brp` with `sslmode=require`. Never commit that file or print either URL.

Required local tools:

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [pnpm](https://pnpm.io/installation)
- [Git for Windows](https://git-scm.com/download/win)
- [Microsoft OpenJDK 17](https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.msi)
- [GitHub CLI](https://cli.github.com/) for the final push/PR acceptance step

The launcher checks all four tools and rejects a Java version other than 17 before
touching the database. From the repository root in PowerShell:

```powershell
uv run --env-file .env --project platform python -m alembic -c platform/alembic.ini upgrade head
uv run --env-file .env --project platform python -m uvicorn brp.api.app:app --host 127.0.0.1 --port 8100
```

In a second terminal, start the worker:

```powershell
uv run --env-file .env --project platform python -m brp.worker
```

In a third terminal:

```powershell
pnpm --dir ui dev --host 127.0.0.1
```

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). Business authoring and
guided PostgreSQL import are under `/studio`; repository imports are under
`/imports`; compatibility governance remains under `/decisions`, `/review` and `/test-suites`; releases
under `/releases`, and worker/job state under `/operations`.

### Use the existing cloud PostgreSQL on this workstation

The current `rule-dev` checkout has no `.env`. The existing ignored
`D:\Graph RAG\rule\.env` points at the shared cloud `brp` database. Load it into each
PowerShell terminal without printing its values, then run the same API/worker commands:

```powershell
Get-Content -LiteralPath 'D:\Graph RAG\rule\.env' | ForEach-Object {
  if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    Set-Item -Path "Env:$($matches[1])" -Value $matches[2]
  }
}
```

Public Java extraction additionally requires one explicit structured-output provider in the
environment used by **both API and worker**:

```dotenv
BRP_LLM_LIVE=true
BRP_LLM_PROVIDER=groq
BRP_LLM_MODEL=openai/gpt-oss-120b
BRP_LLM_MAX_ATTEMPTS=1
BRP_LLM_RESPONSE_FORMAT=json_object
GROQ_API_KEY=<secret-created-in-groq-console>
```

The Groq shorthand supplies `https://api.groq.com/openai/v1` and defaults to
`openai/gpt-oss-120b` for stronger extraction quality. Its free-plan 8K TPM limit means the
bounded prompt, evidence spans, and completion budget must remain compact. It requests JSON-object output;
the compact schema is included in the bounded prompt and Pydantic validates every response
locally. This avoids provider-side schema-validation failures without weakening fail-closed
validation. Both the LLM client and the outer durable public-import job use one attempt so a
malformed response or free-tier 429 is not immediately multiplied by nested retry loops.
Generic `openai-compatible` and `anthropic-compatible` configurations are also supported.
Preflight checks only whether required variables exist; it never returns or logs their values.
With live mode disabled, public Java preflight returns `ready=false` and the UI prevents
queueing instead of falling back to synthetic rules.

Probe first with `uv run --project platform python scripts/check-pg.py`. A fresh 2026-07-23
probe reached cloud PostgreSQL `17.9`; readiness still requires the launcher migration check,
API readiness response, and a fresh worker heartbeat.

For this workstation, the launcher performs that safe probe/migration check and starts API,
worker, and UI in the background:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-cloud-local.ps1
```

Stop only those recorded local processes with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-cloud-local.ps1
```

### Import a public GitHub dummy repository

On **Imports**, choose **Pinned Java repository** and **Public GitHub URL**. Enter a public
`https://github.com/<owner>/<repo>` URL, a branch/tag/commit, repository alias, Java entry class,
and method. Preflight performs a credential-free temporary clone, resolves the revision to an
immutable commit, and validates the subpath and entry point before the durable worker repeats
the pinned checkout.

The verified external extraction target is the public `novoda/dojos` repository at commit
`2e7391623b42617af1bbdad227e3e4701e89af2c`, subpath
`harry-potter/09102010-blundell-xavi`, class `silent.DiscountCalculator`, method `calculate`.
It has separate production/facade/test files and is used read-only. A separate user-owned
repository is still required only for the final generated branch and pull request.

The public path now uses the bounded lightweight evidence agent, not the Phase-1 synthetic
construct miner and not Joern. It requires live structured-provider configuration and fails
closed if cited source spans were not supplied to the model. The recorded provider tests pass,
and a live Groq GPT-OSS 120B durable import produced a compiling discount candidate with exact
source spans, related test evidence and a scenario in one attempt. An earlier 70B candidate
was promoted to Canonical Studio, edited from `-0.8` to `-1.6`, submitted by `maker-a`, and
approved by `checker-b` with semantic diff and audit. Canonical Studio now renders decision
tables with `@gorules/jdm-editor` through a constrained adapter; GoRules supplies the spreadsheet
editing experience only, while canonical storage, evidence, validation and governance remain
platform-owned. A separate GildedRose experiment remains
rejected because v1 cannot faithfully model `quality` as both current input and new output;
arbitrary-repository compatibility is therefore not claimed.
Synthetic fixture imports do not count as that acceptance.

### Import a small cloud PostgreSQL table

Open `/studio`, choose **PostgreSQL import**, keep the connection reference
`BRP_PSQL_URL`, and discover schema `brp_demo_source`. The retained smoke fixture
`eligibility_rules` contains three rows. Discovery and import are read-only, bounded, quote
identifiers through the PostgreSQL driver, and never accept model-authored SQL. The current
connection reference is logically separate from platform persistence but still uses the same
cloud database credentials; a distinct least-privilege source user remains required for F-401.

## Workflows

1. **Configure:** create/select a workspace and site, then create an immutable,
   secret-reference-only site profile with pinned source and target settings.
2. **Import:** preflight an inline supported asset or pinned Java repository and
   submit a durable extraction job. Inspect candidates, diagnostics and provenance.
3. **Govern:** promote selected candidates idempotently, edit the decision table or
   advanced IR, create immutable revisions and run maker-checker lifecycle actions.
4. **Test:** capture/select an approved lookup snapshot, maintain a golden suite and
   run it asynchronously through the worker.
5. **Release:** generate Java/tests, run authoritative target commands, push a branch,
   and create a reviewable GitHub pull request. Merge/deployment remains outside the platform.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/orchestration/catalog` | Exposed adapters/generators, boundaries, and detected tools |
| `POST` | `/orchestration/preflight` | Deterministic multi-site capability matrix |
| `POST` | `/orchestration/extract` | Restricted inline extraction; requires the `maker` role |
| `POST` | `/orchestration/generate` | DMN/C# candidate preview; requires the `maker` role |

The authoritative versioned contract is committed in
[`openapi-v1.json`](openapi-v1.json). Core durable routes start at `/api/v1/sites`,
`/api/v1/import-runs`, `/api/v1/jobs`, `/api/v1/canonical-packages`,
`/api/v1/db-sources`, `/api/v1/decisions`,
`/api/v1/golden-suites`, `/api/v1/releases` and `/api/v1/artifacts`.

Local write-like calls send `X-BRP-Actor` only because
`BRP_LOCAL_DEVELOPMENT_HEADERS=true` was explicitly enabled. Production/default mode rejects
that header and requires OIDC JWT roles.

## Safety and evidence boundary

- The workbench accepts at most 1 MB of text and only a safe basename, never an arbitrary server
  path.
- Inputs are held in memory or an isolated temporary directory. SQL, scripts, framework
  expressions, and engine consequences are parsed but never executed.
- Responses are labeled `LOCAL_PREVIEW_NON_AUTHORITATIVE`, `persistent=false`, and generated
  previews are `authoritative=false`.
- Compatibility-preview candidates are not persisted. Durable `/api/v1` imports
  persist candidates, but promotion, approval and release remain separate audited
  operations with golden evidence gates.
- C# remains `COMPILE_NOT_RUN` on this host until a pinned .NET SDK is installed.

## Verification tiers

Do not load the cloud `.env` for destructive test suites. Use these tiers:

1. Pure/unit checks that do not require a database:

```powershell
cd platform
$env:BRP_DATABASE_URL = "postgresql+psycopg://unit:unit@127.0.0.1:1/brp_unit_test"
uv run pytest tests/test_smoke.py tests/test_git_source.py tests/test_runtime_settings.py -q
uv run ruff check src tests
uv run mypy src

cd ..\ui
pnpm run test -- --run
pnpm run build
```

2. Repository/API suites that write data require a dedicated database whose name ends in
   `_test`. The safety fuse must remain enabled. A shared `brp` application database is not an
   acceptable test target.

3. Cloud integration smoke is read-only: `scripts/check-pg.py`, Alembic `current`,
   `/health/live`, `/health/ready`, worker freshness, and UI HTTP response. It does not run
   repository tests or seed/reset data.

4. External GitHub acceptance is explicitly gated and uses the user's writable dummy repo.
   It must verify the remote branch and pull request independently; a local bare repository is
   only synthetic evidence. `gh auth status` must succeed for the writable account before this
   tier runs; tokens are never placed in command arguments or logs.

Historical RDS/production-hardening notes remain under `docs/` for audit context only and do
not override this active small-flow procedure.
