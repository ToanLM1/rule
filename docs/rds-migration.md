# Singapore RDS Migration Record

> **Historical baseline, not the hardening cutover.** This record documents the
> successful pre-hardening copy at Alembic `0004_mode_a_publications`. The current
> production-hardening code head is `0007_site_scoped_hashes`. As of 2026-07-16,
> the isolated hardening database has reached `0007`, but the shared RDS `brp`
> cutover has not been performed. Do not infer that the current RDS schema matches
> the working tree. The pending procedure and rollback gates are tracked in
> `production-hardening-progress.md`.

The Rule Platform application database is `brp` on the same Singapore RDS PostgreSQL instance
used by Hybrid-RAG. The existing `rag_utils` database was not modified. Local API processes use
the ignored root `.env` and TLS (`sslmode=require`); credentials are never committed.

## Migration evidence

- Source: Docker PostgreSQL 16.4 database `brp`.
- Target: RDS PostgreSQL 17.9 database `brp`, owned by `postgres`.
- Source backup: custom-format `pg_dump`, 129,169 bytes.
- Backup SHA-256: `9f71c12b8d4a755e5fe438e5b90f51db579f14c6e5c7a6d115884104ca8a45d2`.
- Alembic revision: `0004_mode_a_publications` on source and target.
- Verified equal: 17 tables, canonical content hashes for every table, 25 indexes,
  37 constraints, 9 non-internal triggers, extensions, and sequences.
- Key target counts: 260 decisions, 305 decision revisions, 61 golden cases, and
  28 Mode-A publications.
- Two consecutive `upgrade head` runs completed without schema changes.
- A create/insert/read transaction was rolled back and left no probe object behind.

The ignored evidence files are under `output/rds-migration/`. They include the source dump and a
source/target verification manifest. Treat the dump as local operational data and do not commit
or distribute it.

## Runtime and test boundary

Run the API with `uv run --env-file .env ...` as shown in
[`orchestration.md`](orchestration.md). Automated platform tests may commit synthetic records, so
they must use the isolated Docker PostgreSQL URL and must not load the cloud `.env`.

The RDS instance retains its existing office-hours schedule. Outside that window, the local API
cannot start until the shared instance is available again.
