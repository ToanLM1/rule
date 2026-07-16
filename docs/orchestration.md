# Phase-3 Local Orchestration Workbench

The workbench exposes the restricted Phase-3 adapters, deterministic target previews, and
multi-site capability preflight through the local API and Vue UI. It is an inspection surface,
not a shortcut around repository governance.

## Start locally

This workstation uses the shared Singapore RDS instance for the application database. The
ignored repository-root `.env` contains `BRP_DATABASE_URL` and `BRP_PSQL_URL` for database
`brp` with `sslmode=require`. Never commit that file or print either URL.

From the repository root in PowerShell:

```powershell
uv run --env-file .env --project platform python -m alembic -c platform/alembic.ini upgrade head
uv run --env-file .env --project platform python -m uvicorn brp.api.app:app --host 127.0.0.1 --port 8100
```

In a second terminal:

```powershell
pnpm --dir ui dev --host 127.0.0.1
```

Open [http://127.0.0.1:5173/orchestration](http://127.0.0.1:5173/orchestration).

## Workflows

1. **Extract:** select the stored-object, HTML validation, DRL/ODM, or DMN adapter. Use the
   checked-in sample, paste source, or load a local file. The UI shows candidate Rule IR,
   source hash, diagnostics, and every unsupported review item.
2. **Generate:** select a candidate and render deterministic DMN or C# source. This is source
   preview only; the response includes an artifact hash and, for C#, explicit compile evidence.
3. **Preflight:** edit a secret-free site profile and local tool inventory. The capability matrix
   reports each source, target, and runtime as `AVAILABLE`, `UNAVAILABLE`, `INCOMPATIBLE`, or
   `UNKNOWN` before any work starts.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/orchestration/catalog` | Exposed adapters/generators, boundaries, and detected tools |
| `POST` | `/orchestration/preflight` | Deterministic multi-site capability matrix |
| `POST` | `/orchestration/extract` | Restricted inline extraction; requires the `maker` role |
| `POST` | `/orchestration/generate` | DMN/C# candidate preview; requires the `maker` role |

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
- Candidates are not inserted into the governed repository, approved, published, committed, or
  delivered. Production release still uses lifecycle, golden evidence, and Mode-A/Mode-B gates.
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

The RDS copy and its verification evidence are documented in
[`rds-migration.md`](rds-migration.md).
