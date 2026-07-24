# Implementation Plan — Business Rules Platform

> **Active roadmap (2026-07-23): small-first, full-flow-first.** The next product
> outcome is one unrelated small public Java repository completing the governed
> loop through a pushed branch and GitHub pull request. A selected small cloud-
> PostgreSQL table follows. Docker, Joern, production hardening, multi-site scale,
> Mode A, additional languages/DBMSs, and enterprise rollout are not prerequisites.
> M0–M11 are retained in the historical appendix and must not be used to select
> new work.

---

## 0. Active Execution Rules

1. Read `AGENTS.md`, `prd.md`, and `architecture.md` before selecting work.
2. Pick the first unchecked `F-*` task whose dependencies are complete. Do not resume a historical M0–M11 task unless a human explicitly reactivates it.
3. Preserve existing capability, but do not spend work on container hardening, RDS cutover, OIDC, multi-site scale, 10k performance, second language/DBMS, Mode A, DMN/DRL/C#, stored procedures, UI mining, or Joern without an active-task dependency.
4. Synthetic fixtures remain regression tests. They cannot satisfy arbitrary-repository, business-usability, real-PR, real-site, or production-readiness acceptance.
5. Use the existing cloud PostgreSQL for local platform state. No Docker PostgreSQL is required. Any destructive automated DB test must target an isolated `*_test` database or explicitly isolated disposable schema and must fail closed otherwise.
6. Source extraction produces evidence-backed candidates only. Package compilation, Java generation, and release evidence are deterministic; compiled generated Java plus configured target tests are authoritative.
7. A repository full-flow is incomplete until the branch exists on the configured remote and a reviewable GitHub pull request has been created. Never auto-merge or claim production deployment.

## 1. Active Reference Outcome

Use one public, writable dummy Java repository containing a small but non-template decision flow and business tests. The successful demonstration is:

```text
public GitHub repo → immutable commit → EvidenceBundle/candidate
→ business vocabulary + decision-table edit → submit/approve
→ deterministic Rule IR → Java + JUnit → target build/tests
→ changed expected outcome → pushed branch → GitHub pull request
```

The source repository must not be coupled to the existing `EnrollmentValidator` fixture patterns. At least one extracted field must require evidence gathered from a second source or test file so the flow proves evidence navigation rather than one-file regex matching.

After this passes, use one small selected table or view on cloud PostgreSQL as a separate source. Map it through the same Canonical Decision Package, governance, Java generation, test, and pull-request path.

## 2. Active Roadmap

### F0 — Truthful cloud-local baseline

*Exit: API, worker, and UI run natively against cloud PostgreSQL with current migrations, a fresh worker heartbeat, and a repeatable smoke guide; no Docker or Joern process is required.*

- [x] **F-001 — Reconcile runtime configuration and status.** COMPLETE 2026-07-23
  - Implemented: native launcher refreshes the process-local Windows tool path, verifies uv/pnpm/Git/Java 17 before database access, normalizes `JAVA_HOME` without changing machine configuration, runs migrations, and starts API/worker/UI; SQLAlchemy connections fail fast and the worker retries transient PostgreSQL failures.
  - Verified 2026-07-23: Microsoft OpenJDK `17.0.19`, cloud PostgreSQL `17.9`, Alembic `0009_candidate_package_promotion`, `/health/ready` database/artifact/worker checks, fresh worker leases, and `/studio` HTTP/browser smoke. The native stop script traverses only its recorded process trees.
  - Verify the actual cloud migration revision, API health/readiness, worker lease/heartbeat, UI/API routing, Git, and Java 17 availability. Keep secrets out of logs/docs.
  - Update startup documentation to use the existing native cloud-local scripts and list exact prerequisites plus download links only for missing software.
  - Acceptance: a fresh native start followed by health, readiness, worker-freshness, and UI smoke checks; stop scripts leave no project-owned processes running.

- [ ] **F-002 — Establish safe test tiers.**
  - Separate pure/unit tests, isolated `*_test` DB tests, cloud read-only integration smoke, and external GitHub tests. Never weaken the destructive-test fuse to make shared cloud tests pass.
  - Acceptance: documented commands accurately report what was run/skipped; the shared application DB is rejected by destructive suites.
  - Depends: F-001.

### F1 — Canonical Studio for non-technical authors

*Exit: a user can correct and edit a governed decision using vocabulary, table cells, lookups, effective dates, and scenarios without editing JSON.*

- [x] **F-101 — Canonical Decision Package schema and compiler.** COMPLETE 2026-07-23
  - Implemented: strict v1 package models for vocabulary, decisions, lookups, composition, scenarios, evidence, and Java target binding; deterministic fail-closed Package→Rule-IR compiler with field/cell diagnostics; governed immutable revisions, effective-date lifecycle, audit and semantic diff; `/api/v1/canonical-packages/compile`; Korean/evidence/determinism/unit/API tests.
  - Add a versioned package model for vocabulary, decisions, lookups, restricted composition, business scenarios, evidence links, and Java target binding.
  - Implement pure deterministic Package→Rule-IR compilation. Return field/cell-addressed diagnostics and no partial IR on error. Preserve immutable revision/effective-date lifecycle and evidence linkage.
  - Acceptance: round-trip/storage tests, valid compiler fixtures, invalid type/operator/reference/composition cases, deterministic bytes, Korean UTF-8, and evidence preservation.

- [x] **F-102 — Business authoring API.** COMPLETE 2026-07-23
  - Implemented: create/read/revise, compile preview, scenario revision, submit/approve/reject, optimistic concurrency, maker-checker, effective-overlap rejection, audit and semantic diff under `/api/v1/canonical-packages`.
  - Expose package draft create/read/revise, validation/compile preview, submit/approve/reject, readable semantic diff, and business-scenario management through `/api/v1`.
  - Keep compiled/raw IR read-only through an explicit advanced endpoint/view. Existing IR APIs remain compatibility paths, not the new UI default.
  - Acceptance: maker-checker, optimistic concurrency, immutable approved revision, effective-date overlap, actionable diagnostics, audit, and compatibility tests.
  - Depends: F-101.

- [ ] **F-103 — Canonical Studio UI.** IN PROGRESS 2026-07-23
  - Implemented: `/studio` persists and edits package revisions directly; decision-table authoring uses the mature `@gorules/jdm-editor` spreadsheet experience through a constrained Canonical Package↔JDM adapter. GoRules is a UI component only: vocabulary, evidence, lifecycle, scenarios, canonical storage, compilation and approval remain platform-owned. The adapter permits supported row/value edits, rejects arbitrary Zen expressions and schema changes, and preserves evidence/confidence outside JDM. The Studio also maintains business scenarios, shows evidence/confidence, and supports maker/checker submit/approve. The guided PostgreSQL tab discovers and maps bounded tables without raw SQL. A live browser smoke rendered the GoRules table and discovered `brp_demo_source.eligibility_rules`.
  - Remaining: dedicated component/Playwright coverage for validation failure, evidence drill-down, revision diff, responsive/accessibility behavior, and guided nested/lookup editors.
  - Make vocabulary, decision-table rows/cells, outcomes, lookup bindings, dates, scenarios, validation, evidence, and readable diff the primary Decisions experience.
  - Move raw `when`/`then` JSON and Monaco IR behind an “Advanced” disclosure. A standard edit/submit/approve flow must not require JSON knowledge.
  - Acceptance: component and Playwright flows cover create/edit row, validation failure, scenario edit/run, evidence inspection, submit, separate-actor approval, revision diff, and responsive/accessibility checks.
  - Depends: F-102.

### F2 — Evidence-driven small Java repository bootstrap

*Exit: an unrelated small public Java repository produces useful candidates and complete EvidenceBundles without Joern or hard-coded fixture patterns.*

- [ ] **F-201 — EvidenceBundle and tool contracts.** IN PROGRESS 2026-07-23
  - Implemented: strict EvidenceBundle with field-level links, assumptions, unresolved calls, tests, contiguous transcript, and escalation; bounded Git inventory/history, ripgrep search, UTF-8 source reads, hashes, root confinement, output/file/range limits, and tests for traversal/oversize/binary inputs.
  - Verified: subprocess timeout/failure paths expose only the tool name and exit class; tests assert search arguments and stderr are never leaked.
  - Remaining: durable first-class storage rather than snapshot embedding.
  - Define persisted schemas for commit/subpath, hypothesis, exact spans/hashes, inferred fields, assumptions, unresolved calls, alternative interpretations, test evidence/results, per-field confidence, tool transcript, and escalation recommendation.
  - Define bounded read-only tools for repository inventory/manifests, `rg`, Git history/diff, source/test reads, and structural query. Enforce repository-root containment, output/size limits, timeouts, and secret-safe logs.
  - Acceptance: schema/canonicalization tests plus traversal, oversized-output, timeout, binary, malformed UTF-8, and redaction cases.

- [x] **F-202 — Lightweight repository agent.** COMPLETE 2026-07-23
  - Implemented: commit-pinned inventory/search/bounded source and related-test collection; schema-only prompt; provider-swappable structured inference; evidence-link verification; conservative normalization that removes invalid optional claims while recording unresolved evidence; package compilation; public-import worker integration; fail-closed environment provider factory. Public preflight no longer invokes Joern or synthetic construct matching.
  - Verified live: Groq `openai/gpt-oss-120b` imported `novoda/dojos` at `2e7391623b42617af1bbdad227e3e4701e89af2c`, subpath `harry-potter/09102010-blundell-xavi`, entry point `silent.DiscountCalculator#calculate`, in one durable attempt. It produced one compiling discount candidate, exact Java evidence, related test evidence and one scenario. An earlier Groq 70B run was reviewed against source and promoted to a Canonical Decision Package.
  - Demonstrated boundary: GildedRose state transition uses the same `quality` concept as current input and new output, which v1's single-role vocabulary cannot represent without inventing a rename. It remains a concrete model-extension/escalation case, not a reason to add Joern.
  - Orchestrate commit pinning and evidence tools to locate decision logic, related types/constants/lookups, and relevant tests; produce a candidate Decision Package plus EvidenceBundle and review items.
  - Use structured provider output through the existing provider abstraction. Do not accept candidates with missing support for asserted source-derived fields; unsupported logic remains unresolved evidence.
  - Acceptance: recorded deterministic provider tests and a live-provider gated test on the dummy repo; prove the path works with Joern unavailable and does not match fixture-specific names/templates.
  - Depends: F-201.

- [ ] **F-203 — Targeted semantic escalation.**
  - Add Tree-sitter structural queries as the first escalation. Add only the smallest targeted Java semantic tool needed by a demonstrated dummy-repo unresolved case (JavaParser/SymbolSolver, OpenRewrite, or JDT LS).
  - Record the failed question, selected tier, returned evidence, and remaining uncertainty. Joern/SootUp is explicitly outside this task.
  - Acceptance: one case resolved by text/bounded reads and one case requiring structural or targeted semantic evidence; both produce auditable transcripts.
  - Depends: F-202.

- [ ] **F-204 — Durable import and review integration.** IN PROGRESS 2026-07-23
  - Implemented: public repository jobs persist the candidate package and complete EvidenceBundle inside the immutable candidate source snapshot; unresolved calls create review items; Imports UI shows evidence counts, assumptions, and unresolved calls; synthetic fallback is disabled for public URLs. Candidate-to-package promotion is durable, idempotent, audited, linked to the promoted revision, and now routes from Imports into Canonical Studio. Live public/LLM imports use one outer job attempt so a free-tier 429 or malformed output is not immediately multiplied by the durable worker retry loop. Cloud run `6900df8c-2dea-4b81-8efe-9a244077f4e9` succeeded, and candidate `8a559c9f-7f7d-4e95-9b21-f131aa0c3cfa` promoted to package revision 1.
  - Remaining: full retry/cancel acceptance against cloud DB and dedicated evidence views.
  - Replace the fixed synthetic miner as the default public-repository import path. Persist candidate package/evidence, show progress, allow retry/cancel, promote idempotently into a governed draft, and preserve unresolved-fragment dispositions.
  - Acceptance: URL/revision/subpath validation, immutable pin, idempotent retry/promotion, cancellation/recovery, evidence visibility in UI, and explicit unsupported/review outcomes.
  - Depends: F-103, F-202.

### F3 — Repository full-flow delivery

*Exit: one business edit in the dummy repository path changes the expected behavior, passes generated and target tests, and lands as a pushed branch plus GitHub pull request.*

- [ ] **F-301 — Dummy target repository and stable seam.**
  - Configure the user-owned public dummy Java repository with a stable façade/integration seam, baseline business tests, generated/test paths, package name, base branch, and pinned Gradle or Maven commands.
  - Acceptance: baseline clone/build/test passes from the pinned commit; tests exercise the façade used by generated rules.

- [ ] **F-302 — Package release compilation and target gates.**
  - Generate Rule IR, Java, JUnit, and manifest only from an approved package revision, approved scenarios/golden suite, lookup snapshots, target config, and generator version.
  - Run generated tests and configured target tests in the delivery worktree. A failing or unavailable authoritative command blocks branch push/PR.
  - Acceptance: byte-identical rerun; planted business failure blocks delivery; successful edit changes the asserted outcome through the target façade.
  - Depends: F-101, F-301.

- [ ] **F-303 — Remote branch and GitHub pull request.** IN PROGRESS 2026-07-23
  - Implemented: the approved-release delivery job now pushes through a command-scoped GitHub credential helper, then invokes a secret-safe GitHub CLI publisher which verifies origin identity and the independently fetched remote branch head, creates or idempotently reuses one open PR, and verifies PR base/head/OID/state before returning evidence. Unit and local delivery tests cover create, reuse, mismatched heads, deterministic commits, compile/test and delivered execution.
  - Remaining: run it against a distinct user-owned writable Java target repository after the target gate passes.
  - Use a secret reference for writable credentials, branch from the configured base commit, write only allowlisted generated/test paths, commit the manifest/diff, push the branch, and create a PR containing evidence and test summaries.
  - Make retries idempotent by release id/branch; never log tokens, force-push unrelated history, auto-merge, or trigger/claim production deployment.
  - Acceptance: remote branch and PR are independently fetched/verified; PR commit hashes and generated hashes match release evidence; failure before push leaves no false success status.
  - Depends: F-302.

- [ ] **F-304 — Full-flow acceptance rehearsal.**
  - Execute PRD §7 from public import through non-technical edit, separate approval, deterministic generation, behavior change, target tests, remote branch, and GitHub PR.
  - Record exact evidence and limitations. Synthetic/local-only results are reported separately.
  - Depends: F-204, F-303.

### F4 — Small cloud PostgreSQL table full-flow

*Exit: one selected small table/view is imported read-only and completes the same governed Java/PR delivery flow.*

- [ ] **F-401 — Guided table discovery and mapping.** IN PROGRESS 2026-07-23
  - Implemented: read-only bounded `pg_catalog` discovery, validated/quoted identifiers, deterministic row-to-package mapping with stable DB-row evidence and snapshot hash, `/api/v1/db-sources/*`, and guided `/studio` mapping. Cloud smoke imported three rows from `brp_demo_source.eligibility_rules`, then completed package submit/approve without modifying the source table.
  - Remaining: demonstrate a distinct least-privilege source credential rather than the current separately named connection reference to the same cloud database.
  - Configure a source connection reference distinct from platform persistence, browse allowlisted schemas/tables/views, select bounded rows/columns, and map condition/outcome/vocabulary fields through a reviewed UI.
  - Persist source object, stable row identity, selected columns, mapping, snapshot/hash, and read-only evidence. No arbitrary model-authored SQL.
  - Acceptance: least-privilege/read-only enforcement, injection/identifier containment, bounds, redaction, Korean text, deterministic mapping, and cloud integration smoke.
  - Depends: F-002, F-103.

- [ ] **F-402 — DB-derived governed delivery.**
  - Promote mapped rows to a draft Decision Package, correct/edit/approve it, then reuse F-302/F-303 for Java generation, authoritative tests, remote branch, and PR.
  - Acceptance: a selected DB-row change is visible in evidence/diff and produces the expected tested target behavior without modifying the source DB.
  - Depends: F-303, F-401.

### F5 — Evidence-triggered expansion gate

- [ ] **F-501 — Evaluate real blockers only after F-304 and F-402.**
  - For each proposed heavy/scale capability, record the real failed input/outcome, evidence from current lightweight tooling, smallest sufficient addition, operational cost, rollback boundary, and acceptance test.
  - Joern/SootUp, Mode A, DMN/DRL/C#, stored procedures, UI mining, second language/DBMS, multi-site controls, containers, OIDC, HA, and performance engineering remain deferred until this gate approves a concrete case.
  - Depends: F-304, F-402.

## 3. Active Definition Of Done

An `F-*` task is complete only when its listed acceptance evidence passes, changed projects remain lint/type/build clean, documentation matches actual behavior, and no claim exceeds the evidence tier. F-304 and F-402 require external remote/DB evidence respectively; mocks cannot replace them.

---

# Appendix A — Historical Implementation Record (M0–M11)

The material below is retained for audit and regression context. Its task ordering, environment assumptions, scale work, and unchecked items are **not active instructions**. In particular, historical M11 production-hardening work is paused until the active vertical slices pass and a human explicitly reprioritizes it.

## 0. Historical Execution Protocol

### 0.1 Required reading

1. `AGENTS.md` and `prd.md` in this directory.
2. `architecture.md`, including ADR-1..8 and §14.
3. Knowledge-assistant PRD §4.10 and §5.2–§5.4 for separation/trust context only.
4. This plan, top to bottom.

### 0.2 Task selection and progress

1. Dependencies are authoritative. Pick the lowest-numbered unchecked task whose `Depends` are checked; an unrelated blocked environment task does not freeze the whole plan.
2. A task is done only when every listed acceptance command/test passes. If a required tool is missing, leave the task unchecked and log `BLOCKED`.
3. Work on a feature branch unless a human explicitly authorizes direct work on `main`. One task per commit where practical.
4. Mark completion as `- [x] ... ✅ YYYY-MM-DD <short-commit-hash>` and append one Progress Log line. E-tasks use their E-id in the same format.
5. Design changes require a `PROPOSAL` log entry and human review. Do not silently widen IR semantics, add a provider, or weaken a gate.
6. Existing Progress Log lines are append-only.

Progress format:

```text
YYYY-MM-DD HH:MM | E-###|T-### | done|BLOCKED|PROPOSAL | <commit-or-n/a> | note
```

### 0.3 Non-negotiable invariants

- Canonical decision content is the only rule-system source of truth. JDM, DMN, Java, reports, and test source are derived.
- Repository revision/status/effective/actor metadata lives in the ADR-6 envelope, never duplicated inside content JSON.
- Extracted rules are candidates with exact immutable source provenance and confidence. User-authored rules use `USER_ACTION` provenance. Nothing is auto-approved.
- Approver differs from creator and submitter. Every transition is audited.
- Generated artifacts depend only on the recorded ADR-8 `ReleaseInput` and are byte-identical for identical inputs.
- Mode-B authority is compiled generated Java plus target-application regression tests. Zen output is labeled advisory.
- Korean strings survive byte-exact from fixtures/evidence through JSONB, Zen, Java, logs, diffs, and reports.
- Site differences, PGM mappings, composition, lookup binding, and delivery paths live in validated config or adapters, never hard-coded core branches.
- Secrets are read from environment/secret stores. Never place passwords in command arguments, committed files, logs, or progress entries.

### 0.4 Development isolation

- Local/CI PostgreSQL containers and synthetic fixtures are the default automated-test path.
- Shared EC2/RDS resources are optional integration targets. Any service-impacting change, database/role creation, security-group edit, instance resize, or external push/PR requires explicit human authorization.
- Never modify the knowledge-assistant service, environment, ports, databases, ingestion, or deployment.
- Python commands run from `platform/` or `mcp-db-connector/`; Gradle from `java-toolchain/` or `fixtures/legacy-enrollment/`; pnpm from `ui/`.
- Every committed `.sh` under `scripts/` has a behavior-equivalent `.ps1`. Acceptance tests invoke the platform-neutral Python/Gradle entrypoint where practical.

---

## 1. Phase-1 Reference Outcome

The synthetic reference site maps one legacy API program (`EnrollmentValidator#evaluate`) to three independently evaluated decisions:

1. `enrollment_eligibility` (`FIRST`) — age/product/region rejection with an eligible default; region uses a typed lookup.
2. `premium_adjustments` (`COLLECT`) — matching rows emit loading percentages; the site façade applies `SUM`.
3. `required_documents` (`COLLECT`) — matching rows emit document codes; the façade applies `DISTINCT`.

This makes legacy increments and list mutations explicit without admitting side effects into IR. `STARTS_WITH` is part of IR v1 and covers the cancer-product branch. The final demo edits the under-age threshold, generates a delivery branch from a seam-enabled baseline, runs generated tests and the legacy application's tests on that branch, and executes the legacy entry point to prove the outcome changed.

Customer samples remain gated. The synthetic reference proves contracts and flow, not mining accuracy on a real site.

---

## 2. Configuration And Environment Contracts

### 2.1 Environment variables

```dotenv
# SQLAlchemy/psycopg application URL
BRP_DATABASE_URL=postgresql+psycopg://brp:brp@localhost:55432/brp
# libpq URL used only by psql scripts
BRP_PSQL_URL=postgresql://brp:brp@localhost:55432/brp
BRP_API_PORT=8100
BRP_LLM_PROVIDER=mock
BRP_LLM_BULK_MODEL=
BRP_LLM_FRONTIER_MODEL=
BRP_LLM_API_KEY=
BRP_LLM_BASE_URL=
BRP_LLM_LIVE=0
JOERN_MODE=native
JOERN_HOME=
PYTHONUTF8=1
JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8
```

`.env.example` contains safe local values only. Integration secrets use a separate uncommitted `.env.integration` or the runtime secret store.

### 2.2 Site profile

`config/sites/fixture.yaml` must validate against a Pydantic model and contain no secret values:

```yaml
site: fixture
delivery_mode: B
language: java
source:
  db:
    kind: postgres
    connection_env: BRP_DATABASE_URL
  repositories:
    - alias: legacy-enrollment
      path: ../fixtures/legacy-enrollment
      revision: HEAD
  program_contexts:
    - program_id: ENROLLMENT-API
      kind: API
      repository: legacy-enrollment
      class: legacy.EnrollmentValidator
      method: evaluate
adapters: [db-postgres, code-java, docs-manual]
mapping_spec: config/mappings/fixture-tables.yaml
target:
  repository: ../out/fixture-remote.git
  base_branch: main
  generated_source_path: src/generated/java
  generated_test_path: src/generatedTest/java
  java_package: brp.rules.generated
  build_command: ./gradlew test
  pr_provider: local-report
  composition:
    facade: legacy.rules.EnrollmentRuleModule
    decisions:
      premium_adjustments: { field: premiumLoadingPct, aggregate: SUM }
      required_documents: { field: requiredDoc, aggregate: DISTINCT }
```

### 2.3 API surface

Writes require `X-BRP-Actor`; reads do not. Phase-1 actor headers are development identity only, not production authentication.

| Method and path | Purpose |
|---|---|
| `POST /decisions` | Create decision and immutable DRAFT revision from content + effective interval |
| `GET /decisions` · `GET /decisions/{key}` | List/fetch envelope plus content |
| `POST /decisions/{key}/revisions` | Create a new DRAFT from full content |
| `POST /decisions/{key}/revisions/{r}/submit` | Submit revision |
| `POST /decisions/{key}/revisions/{r}/approve` · `/reject` · `/retire` | Govern lifecycle |
| `GET /decisions/{key}/audit` | Append-only lifecycle/content audit |
| `GET /decisions/{key}/diff?from=&to=` | Semantic content diff |
| `POST /preview/{key}?revision=` | Zen advisory preview |
| `POST /golden-suites/{key}` | Create suite revision |
| `POST /golden-suites/{key}/{r}/submit` · `/approve` | Govern suite revision |
| `POST /golden/{key}/run?executor=zen-advisory|generated-java` | Run a named executor; response identifies authority |

---

## 3. Milestones And Tasks

### 3.0 E — Safe local environment

- [x] **E-000 — Align governing status.** ✅ 2026-07-10 76b6331
  - Do: update stale planning-only statements in `AGENTS.md` to agree with the approved per-site Mode A/B decision and implementation status; preserve the isolated-track boundary.
  - Accept: `rg -n "unconfirmed|planning track" AGENTS.md` returns no stale instruction; `rg -n "separate|isolated" AGENTS.md` confirms the boundary remains.

- [x] **E-001 — Inventory local tools.** ✅ 2026-07-10 63017a4
  - Do: record actual Python, uv, Java, Node, pnpm, Git, Docker, and optional psql versions in `docs/environment.md`. Required: Python 3.12, Java 17, Node 20+, pnpm 9, Docker/Compose or a supplied test PostgreSQL URL. Do not install or mutate shared hosts.
  - Accept: `uv --version`; `uv run --python 3.12 python --version`; `java -version`; `node -v`; `pnpm -v`; `git --version`; and either `docker compose version` or a successful documented external test-DB probe.

- [x] **E-002 — Local PostgreSQL and safe URLs.** ✅ 2026-07-10 4b152ec
  - Do: add Compose PostgreSQL 16 on port 55432, create the `brp` database/user through container initialization, and implement `scripts/check-pg.py` using psycopg so shell scripts never need to translate SQLAlchemy URLs. `.sh`/`.ps1` wrappers call the Python script. RDS integration is opt-in and not part of local acceptance.
  - Accept: `docker compose -f docker/docker-compose.yml up -d --wait postgres`; then `uv run --project platform python scripts/check-pg.py` exits 0 using `BRP_DATABASE_URL`.
  - Depends: T-001.

- [x] **E-003 — Joern runtime.** ✅ 2026-07-10 7300c89
  - Do: pin an exact Joern 4.x release and configure native or Docker mode. Record the version and checksum. This task may remain blocked while non-Joern tasks proceed.
  - Accept: `uv run --project platform python scripts/joern_smoke.py --version-only` prints the pinned version.
  - Depends: T-001.

### M0 — Scaffold and executable legacy fixture

*Exit: every project builds locally; CI definitions are locally validated; the fixture behavior and expected decision decomposition are explicit.*

- [x] **T-001 — Monorepo scaffold.** ✅ 2026-07-10 fddbb1f
  - Do: create `platform/`, `java-toolchain/`, `mcp-db-connector/`, `ui/`, `fixtures/legacy-enrollment/`, `fixtures/manuals/`, `docker/`, `docs/`, `scripts/`, `config/sites/`, `config/mappings/`, and `.github/workflows/`. Initialize package `brp`; add dependencies from architecture §13 plus `mcp`, `pypdf`, `python-docx`, and `openpyxl`. Add `.env.example`, `.gitattributes`, `.gitignore`, and a real smoke test.
  - Accept (from `platform/`): `uv run ruff check .`; `uv run pytest tests/test_smoke.py`.
  - Depends: E-000, E-001.

- [x] **T-002 — Database bootstrap and fixture loaders.** ✅ 2026-07-10 8f0019e
  - Do: add idempotent schema/seed loaders invoked through Python/psycopg and thin `.sh`/`.ps1` wrappers. No password appears in process arguments or logs.
  - Accept: run `uv run --project platform python scripts/load_fixture_db.py --reset` twice; both exit 0 and row counts match.
  - Depends: T-001, E-002.

- [x] **T-003 — Java toolchain scaffold.** ✅ 2026-07-10 90c3a48
  - Do: Gradle 8.7 wrapper, Java 17 toolchain, modules `codegen-cli`, `brp-rules-runtime`, and `seam-recipes`; JUnit 5; JavaPoet; Jackson; OpenRewrite; Spotless/google-java-format.
  - Accept (from `java-toolchain/`): `./gradlew build` (or `gradlew.bat build` on Windows).
  - Depends: T-001.

- [x] **T-004 — Governance UI scaffold.** ✅ 2026-07-10 647c474
  - Do: Vue 3 + TypeScript + Vite + Pinia + router, ag-grid-community, Monaco, Vitest, and a placeholder decision page.
  - Accept (from `ui/`): `pnpm install --frozen-lockfile`; `pnpm build`; `pnpm run test -- --run`.
  - Depends: T-001.

- [x] **T-005 — Synthetic legacy application and expected decomposition.** ✅ 2026-07-10 067e78f
  - Do: build the Java 17 fixture with the six legacy constructs from the original plan: under-age, product/age limit, `startsWith` smoker loading, region JDBC lookup, occupation document, and senior loading/document. Add at least 10 behavior tests and `fixtures/legacy-enrollment/expected-decisions.yaml` mapping all six constructs to the three §1 decisions and façade aggregators. Add an unrelated class for Joern exclusion tests.
  - Accept (from `fixtures/legacy-enrollment/`): `./gradlew test`; schema test confirms exactly six mapped constructs and no unclassified construct.
  - Depends: T-002, T-003.

- [x] **T-006 — CI workflow.** ✅ 2026-07-10 068fa26
  - Do: jobs for platform (PostgreSQL service), connector, Java toolchain, fixture, and UI; pinned action majors and caches. CI must not contact shared AWS resources.
  - Accept: `uv run --project platform pytest platform/tests/ci/test_workflow.py`; `uv run --project platform python scripts/run_ci_matrix.py`. When a remote is available, record the first green run URL before closing M0.
  - Depends: T-001..T-005.

- [x] **T-007 — Joern fixture smoke.** ✅ 2026-07-10 ddbf7a2
  - Do: platform-neutral Python wrapper plus `.sh`/`.ps1` launchers; build a CPG and assert the fixture entry point exists.
  - Accept: `uv run --project platform python scripts/joern_smoke.py --site config/sites/fixture.yaml` prints a positive method count and the entry point.
  - Depends: E-003, T-005.

### M1 — Canonical IR v1 and site contracts

*Exit: the schema and conformance corpus fully define types, operators, lookup behavior, hit policies, provenance, canonical bytes, PGM context, and composition.*

- [x] **T-101 — IR conformance corpus.** ✅ 2026-07-10 c7e4c21
  - Do: before models, commit JSON cases covering every ADR-7 operator/type combination, invalid combinations, FIRST default, UNIQUE collision, COLLECT ordering/empty result, lookup hit/miss, nested groups depth 3/4, Korean strings, and the three fixture decisions.
  - Accept: `uv run pytest tests/conformance/test_corpus_shape.py` confirms every operator and hit policy has positive and negative cases.
  - Depends: T-001, T-005.

- [x] **T-102 — Pydantic decision-content models.** ✅ 2026-07-10 263de4f
  - Do: implement discriminated operands and source references, condition groups, typed outputs/defaults, program contexts, rules, and origin/confidence invariants. Reject repository status/revision/effective fields inside content. Enforce operator/type rules and Java-safe logical names.
  - Accept: `uv run pytest tests/ir/test_models.py tests/conformance/test_pydantic.py`.
  - Depends: T-101.

- [x] **T-103 — JSON Schema and canonical serialization.** ✅ 2026-07-10 8545e79
  - Do: export `docs/ir-v1.schema.json`; define canonical bytes as UTF-8 JSON with sorted object keys, compact separators, preserved list order, normalized decimals/dates, and no insignificant whitespace. Test across reordered input keys and two fresh processes.
  - Accept: `uv run pytest tests/ir/test_schema_export.py tests/ir/test_canonical.py`.
  - Depends: T-102.

- [x] **T-104 — Site, mapping, target, and composition models.** ✅ 2026-07-10 faa4b71
  - Do: validate §2.2, connection-env indirection, PGM kinds, repository aliases, target paths, commands, lookup bindings, and restricted aggregators. Reject secrets and path traversal in config.
  - Accept: `uv run pytest tests/config/test_site_profile.py`; fixture profile parses and malicious/unknown settings fail.
  - Depends: T-102.

### M2 — Governed repository and API

*Exit: immutable content/revisions, event-backed lifecycle, effective dating, review queue, and semantic diff are transactionally enforced.*

- [x] **T-201 — Schema and migrations.** ✅ 2026-07-10 887d5a5
  - Do: tables for decisions, immutable content blobs keyed by hash, revision envelopes, lifecycle events, review-queue items, golden suites/revisions/cases, and lookup snapshots. Trigger blocks content/hash/revision/effective updates; lifecycle projection changes require a matching event in the same transaction.
  - Accept: reset local DB; `uv run alembic upgrade head`; `uv run pytest tests/repository/test_schema.py` including forbidden-update tests.
  - Depends: T-002, T-103.

- [x] **T-202 — Revision repository service.** ✅ 2026-07-10 9defbbc
  - Do: create decision/revision, fetch by revision, list, resolve approved revision by explicit revision or `as_of`, and deduplicate content blobs. Server assigns revision numbers under row lock; client content cannot override them.
  - Accept: `uv run pytest tests/repository/test_revision_service.py` including concurrent revision creation.
  - Depends: T-201.

- [x] **T-203 — Lifecycle, maker-checker, and effective dates.** ✅ 2026-07-10 c6ca62f
  - Do: implement ADR-6 state machine; require reasons for reject/retire; approver differs from creator and submitter; approval rejects overlapping effective intervals. Call an injected `ReleaseEvidencePolicy` before approval so T-402 can wire the governed golden-suite requirement without coupling the lifecycle service to golden storage.
  - Accept: `uv run pytest tests/repository/test_lifecycle.py` including self-approval, maker-as-approver, overlap, future/as-of, and illegal transition cases.
  - Depends: T-202.

- [x] **T-204 — Audit and review queue.** ✅ 2026-07-10 c0eaece
  - Do: append actor, correlation id, content hash, before/after states, reason, and timestamp for every write; persist unmappable raw fragments with exact provenance and disposition history.
  - Accept: `uv run pytest tests/repository/test_audit.py tests/repository/test_review_queue.py`.
  - Depends: T-203.

- [x] **T-205 — Repository API.** ✅ 2026-07-10 4ab01a2
  - Do: implement §2.3 repository routes with RFC 7807 errors. Actor required on writes only. Return envelope and content as distinct fields.
  - Accept: `uv run pytest tests/api/test_repository_api.py` covering actor rules, maker-checker, content/status separation, effective resolution, and Korean round-trip.
  - Depends: T-203, T-204.

- [x] **T-206 — Semantic diff.** ✅ 2026-07-10 98d2e21
  - Do: diff inputs, outputs, defaults, lookups, program contexts, groups, rules, and provenance; stable paths and ordering; route by revision.
  - Accept: `uv run pytest tests/governance/test_diff.py`.
  - Depends: T-202.

### M3 — Source adapters

*Exit: DB, Java, and a bounded manual source all produce traced candidate batches; repeated ingestion is idempotent.*

- [x] **T-301 — Adapter and extraction-batch contracts.** ✅ 2026-07-10 28545a2
  - Do: `SourceAdapter.discover()` and `extract() -> ExtractionBatch{decisions, unmappable, diagnostics, source_snapshot}`; registry and capability versions.
  - Accept: `uv run pytest tests/adapters/test_contract.py`.
  - Depends: T-102, T-104.

- [x] **T-302 — Secure reusable MCP DB connector.** ✅ 2026-07-10 790c939
  - Do: standalone FastMCP package for list tables, schema, bounded sample rows, and stored-procedure source. Use a SELECT-only role, read-only transactions, catalog allowlists, driver identifier quoting, row/time limits, and redacted logs.
  - Accept (from `mcp-db-connector/`): `uv run pytest`; tests prove reads work, writes fail, injection identifiers fail, limit >50 fails, and secrets never appear in captured logs.
  - Depends: T-002.

- [x] **T-303 — PostgreSQL table adapter.** ✅ 2026-07-10 9358896
  - Do: mapping-driven rows to rules with `DB_ROW` primary-key JSON and snapshot hash; confidence 1.0; deterministic ordering and typed values.
  - Accept: `uv run pytest tests/adapters/test_db_postgres.py`; Korean values and composite primary keys round-trip byte-exact.
  - Depends: T-301, T-302.

- [x] **T-304 — Joern locate.** ✅ 2026-07-10 201d486
  - Do: pin source commit, build CPG, map PGM context, traverse reachable private helpers, and exclude unrelated code.
  - Accept: `uv run pytest tests/adapters/test_joern_locate.py`.
  - Depends: T-007, T-301.

- [x] **T-305 — Joern decision slices.** ✅ 2026-07-10 24a920b
  - Do: slice if/switch/ternary/JDBC constructs, max 120 lines, exact immutable source reference, manifest and diagnostics.
  - Accept: `uv run pytest tests/adapters/test_joern_slice.py`; all six expected constructs are covered exactly once.
  - Depends: T-304.

- [x] **T-306 — Provider-swappable LLM client.** ✅ 2026-07-10 8239e84
  - Do: mock, Anthropic-compatible, and OpenAI-compatible HTTP providers through `httpx`; structured validation; at most three attempts; token/latency counters; no prompt/response source text in normal logs. Live tests opt-in only.
  - Accept: `uv run pytest tests/llm/` covering valid, retry, exhaustion, redaction, Korean, and provider-contract cases.
  - Depends: T-102.

- [x] **T-307 — Java rule mining.** ✅ 2026-07-10 bbdb9e5
  - Do: slices to candidate content/unmappable items. Recorded mocks map all six fixture constructs into the three §1 decisions: `STARTS_WITH`, lookup operand, COLLECT loading rows, and COLLECT document rows. Identical normalized rules collapse; provenance never collapses.
  - Accept: `uv run pytest tests/adapters/test_code_java.py`; output matches `expected-decisions.yaml`, all rule references have exact commit/file/lines, and an unsupported raw call reaches review queue.
  - Depends: T-305, T-306.

- [x] **T-308 — Supplementary manual adapter.** ✅ 2026-07-10 41014ff
  - Do: native-first extraction for the synthetic DOCX/XLSX manual; preserve page/sheet/section/cell provenance; low default confidence; candidate-only. Reuse libraries, not the knowledge-assistant ingestion service.
  - Accept: `uv run pytest tests/adapters/test_docs_manual.py`; Korean evidence and source locations survive, sparse/ambiguous text becomes review queue.
  - Depends: T-301.

- [x] **T-309 — Idempotent ingestion runner.** ✅ 2026-07-10 88c108c
  - Do: `brp ingest --site`; hash source snapshot + adapter version + canonical candidate content; identical rerun inserts nothing, changed source creates a new draft and audit entry.
  - Accept: `uv run pytest tests/e2e/test_ingest.py` with identical and changed-source runs.
  - Depends: T-205, T-303, T-307, T-308.

### M4 — Preview, golden governance, and UI

*Exit: preview is explicitly advisory; golden suites and lookup snapshots are governed release inputs; UI cannot bypass lifecycle rules.*

- [x] **T-401 — JDM export and Zen conformance.** ✅ 2026-07-10 1d0a07b
  - Do: pure content-to-JDM transform and Zen adapter for ADR-7 semantics; lookup snapshot resolver; preview response includes `executor=ZEN`, `authority=ADVISORY` for Mode B.
  - Accept: `uv run pytest tests/governance/test_zen_conformance.py tests/conformance/test_zen.py`.
  - Depends: T-103, T-205.

- [x] **T-402 — Versioned golden suites and lookup snapshots.** ✅ 2026-07-10 65e2d59
  - Do: import fixture behavior cases with provenance; immutable suite revisions; maker-checker; snapshot lookup rows canonically and hash them; wire `ReleaseEvidencePolicy` so decision approval requires an approved suite revision.
  - Accept: `uv run pytest tests/governance/test_golden_repository.py` including mutation rejection, suite self-approval rejection, and snapshot determinism.
  - Depends: T-203, T-005.

- [x] **T-403 — Golden runner API.** ✅ 2026-07-10 f26e600
  - Do: Zen advisory runner now; generated-Java executor plugs in at T-504. Response names executor, authority, suite revision/hash, lookup snapshots, passed/failed cases.
  - Accept: `uv run pytest tests/api/test_golden_api.py`; Mode B Zen result can never report `AUTHORITATIVE`.
  - Depends: T-401, T-402.

- [x] **T-404 — Minimal governance UI.** ✅ 2026-07-10 5f297e5
  - Do: decision list/detail, content/envelope separation, edit-as-new-revision, actor picker, submit/approve/reject, audit, semantic diff, review queue, golden-suite status, and advisory preview panel.
  - Accept (from `ui/`): `pnpm run test -- --run`; `pnpm build`; `pnpm test:e2e`; the e2e run captures list/detail/preview screenshots and fails on browser console errors.
  - Depends: T-205, T-206, T-403.

### M5 — Deterministic Java generation

*Exit: one ReleaseInput produces byte-identical source/tests/manifests; generated Java passes the shared semantics corpus.*

- [x] **T-501 — Generator and ReleaseInput contracts.** ✅ 2026-07-10 fade3a8
  - Do: target generator capability contract; manifest hashes content/revision, golden suite, lookup snapshots, site config, composition, generator, and outputs.
  - Accept: `uv run pytest tests/generators/test_contract.py tests/generators/test_release_input.py`.
  - Depends: T-103, T-104, T-402.

- [x] **T-502 — JavaPoet decision generator.** ✅ 2026-07-10 c66e0d3
  - Do: typed records, operands/operators, nested groups, lookup calls, FIRST/UNIQUE defaults, UNIQUE collision, COLLECT list, generated annotations/header, deterministic formatting.
  - Accept (from `java-toolchain/`): `./gradlew :codegen-cli:test`; Java results match every conformance case and two fresh output directories are byte-identical.
  - Depends: T-003, T-103.

- [x] **T-503 — Runtime, packaging, and composition façade.** ✅ 2026-07-10 da0df40
  - Do: typed `LookupProvider`, missing/type exceptions, generated-module template, restricted site façade aggregators, and fixture JDBC provider.
  - Accept: `uv run --project platform python scripts/gen_compile_fixture.py`; façade tests prove SUM, DISTINCT, FIRST_NON_NULL, Korean, lookup hit/miss.
  - Depends: T-502, T-104.

- [x] **T-504 — Generated golden tests.** ✅ 2026-07-10 aca89e3
  - Do: suite revision + snapshots to JUnit exercising generated classes and façade. Register `generated-java` runner as Mode-B authority.
  - Accept: `uv run --project platform pytest platform/tests/generators/test_generated_tests.py`; tests compile/run JUnit, plant a failing expectation, and verify manifest changes for suite/lookup changes.
  - Depends: T-402, T-503.

- [x] **T-505 — Generation orchestration.** ✅ 2026-07-10 541426c
  - Do: `brp generate --site --decision --revision|--as-of`; require approved effective revision and approved suite; assemble ReleaseInput; invoke CLI with tests; write versioned output atomically; refuse drafts and ambiguous effective revisions.
  - Accept: `uv run pytest tests/e2e/test_generate.py` including pending, overlap, missing-suite, atomic-failure, and deterministic rerun cases.
  - Depends: T-203, T-501, T-504.

- [x] **T-506 — Preview/generated consistency.** ✅ 2026-07-10 b3215d7
  - Do: run conformance and golden suites through Zen and generated Java; report divergence as generator/export defect without changing Mode-B authority.
  - Accept: `uv run pytest tests/e2e/test_consistency.py` including planted divergences.
  - Depends: T-401, T-504.

### M6 — Seam-first Mode-B delivery

*Exit: recurring delivery branches from a seam-enabled baseline and the target application executes regenerated code before a review branch is emitted.*

- [x] **T-601 — One-time seam baseline.** ✅ 2026-07-10 7ebc13a
  - Do: create a local bare fixture remote; install the initially approved generated module; apply OpenRewrite recipe and reviewed façade/JDBC provider; commit seam to `main`; run pre/post behavior and shadow tests; tag `seam-baseline-v1`.
  - Accept: `uv run --project platform pytest platform/tests/e2e/test_seam_baseline.py`; the test uses a fresh clone, runs fixture tests, proves `EnrollmentValidator` calls the generated façade, and asserts the tag.
  - Depends: T-307, T-505.

- [x] **T-602 — Transactional delivery gate.** ✅ 2026-07-11 bce84b9
  - Do: clone/worktree from configured seam baseline; generate; copy only manifest-listed files; compile generated module; run generated golden tests and target application regression tests through the façade. On failure, leave no commit or delivery branch and emit a failure report.
  - Accept: `uv run pytest tests/e2e/test_delivery_gate.py` with success plus corrupted expectation/source/config negatives.
  - Depends: T-505, T-601.

- [x] **T-603 — Diff, branch, push, and review report.** ✅ 2026-07-11 a61dbe6
  - Do: after gate success create `rules/gen-<key>-r<N>`, commit manifest and artifacts, push to configured remote, and emit `review-report.md` containing semantic rule diff, generated file diff, evidence hashes, tests, and exact base/head commits. Provider adapters may open GitHub/GitLab PRs later; fixture uses `local-report`.
  - Accept: `uv run --project platform pytest platform/tests/e2e/test_delivery_branch.py`; tests assert branch/commit/push/report and that gate failure creates none.
  - Depends: T-206, T-602.

- [x] **T-604 — Delivered-branch execution proof.** ✅ 2026-07-11 dd57ab2
  - Do: check out the pushed delivery branch in a fresh clone, run its build/tests, invoke the legacy entry point, and capture output plus commit and manifest hashes.
  - Accept: `uv run --project platform pytest platform/tests/e2e/test_delivered_execution.py`; the test changes `<18` to `<19`, verifies `main` and delivery-branch outcomes, and instruments `EnrollmentValidator` to prove both calls use the façade rather than Zen/direct generated classes.
  - Depends: T-603.

### M7 — End-to-end PoC

- [x] **T-701 — Repeatable Mode-B demo.** ✅ 2026-07-11 22d2015
  - Do: one `.sh` and `.ps1` orchestrated by a shared Python CLI: reset local DB/remote; ingest; disposition unmappable items; approve suite and decisions with two actors; establish seam baseline; print legacy-app BEFORE; create/edit/submit/approve revision; deliver; run fresh delivery clone; print AFTER; show revision, suite, lookup, manifest, branch, commit, and timings.
  - Accept: `bash scripts/demo-mode-b.sh`; `pwsh -File scripts/demo-mode-b.ps1`; both outputs include `BEFORE: ELIGIBLE`, `AFTER: REJECTED(UNDER_AGE)`, `EXECUTOR: GENERATED_JAVA`, and a delivery commit hash.
  - Depends: all M2–M6 tasks.

- [x] **T-702 — Fresh-checkout documentation.** ✅ 2026-07-11 8a67713
  - Do: `docs/demo.md`, architecture links, exact prerequisites/commands/expected output, troubleshooting, security boundaries, and explanation of advisory vs authoritative results.
  - Accept: `uv run --project platform python scripts/verify_fresh_checkout.py --guide docs/demo.md`; record platform and commit in Progress Log.
  - Depends: T-701.

### M8 — Phase 2 (human-gated)

- [x] **PHASE-2-GATE — Human authorization.** ✅ 2026-07-11 user authorization
  - Scope: implement T-801–T-805 as reusable local/self-hosted product capabilities. Use synthetic/local evidence where customer inputs remain unavailable; do not claim real-site mining accuracy or production readiness.
  - Still gated: customer-approved real Java slices and ground truth, provider/foreign-model policy, pilot approval-role matrix, production IdP metadata, and a production second-DBMS target.

- [x] **T-801 — DMN import adapter.** ✅ 2026-07-11 93e21d7
  - Do: parse DMN 1.3+ decision tables into candidate Rule IR; support literal/simple comparison/range/list FEEL only; preserve asset/revision/decision/element provenance; route unsupported FEEL/boxed expressions to review; reject BPMN documents.
  - Accept: `uv run pytest tests/adapters/test_dmn.py`; tests cover FIRST/UNIQUE/COLLECT, Korean text, exact element provenance, restricted FEEL, unsupported FEEL review items, and BPMN rejection.
  - Depends: T-301, T-309.

- [x] **T-802 — Mode-A Zen service.** ✅ 2026-07-11 0f34366
  - Do: publish only approved/effective decision revisions with approved golden evidence; run the golden suite authoritatively on Zen before activation; keep an immutable publication history; resolve the active release; rollback by appending a publication that points to a previously validated revision.
  - Accept: `uv run pytest tests/mode_a/`; tests cover publish, draft/ineffective/missing-suite denial, authoritative golden failure, Korean lookup snapshots, active execution, audit, and rollback.
  - Depends: T-401, T-402, T-403, T-801.

- [x] **T-803 — Second DBMS connector.** ✅ 2026-07-11 1717f2a
  - Do: refactor the MCP connector behind a driver protocol and add SQLite as the dependency-free local second-DBMS proof; preserve catalog allowlists, identifier quoting, row limits, read-only enforcement, stored-object capability reporting, and redacted logs.
  - Accept (from `mcp-db-connector/`): `uv run pytest`; shared contract tests run for PostgreSQL and SQLite, with writes/injection/excess limits rejected for both and unsupported stored-procedure source reported explicitly.
  - Depends: T-302.

- [x] **T-804 — Real-slice mining benchmark.** ✅ 2026-07-11 02f7bcc
  - Do: implement the versioned benchmark/ground-truth format and precision/recall/cost/latency runner with provider-policy enforcement and per-construct diagnostics. Check in a synthetic proof only until customer-approved slices arrive.
  - Accept: `uv run pytest tests/benchmark/`; synthetic metrics are reproducible and labeled `SYNTHETIC_NON_CUSTOMER`; a `REAL_CUSTOMER` run fails closed without approval metadata and provider policy.
  - Depends: T-305, T-306, T-307.

- [x] **T-805 — Governance hardening.** ✅ 2026-07-11 b8ff071
  - Do: OIDC/JWT validation with issuer/audience/JWKS configuration; role enforcement for maker/checker/reviewer/deployer; configurable release-evidence policy; atomic batch review; deployment authorization and audit. Keep Phase-1 development headers available only behind an explicit local-development flag.
  - Accept: `uv run pytest tests/security/ tests/governance/test_batch_review.py tests/api/test_deployment_authorization.py`; cover invalid issuer/audience/signature/expiry, role denial, maker-checker, evidence policy, batch rollback, deployment authorization, and header-mode production rejection.
  - Depends: T-204, T-402, T-802.

**Phase-2 verification (local/synthetic):** platform Ruff and strict mypy passed; 162 non-E2E and 8 E2E platform tests passed; connector 10 tests passed for PostgreSQL/SQLite; UI unit/build/Playwright passed; Java toolchain and legacy-fixture Gradle tests passed. The mining evidence label remains `SYNTHETIC_NON_CUSTOMER`.

### M9 — Phase 3 scale (human-authorized, generic/local scope)

- [x] **PHASE-3-GATE — Human authorization.** ✅ 2026-07-12 user authorization
  - Scope: implement reusable/local proofs for T-901–T-906. Restricted parsers must fail closed to review; synthetic fixtures cannot support real-site compatibility or accuracy claims.
  - Still gated: customer stored-object/UI/DRL/ODM samples, real target conventions, a production non-PostgreSQL DBMS, installed .NET SDK/target repository, and multi-site rollout approval.

- [x] **T-901 — Restricted PostgreSQL stored-procedure mining.** ✅ 2026-07-12 ea65134
  - Do: ingest immutable PL/pgSQL function source from the bounded connector/source snapshot; map only scalar input comparisons plus literal `RETURN` branches into candidate Rule IR; preserve stored-object and line provenance; route SQL, calls, assignments, loops, and unsupported syntax to review.
  - Accept: `uv run pytest tests/adapters/test_db_stored_object.py`; cover Korean literals, deterministic candidates, exact provenance, unsupported routing, and injection-free connector boundaries.
  - Depends: T-301, T-302, T-309.

- [x] **T-902 — Declarative UI validation adapter.** ✅ 2026-07-12 9be14d9
  - Do: parse static HTML input validation metadata into candidate IR for numeric min/max and explicit equality/list data rules; preserve file/element provenance; route required/pattern/scripts/framework expressions to review instead of executing UI code.
  - Accept: `uv run pytest tests/adapters/test_ui_validation.py`; cover Korean error codes/text, supported validations, unsupported attributes/scripts, stable source hashes, and no script execution.
  - Depends: T-301, T-309.

- [x] **T-903 — Engine-native import boundary.** ✅ 2026-07-12 29d3a06
  - Do: import a restricted DRL decision-rule subset (fact-field comparisons and literal setter actions) into candidate IR with exact asset/rule provenance; classify ODM artifacts and route them to review until customer format/version samples exist; reject workflow assets.
  - Accept: `uv run pytest tests/adapters/test_engine_native.py`; cover DRL rules/default, Korean text, unsupported consequences, ODM review routing, and BPMN rejection.
  - Depends: T-801.

- [x] **T-904 — Deterministic DMN export.** ✅ 2026-07-12 12d58a0
  - Do: export approved-profile IR decision tables to deterministic DMN 1.3 XML with typed inputs/outputs, FIRST/UNIQUE/COLLECT policies, restricted FEEL, provenance extension metadata, and no repository envelope fields.
  - Accept: `uv run pytest tests/generators/test_dmn_export.py`; byte stability, Korean UTF-8, XML safety, canonical re-import equivalence, and explicit rejection of non-representable operands.
  - Depends: T-102, T-801.

- [x] **T-905 — C# target plug-in proof.** ✅ 2026-07-12 c492456
  - Do: add a deterministic C# generator for IR v1 scalar operators, FIRST/UNIQUE/COLLECT, typed records, and lookup contract; emit manifest hashes and golden-test source. Compilation is authoritative only when an installed/pinned .NET SDK runs; otherwise report `COMPILE_NOT_RUN` and never claim executable proof.
  - Accept: `uv run pytest tests/generators/test_csharp.py`; deterministic snapshots and operator coverage pass; compile gate either runs successfully or returns the explicit fail-closed status on this host.
  - Depends: T-501, T-502, T-504.

- [x] **T-906 — Multi-site capability orchestration.** ✅ 2026-07-12 da4c715
  - Do: extend the adapter/target registry and site profile with capability declarations; validate incompatible source/target/profile combinations before work starts; produce a deterministic capability matrix for multiple synthetic sites/products/flows.
  - Accept: `uv run pytest tests/config/test_capability_matrix.py`; cover compatible Java/DMN/C# paths, unavailable toolchains, unsupported DB/engine/UI combinations, deterministic reports, and secret-free configuration.
  - Depends: T-104, T-301, T-905.

**Phase-3 verification (generic/local):** platform Ruff and strict mypy passed; 186 non-E2E and 8 E2E platform tests passed; connector 10 tests passed; UI unit/build/Playwright passed; Java toolchain and legacy-fixture Gradle tests passed. C# source/golden/manifest generation is deterministic, but the host has no .NET SDK, so its compile evidence is `COMPILE_NOT_RUN`. Stored-object/UI/DRL/ODM fixtures are synthetic and do not support real-site compatibility or accuracy claims.

### M10 — Phase-3 local orchestration follow-up

- [x] **T-907 — Phase-3 API/UI orchestration workbench.** ✅ 2026-07-12 0137c40
  - Do: expose a safe local catalog, inline restricted extraction, DMN/C# target preview, and multi-site preflight through FastAPI; add a Vue workbench for samples/local files, candidate/review inspection, artifacts, and readiness evidence. Never persist, approve, publish, or execute uploaded code.
  - Accept: `uv run pytest tests/api/test_orchestration_api.py`; from `ui/`, `pnpm run test -- --run`, `pnpm run build`, and `pnpm run test:e2e`; live HTTP smoke proves PL/pgSQL → candidate → DMN preview with `persistent=false` and `authoritative=false`.
  - Depends: T-901–T-906.

**T-907 verification:** platform Ruff and strict mypy passed with 190 non-E2E tests; UI 4 component tests, production build, and 2 Playwright flows passed. Live API/UI served on ports 8100/5173 and produced one candidate plus a hashed DMN preview. The in-app browser-control plugin could not attach because its local kernel-asset setup failed; repository Playwright and live HTTP verification remained green.

### M11 — Internal self-hosted production hardening (historical, paused)

*Historical target only. Do not resume T-1003–T-1006 from this appendix unless a
human explicitly reactivates production hardening after F-304 and F-402. The
unchecked status records unfinished historical work; it is not the current queue.*

- [x] **T-1001 — Multi-workspace/site control plane and `/api/v1`.** ✅ 2026-07-16 working-tree
  - Implemented: workspace/site scoping, versioned secret-reference-only profiles,
    indexed decision metadata and pagination, optimistic revision concurrency,
    RFC 7807 problems, correlation IDs, compatibility aliases and Alembic
    revisions `0005`–`0007`.
  - Evidence: targeted API/repository tests passed against isolated `brp_test`;
    destructive-test fuse rejects shared database names.

- [x] **T-1002 — Durable imports, jobs, artifacts and releases.** ✅ 2026-07-16 working-tree
  - Implemented: PostgreSQL `SKIP LOCKED` leases, heartbeats, retry/cancel/recovery,
    separate worker, durable inline and pinned-Java-repository imports, candidate
    provenance/promotion, golden jobs, local/S3 artifact abstraction, Mode-A
    publish/rollback and Mode-B GitHub/GitLab provider seams.
  - Evidence: isolated Java import resolved commit `888621061246…`, produced three
    candidates and proved idempotent promotion; real local-bare-Git Mode-B delivery,
    artifact hash/download, Mode-A publication and rollback all passed.

- [ ] **T-1003 — Enterprise console final acceptance.** IN PROGRESS 2026-07-16
  - Implemented: enterprise shell, workspace/site context, Overview, Decisions,
    Imports, Review Queue, Test Suites, Releases, Sites and Operations; server-side
    pagination/filtering, ag-Grid, lazy Monaco, EN/KR, lifecycle actions, lookup
    snapshots, job progress/cancellation and responsive states.
  - Remaining: rerun build, Vitest, Playwright/axe and live browser verification
    after the latest lookup/release/lifecycle edits; resolve any regression found.

- [ ] **T-1004 — Production packaging and operations.** IN PROGRESS 2026-07-16
  - Implemented: API/UI Dockerfiles, nginx proxy/security policy, Compose API/UI/
    worker/PostgreSQL/optional-Joern services, non-root/read-only controls, health,
    readiness, metrics, structured redacted logs and validated runtime settings.
  - Remaining: fix Docker build-context/node_modules contamination, ensure the
    worker image contains Git/JDK/toolchain paths, rebuild both images and run the
    complete Compose health/start/stop rehearsal.

- [ ] **T-1005 — CI-equivalent release gate.** IN PROGRESS 2026-07-16
  - Implemented: expanded CI definitions for Ruff, strict mypy, backend/frontend
    tests, OpenAPI drift, accessibility, Playwright, image builds, dependency and
    secret scans, Trivy and SBOM.
  - Remaining: regenerate OpenAPI after the newest routes; rerun full backend suite
    (the last full run exposed two failures that were fixed and passed focused
    reruns), frontend gates, Java/fixture builds, container scans and a 10,000-row
    performance rehearsal. Do not call the release green until these complete.

- [ ] **T-1006 — Protected RDS hardening cutover.** PENDING 2026-07-16
  - Current RDS `brp` is the verified historical copy at `0004`; isolated hardening
    is at `0007`. No hardening cutover has occurred.
  - Remaining: stop writers, create timestamped custom dump plus SHA-256, record a
    read-only `rag_utils` fingerprint, recreate only `brp`, migrate/seed curated
    data, run workflow smoke tests and retain the documented `0004` rollback path.
  - Depends: T-1003, T-1004 and T-1005 green.

Detailed live evidence and blockers are maintained in
[`docs/production-hardening-progress.md`](docs/production-hardening-progress.md).

---

## 4. Customer-Gated Inputs

| Input | Blocks | Does not block |
|---|---|---|
| Masked Java source, DB schema, and immutable sample revision | Real-site M3 validation; T-804 | Synthetic contracts and demo |
| Pilot product/flow and PGM mappings | Real seam/site config | Generic `program_contexts` contract |
| Pilot role/group mapping and evidence thresholds | Production rollout configuration | Generic four-role enforcement and configurable policy |
| Production IdP issuer/audience/JWKS metadata | Production authentication rollout | OIDC/JWT validation and local cryptographic tests |
| Provider/foreign-model policy and approved ground truth | Live mining and real T-804 run | Recorded mock extraction and synthetic benchmark proof |
| Production second-DBMS choice and access | Production portability proof | PostgreSQL reference and local SQLite driver contract |
| Coding conventions and target repository commands | Real generator style/seam | Fixture JavaPoet path |
| Lookup freshness and release-channel policy | Production SLA/rollout | Snapshot-based golden gate |
| Stored-object, UI, DRL, and ODM samples with immutable revisions | Real Phase-3 compatibility/accuracy evidence | Restricted synthetic adapters and review routing |
| Pinned .NET SDK and C# target repository conventions | Executable C# delivery proof | Deterministic source-generation plug-in and fail-closed compile status |

## 5. Global Definition Of Done

A task is complete only when its acceptance tests pass, changed projects remain lint/build clean, invariants in §0.3 hold, docs/config examples match behavior, CI is green when applicable, and the Progress Log is updated. A milestone is complete only when every task is checked and its exit statement is demonstrated.

## 6. Out Of Scope

Chat/RAG/Neptune integration; using knowledge-assistant chunks as the rule system of record; full FEEL; BPMN-as-rules; arbitrary stored-procedure dialects or executable UI/framework code; full ODM compatibility without customer artifacts; arbitrary expressions or custom aggregators in IR; bespoke preview evaluator; automatic merge/deploy.

## 7. Progress Log

```text
2026-07-10 18:02 | E-000 | done | 76b6331 | Aligned implementation status, per-site delivery modes, and isolated-track boundary.
2026-07-10 18:05 | E-001 | done | 63017a4 | Verified Python 3.12, JDK 17, Node, pnpm 9, Git, and Docker Compose locally.
2026-07-10 18:08 | T-001 | done | fddbb1f | Created the Python 3.12 package, locked dependencies, repository layout, and passing smoke test.
2026-07-10 18:11 | E-002 | done | 4b152ec | Started an isolated local PostgreSQL 16 stack and verified the redacted psycopg probe.
2026-07-10 18:22 | T-002 | done | 8f0019e | Added idempotent PostgreSQL fixture schema, Korean seed data, and cross-platform loaders.
2026-07-10 18:27 | T-003 | done | 90c3a48 | Added Gradle 8.7 Java 17 modules, pinned wrapper checksum, formatting, and smoke tests.
2026-07-10 18:30 | T-004 | done | 647c474 | Added Vue, Pinia, router, grid/editor dependencies, build config, and a passing component smoke test.
2026-07-10 18:33 | T-005 | done | 067e78f | Added six legacy decision constructs, 12 behavior tests, H2 isolation, and expected decomposition metadata.
2026-07-10 18:34 | E-003 | done | 7300c89 | Pinned and verified Joern 4.0.579 by immutable container digest.
2026-07-10 18:37 | T-006 | done | 068fa26 | Added isolated CI jobs and a passing local matrix across Python, Java, connector, fixture, and UI.
2026-07-10 18:39 | T-007 | done | ddbf7a2 | Built the fixture CPG and found 39 methods plus the configured enrollment entry point.
2026-07-10 18:42 | T-101 | done | c7e4c21 | Defined positive/negative cases for every IR operator, hit policy, lookup, nesting, provenance, and fixture decision.
2026-07-10 18:46 | T-102 | done | 263de4f | Implemented strict Rule IR v1 content, operand, lookup, provenance, and cross-reference validation.
2026-07-10 18:48 | T-103 | done | 8545e79 | Added committed JSON Schema and stable UTF-8 canonical bytes across key order and fresh processes.
2026-07-10 18:50 | T-104 | done | faa4b71 | Validated secret-free source, PGM context, target, composition, path, and adapter contracts.
2026-07-10 19:06 | T-201 | done | 887d5a5 | Added immutable JSONB content, revision envelopes, lifecycle events, release evidence tables, and database triggers.
2026-07-10 19:08 | T-202 | done | 9defbbc | Added content-addressed revisions, row-locked numbering, concurrent creation, and effective approved resolution.
2026-07-10 19:10 | T-203 | done | c6ca62f | Enforced transactional lifecycle, maker-checker, release evidence policy, reasons, and effective overlap checks.
2026-07-10 19:13 | T-204 | done | c0eaece | Audited every revision/transition and added persistent unmappable-fragment disposition history.
2026-07-10 19:16 | T-205 | done | 4ab01a2 | Exposed actor-gated writes, actor-free reads, lifecycle, effective resolution, Korean content, and audit routes.
2026-07-10 19:20 | T-206 | done | 98d2e21 | Added stable semantic revision diffs for named IR structures and provenance.
2026-07-10 19:25 | T-301 | done | 28545a2 | Defined capability-versioned source, batch, candidate, diagnostic, and unmappable contracts.
2026-07-10 19:31 | T-302 | done | 790c939 | Added the bounded read-only FastMCP PostgreSQL connector with injection and redaction tests.
2026-07-10 19:36 | T-303 | done | 9358896 | Mapped deterministic PostgreSQL rows into typed, byte-exact traced candidates.
2026-07-10 19:41 | T-304 | done | 201d486 | Pinned Java source revisions and located the entry point plus reachable private helper.
2026-07-10 19:45 | T-305 | done | 24a920b | Produced six exact, bounded decision slices with immutable line provenance.
2026-07-10 19:49 | T-306 | done | 8239e84 | Added mock, OpenAI-compatible, and Anthropic-compatible structured LLM providers.
2026-07-10 19:54 | T-307 | done | bbdb9e5 | Mapped all recorded Java constructs into three candidate decisions and review items.
2026-07-10 20:00 | T-308 | done | 41014ff | Added native DOCX/XLSX extraction with Korean location evidence and ambiguity routing.
2026-07-10 20:06 | T-309 | done | 88c108c | Added fingerprinted ingestion; identical sources skip and changed sources create audited drafts.
2026-07-10 20:13 | T-401 | done | 1d0a07b | Exported pure JDM and verified embedded Zen advisory semantics and lookup snapshots.
2026-07-10 20:19 | T-402 | done | 65e2d59 | Governed immutable golden suites and lookup snapshots with maker-checker release evidence.
2026-07-10 20:24 | T-403 | done | f26e600 | Added preview and golden runner APIs with explicit executor authority metadata.
2026-07-10 20:42 | T-404 | done | 5f297e5 | Built and browser-verified the governance workspace, screenshots, and console-error gate.
2026-07-10 20:48 | T-501 | done | fade3a8 | Hashed all ADR-8 release inputs and outputs in deterministic generator contracts.
2026-07-10 21:02 | T-502 | done | c66e0d3 | Added the deterministic JavaPoet Rule IR generator and centralized operator semantics.
2026-07-11 00:10 | T-503 | done | da0df40 | Compiled and executed the fixture façade with typed lookups and restricted aggregators.
2026-07-11 00:18 | T-504 | done | aca89e3 | Generated authoritative JUnit and proved both passing and planted-failure gates.
2026-07-11 00:24 | T-505 | done | 541426c | Added approved/effective generation orchestration and atomic versioned outputs.
2026-07-11 00:28 | T-506 | done | b3215d7 | Reported Zen/generated divergence as generator/export defects without changing authority.
2026-07-11 00:37 | T-601 | done | 7ebc13a | Created, tagged, pushed, and fresh-clone-tested the one-time façade seam baseline.
2026-07-11 00:44 | T-602 | done | bce84b9 | Gated manifest-only delivery with generated and target tests and failure evidence.
2026-07-11 00:49 | T-603 | done | a61dbe6 | Pushed deterministic review branches with exact commit, diff, manifest, and test evidence.
2026-07-11 00:57 | T-604 | done | dd57ab2 | Proved main/delivery outcomes from fresh clones and instrumented façade calls.
2026-07-11 01:05 | T-701 | done | 22d2015 | Ran the shared Mode-B demo: ELIGIBLE to UNDER_AGE via delivered generated Java.
2026-07-11 01:09 | T-702 | done | 8a67713 | Verified the Windows 11 fresh-checkout guide structure and recorded local-only boundaries.
2026-07-11 01:27 | T-801 | done | 93e21d7 | Added restricted DMN decision-table import with exact provenance, Korean text, review routing, and BPMN rejection.
2026-07-11 01:43 | T-802 | done | 0f34366 | Added authoritative Zen publication, immutable evidence history, active execution, audit, and append-only rollback.
2026-07-11 01:55 | T-803 | done | 1717f2a | Refactored the bounded connector behind a driver contract and proved PostgreSQL/SQLite read-only parity.
2026-07-11 02:07 | T-804 | done | 02f7bcc | Added versioned ground truth, provider-policy gates, reproducible metrics, and a synthetic-only benchmark proof.
2026-07-11 02:31 | T-805 | done | b8ff071 | Added OIDC/JWKS validation, four-role enforcement, configurable evidence, atomic batch review, and deployment audit.
2026-07-11 03:18 | M8 | done | 45cd7f5 | Passed full cross-project regression and aligned Phase-2 architecture, environment, and customer-gated boundaries.
2026-07-12 19:58 | T-901 | done | ea65134 | Added fail-closed scalar PL/pgSQL mining with immutable stored-object and line provenance.
2026-07-12 20:08 | T-902 | done | 9be14d9 | Added non-executing HTML validation mining with element provenance and unsupported-script review routing.
2026-07-12 20:18 | T-903 | done | 29d3a06 | Added restricted DRL import, ODM customer-mapping review routing, and BPMN rejection.
2026-07-12 20:28 | T-904 | done | 12d58a0 | Added deterministic restricted DMN export with provenance extensions and semantic round-trip proof.
2026-07-12 20:45 | T-905 | done | c492456 | Added deterministic C# source/golden/manifest generation; compile evidence is explicitly COMPILE_NOT_RUN without a local .NET SDK.
2026-07-12 21:00 | T-906 | done | da4c715 | Added deterministic multi-site source/target/runtime capability preflight with fail-closed compatibility and toolchain status.
2026-07-12 21:14 | M9 | done | c9e0a8f | Passed full cross-project regression and aligned Phase-3 architecture, toolchain evidence, and customer-gated boundaries.
2026-07-12 17:16 | T-907 | done | 0137c40 | Added safe Phase-3 API/UI orchestration, candidate/artifact inspection, and capability preflight with non-authoritative evidence labels.
2026-07-16 14:45 | T-1001 | done | working-tree | Added the site-scoped versioned control plane, migrations 0005–0007, concurrency, problem details and test-database safety fuse.
2026-07-16 14:46 | T-1002 | done | working-tree | Proved durable Java import/promotion, worker leases, Mode-A rollback and Mode-B bare-Git delivery with hashed artifacts on isolated PostgreSQL.
2026-07-16 14:47 | T-1003 | IN PROGRESS | working-tree | Enterprise console implemented; final post-edit frontend and browser regression remains open.
2026-07-16 14:48 | T-1004 | IN PROGRESS | working-tree | Runtime/Compose assets implemented; Docker context and worker Git/JDK/toolchain packaging remain open.
2026-07-16 14:49 | T-1005 | IN PROGRESS | working-tree | CI gates expanded; final full regression, OpenAPI refresh, scans and 10k performance proof remain open.
2026-07-16 14:50 | T-1006 | PENDING | working-tree | RDS remains at historical 0004; protected backup/recreate/migrate/smoke cutover has not started.
```
