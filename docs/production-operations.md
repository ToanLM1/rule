# Production operations

## Release boundary

This is an internal, self-hosted release candidate. Run it only on a trusted
network until OIDC Authorization Code + PKCE replaces development identities.
The API exposes the release boundary in `/api/v1/context` as
`productionBlocked: true`.

As of 2026-07-16 the release has not passed its final packaging/CI gate and has not
been cut over to RDS. Treat this document as the target runbook, not evidence that
deployment is complete. Current evidence and blockers are in
[`production-hardening-progress.md`](production-hardening-progress.md).
Deployment sizing and the current-vs-proposed AWS estimate are maintained in
[`cloud-sizing.md`](cloud-sizing.md).

## Services

- `ui`: non-root nginx serving the SPA and proxying `/api`, health and metrics.
- `api`: non-root FastAPI process; all long-running work is submitted as a job.
- `worker`: separate process leasing PostgreSQL jobs with `FOR UPDATE SKIP LOCKED`.
- `postgres`: isolated deployment database. External RDS can replace this service.
- `joern`: optional profile for source analysis.

Start the isolated stack from the repository root:

```powershell
docker compose -f docker/compose.production.yml up -d --build --wait
```

This command is a release acceptance target while T-1004 remains open. The default
Compose file starts its own isolated PostgreSQL. Cloud deployment must use an
explicit external-RDS configuration and must not accidentally start a second
authoritative database. Joern is optional and only starts with `--profile joern`.

For a local API/UI against an external database, set an ignored environment file,
run migrations with `uv run python -m brp.migrate`, start the API with Uvicorn and
start the worker with `uv run python -m brp.worker`. Never commit connection URLs.

## Health and observability

- `/health/live` checks process liveness only.
- `/health/ready` checks the database, Alembic head, artifact storage and stale leases.
- `/metrics` exposes Prometheus counters and request latency.
- Requests and jobs carry correlation IDs. Problem responses use RFC 7807 with a
  stable code, correlation ID, retryability flag and field-violation collection.

Alert on readiness failures, failed jobs, expired leases and repeated retry
exhaustion. A database outage must make readiness fail while liveness remains up.

## Test database safety

The global pytest safety fuse refuses a database whose name does not end in
`_test`, unless `BRP_ALLOW_DESTRUCTIVE_TEST_DATABASE=true` is explicitly supplied.
Never set that override for RDS `brp`. Automated suites run only against isolated
PostgreSQL; shared RDS receives smoke and manual acceptance checks only.

## RDS cutover

1. Stop API and worker writers.
2. Create a timestamped custom-format `pg_dump` of `brp` and a SHA-256 checksum.
3. Capture read-only fingerprints for `rag_utils`; do not connect to it with a
   mutating command.
4. Verify the release against isolated PostgreSQL and retain the last known-good
   commit and backup path.
5. Drop and recreate only `brp`, migrate to head, and run the curated seed once.
6. Start API, worker and UI; verify import, review, revision, golden run, Mode-A,
   Mode-B evidence, artifact download, health and responsive UI.
7. If acceptance fails, stop writers, recreate only `brp` from the backup and
   restart the last known-good release.

The seed command refuses to run when governed decisions already exist. Never run
the full pytest suite against the shared RDS.

## Secrets

PostgreSQL stores secret references only. Providers resolve uppercase environment
references or absolute `file:` references at execution time. Do not print secret
values, place them in site profiles, pass them as command-line arguments or include
them in artifacts and delivery evidence.
