# Rule Platform local orchestration

The enterprise console exposes the durable governed flow:

`source import → extraction job → candidate review → immutable revision → golden evidence → approval → Mode-A publication or Mode-B Git delivery`.

The old inline Phase-3 workbench routes remain non-persistent compatibility tools
for one release. New application work uses `/api/v1` and the durable worker.

## Start locally

This workstation uses the shared Singapore RDS instance for the application database. The
ignored repository-root `.env` contains `BRP_DATABASE_URL` and `BRP_PSQL_URL` for database
`brp` with `sslmode=require`. Never commit that file or print either URL.

From the repository root in PowerShell:

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

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). Imports are under
`/imports`, governance under `/decisions`, `/review` and `/test-suites`, releases
under `/releases`, and worker/job state under `/operations`.

## Workflows

1. **Configure:** create/select a workspace and site, then create an immutable,
   secret-reference-only site profile with pinned source and target settings.
2. **Import:** preflight an inline supported asset or pinned Java repository and
   submit a durable extraction job. Inspect candidates, diagnostics and provenance.
3. **Govern:** promote selected candidates idempotently, edit the decision table or
   advanced IR, create immutable revisions and run maker-checker lifecycle actions.
4. **Test:** capture/select an approved lookup snapshot, maintain a golden suite and
   run it asynchronously through the worker.
5. **Release:** publish/rollback Mode A or generate/deliver Mode B. Inspect hashes,
   immutable artifacts and provider PR/MR evidence.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/orchestration/catalog` | Exposed adapters/generators, boundaries, and detected tools |
| `POST` | `/orchestration/preflight` | Deterministic multi-site capability matrix |
| `POST` | `/orchestration/extract` | Restricted inline extraction; requires the `maker` role |
| `POST` | `/orchestration/generate` | DMN/C# candidate preview; requires the `maker` role |

The authoritative versioned contract is committed in
[`openapi-v1.json`](openapi-v1.json). Core durable routes start at `/api/v1/sites`,
`/api/v1/import-runs`, `/api/v1/jobs`, `/api/v1/decisions`,
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

## Verification

The full platform test suite writes and commits test records. Run it only against the isolated
Docker database, never with the cloud `.env` loaded:

```powershell
docker compose -p brp -f docker/docker-compose.yml up -d postgres
$env:BRP_DATABASE_URL = "postgresql+psycopg://brp:brp@localhost:55432/brp"
$env:BRP_PSQL_URL = "postgresql://brp:brp@localhost:55432/brp"

cd platform
uv run pytest tests/api/test_orchestration_api.py -q

cd ..\ui
pnpm run test -- --run
pnpm run build
pnpm run test:e2e
```

The historical RDS copy and its verification evidence are documented in
[`rds-migration.md`](rds-migration.md). It remains at schema `0004`; do not run the
hardening code against it as if the `0007` cutover were complete. See
[`production-hardening-progress.md`](production-hardening-progress.md).
