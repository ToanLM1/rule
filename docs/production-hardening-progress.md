# Production-hardening progress

Last updated: 2026-07-16. Branch: `feat/production-hardening`.

## Release status

The hardening release is **implemented but not cut over**. The multi-site control
plane and durable governed workflow have targeted acceptance evidence on isolated
PostgreSQL. The release remains an internal-network release candidate because OIDC
Authorization Code + PKCE is deferred. Container packaging, final CI-equivalent
regression and the protected RDS cutover are still open.

| Area | State | Evidence or remaining gate |
|---|---|---|
| Workspace/site data model and migrations | Implemented, targeted verification passed | Isolated DB at `0007_site_scoped_hashes`; site-scoped uniqueness and profile revisions covered |
| Versioned API and errors | Implemented, targeted verification passed | `/api/v1`, pagination/filtering, optimistic concurrency, RFC 7807, correlation IDs |
| Durable job worker | Implemented, targeted verification passed | Lease/heartbeat/retry/cancel/recovery tests; separate worker processed acceptance jobs |
| Imports and candidate governance | Implemented, acceptance passed | Pinned Java commit produced three candidates; repeat promotion returned the same governed revision |
| Golden and lookup evidence | Implemented, acceptance passed | Approved lookup snapshot and suite used by Mode-A publication |
| Mode A | Implemented, acceptance passed | Two publications followed by an append-only rollback publication |
| Mode B | Implemented, acceptance passed | Local bare Git branch/commit, generated gates, manifest, artifact and verified download hash |
| Enterprise UI | Implemented, final regression pending | Eight product areas, EN/KR, responsive shell, grid/editor and async operations; rerun latest UI gates |
| Runtime/observability | Implemented, packaging pending | Live/ready/metrics, structured redacted logs, settings validation; rebuild/rehearse containers |
| CI/security gates | Defined, final run pending | Full suite, OpenAPI drift, scans, SBOM and 10k performance evidence still required |
| Shared RDS | **Not cut over** | RDS `brp` remains historical `0004`; backup/checksum and isolated gates are prerequisites |

## Isolated acceptance evidence

- PostgreSQL container: `brp-hardening-test`, PostgreSQL 17.9, database
  `brp_test`, host port `55433`.
- Durable Java import run `2d664cd3-5271-43c7-9f7b-435f5e8f420c`
  resolved immutable commit `888621061246…` and produced
  `enrollment_eligibility`, `premium_adjustments` and `required_documents`.
- Promotion was idempotent: the initial and repeated request both resolved revision
  2 without duplicating the decision or revision.
- Mode-B job `36288e9c-4cb0-47dc-a804-94d429e93d4e` succeeded against a real local
  bare repository. It pushed branch `rules/gen-enrollment_eligibility-r1`, persisted
  commit `0195ba0ffd4310f7f744ee7a79db860070aabfc4`, generated an immutable manifest
  and served artifact `35f1352a-2356-40c0-82b6-23c9b5c41f9f`; the downloaded bytes
  matched the stored SHA-256.
- Mode-A acceptance published twice on the `acceptance` channel and created a third
  append-only publication for rollback after approved golden and lookup evidence.
- The earlier frontend gate passed 4 Vitest tests and 2 Playwright flows, including
  mobile Korean switching and zero critical axe violations. This evidence predates
  the latest lookup/release/lifecycle edits and is not the final UI gate.
- The last full backend run reached 206 passing tests and exposed two failures.
  Both causes were fixed and their focused tests passed; a fresh full run is still
  required before release acceptance.

Identifiers above refer only to disposable isolated acceptance data. They are not
customer records and must not be presented as RDS production evidence.

## Open blockers, in execution order

1. Add a root `.dockerignore`; prevent local `node_modules`, virtual environments,
   outputs and build caches from entering image contexts.
2. Package Git, Java 17 and the Java toolchain in the worker runtime and separate
   platform-toolchain paths from customer repository paths.
3. Build API and UI images and start the complete Compose stack from an empty
   isolated database; verify graceful stop/restart and worker crash recovery.
4. Regenerate `docs/openapi-v1.json` and run Ruff, strict mypy, full pytest, UI
   build/Vitest/Playwright/axe, Gradle gates, image/secret/dependency scans and SBOM.
5. Run the 10,000-decision pagination/performance rehearsal and retain results.
6. Only after 1–5 are green: stop RDS writers, back up `brp` with checksum, capture
   a read-only `rag_utils` fingerprint, recreate only `brp`, migrate to `0007`, seed
   curated data and smoke the entire workflow. Roll back from the checked backup on
   any acceptance failure.

## Non-goals and claims boundary

- OIDC login is not implemented; development identity controls are not production
  authentication. Do not expose the release directly to the Internet.
- C# generation remains non-authoritative until a pinned .NET SDK compiles and runs
  a target golden suite.
- Synthetic Java/PL/pgSQL/HTML/DMN/DRL/ODM evidence does not establish arbitrary
  customer-source compatibility or mining accuracy.
- `rag_utils`, Hybrid-RAG ingestion and Neptune are outside this application's
  runtime and migration scope.

