# Rule Platform

Rule Platform is a self-hosted, multi-site governance console for extracting,
reviewing, testing, approving and delivering business rules. Its governed flow is:

`source import → durable extraction job → candidate review → immutable revision → golden tests → approval → Mode-A publish or Mode-B Git delivery`

The release consists of a Vue enterprise console, a FastAPI service, a separate
PostgreSQL-backed worker and PostgreSQL. Nginx serves the SPA and proxies `/api`.
English and Korean UI locales are included; user-authored source and rule content
is never translated.

This milestone is an internal-network release candidate. Development identity
headers are deliberately visible in the UI. Internet exposure and an unconditional
production claim remain blocked until OIDC Authorization Code + PKCE is implemented.

- [Product requirements](prd.md)
- [Architecture](architecture.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Production operations](docs/production-operations.md)
- [Production-hardening progress](docs/production-hardening-progress.md)
- [AWS capacity and cost estimate](docs/cloud-sizing.md)
- [Local orchestration and run commands](docs/orchestration.md)
- [Local environment](docs/environment.md)
- [RDS migration record](docs/rds-migration.md)

Current status (2026-07-16): the control plane, durable worker workflows and
enterprise console are implemented and have targeted isolated acceptance evidence.
The release is not yet cut over: container packaging, the final CI-equivalent gate
and migration of the shared RDS `brp` database from schema `0004` to hardening head
`0007` remain open. See the progress report before deploying.

The Telecom Knowledge Assistant is historical product context only. Rule Platform
does not depend on its chat, RAG, vector, document-ingestion or Neptune services.
