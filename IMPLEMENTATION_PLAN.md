# Implementation Plan — Business Rules Platform

> **Audience: an AI coding agent.** This file is the execution plan and the progress tracker for building the platform described in `prd.md` (product) and `architecture.md` (design — the architecture source of truth). The customer has approved the architecture (2026-07-04). Follow the protocol below exactly.

---

## 0. Agent Protocol (read before doing anything)

**Required reading order:** `AGENTS.md` → `architecture.md` (full) → `prd.md` §5–§9 → this file.

**How to work:**
1. Pick the **first unchecked task** in the current milestone whose `Depends` are all done. Do not skip ahead across milestones (exception: M4/T-403+ may run any time after M2 is done).
2. A task is **done only when its `Accept` command(s) pass**. Run them; do not reason your way past them.
3. Mark done by changing `- [ ]` to `- [x]` and appending ` ✅ YYYY-MM-DD <short-commit-hash>` to the task line. Then append one line to the **Progress Log** (§6).
4. One task per commit where practical. Commit message: `feat(platform): T-### <task title>` (or `fix`/`chore`/`test` as appropriate).
5. If blocked (missing tool, failing environment, ambiguous requirement): do **not** mark the task; append a `BLOCKED:` line to the Progress Log with what you tried, then move to the next unblocked task.
6. Never modify `prd.md` / `architecture.md` beyond adding links; if a design change seems needed, log it as `PROPOSAL:` in the Progress Log for human review.

**Ground rules (violating any of these = task not done, regardless of tests):**
- The **Canonical Rule IR is the only system of record** (architecture ADR-1). Never persist JDM/DMN/source as truth.
- **Production code generation is deterministic** — templates/AST only; same approved IR → byte-identical output (ADR-4). LLMs may only produce *candidate* rules (`status=PENDING_REVIEW`); LLM text never flows into generated artifacts.
- Every extracted candidate carries `sourceReferences` (exact file/line or table) and `confidence`. Nothing is auto-approved; approval requires a **different actor** than the submitter (maker-checker).
- Golden tests for mode B run against the **generated Java** (compile + execute), not the Zen preview (§9 of architecture).
- **Korean text is preserved byte-exact** through extraction → storage → generation. Include Korean strings in test fixtures.
- Nothing site-specific in core code — site differences live in config/adapters only (multi-site NFR, prd §8).
- Secrets/connection strings only via env/config files that are gitignored; never hardcode, never log them.

**Environment:** Windows dev host (Git Bash available) — keep commands cross-platform. Python via `uv`. Java via `./gradlew` wrapper. Node via `pnpm`. PostgreSQL and Joern run in Docker (`docker compose`). If Docker is unavailable, log BLOCKED for the affected tasks and continue with pure-unit tasks.

---

## 1. Context Snapshot (self-contained — do not rely on chat history)

We are building a **rule-governance and source-generation platform** for finance/insurance enrollment logic (`가입 Rule`):

- **Initial load (one-time per site):** extract rules out of legacy assets — PostgreSQL config tables, Java source code (located via Joern static analysis, converted by LLM into *candidate* rules), manuals, DMN assets — into a governed **Rule Repository** storing the vendor-neutral **Canonical Rule IR v1** (spec: `architecture.md` §5).
- **Operation (ongoing):** business users edit/approve rules; the platform delivers per site via **mode B** (deterministically regenerate Java source → build → golden tests → deploy; Phase-1 lead) or **mode A** (publish approved rules to an embedded GoRules Zen runtime; Phase 2).
- Stack (architecture §13): Python 3.12/FastAPI/Pydantic v2/SQLAlchemy/PostgreSQL 16 · Vue 3 + Vite UI · Joern · tiered provider-swappable LLM client · Java 17 toolchain (JavaPoet + google-java-format, OpenRewrite) · GoRules Zen via `zen-engine` Python binding · FastMCP + psycopg3 DB connector library.

**Customer samples have NOT arrived yet.** Therefore M0 builds a synthetic legacy fixture app that stands in for the pilot system; every later task develops against it. When real samples arrive, they slot in as a second fixture — no design change.

---

## 2. Target Repository Layout

```
business-rules-platform/
├── platform/                    # Python core (uv project)
│   ├── src/brp/
│   │   ├── ir/                  # M1 — Canonical Rule IR models + profile guard
│   │   ├── repository/          # M2 — storage, versioning, approval, audit
│   │   ├── adapters/            # M3 — SourceAdapter contract + implementations
│   │   │   ├── db_postgres/
│   │   │   └── code_java/      # Joern orchestration + LLM mining
│   │   ├── llm/                 # M3 — tiered provider-swappable client
│   │   ├── governance/          # M4 — diff, golden-test harness, zen preview
│   │   ├── generators/          # M5 — TargetGenerator contract, jdm-export, orchestration
│   │   ├── delivery/            # M6 — branch/diff/gate flow
│   │   └── api/                 # FastAPI app
│   └── tests/
├── java-toolchain/              # Gradle multi-module (Java 17)
│   ├── codegen-cli/             # M5 — IR JSON → JavaPoet → formatted .java
│   └── seam-recipes/            # M6 — OpenRewrite cut-over recipes
├── mcp-db-connector/            # M3 — reusable FastMCP server (own uv project)
├── ui/                          # M4 — Vue 3 governance UI (pnpm)
├── fixtures/
│   └── legacy-enrollment/       # M0 — synthetic legacy Java app + schema.sql + seeds
├── docker/                      # compose: postgres16, joern
├── docs/                        # generated schema exports, demo notes
└── .github/workflows/ci.yml
```

---

## 3. Milestones & Tasks

### M0 — Scaffold & Foundations
*Exit: all builds green in CI; fixture app runs its own tests; Joern parses the fixture.*

- [ ] **T-001 — Monorepo scaffold + Python project.** Create the layout above. `platform/`: `uv init`, deps `fastapi pydantic sqlalchemy alembic psycopg[binary] httpx pytest ruff`. Root `README.md` linking prd/architecture/this plan.
  - Accept: `cd platform && uv run ruff check . && uv run pytest` (0 tests is OK, exit 0).
- [ ] **T-002 — Docker services.** `docker/docker-compose.yml`: `postgres:16` (db `brp`, healthcheck) + `ghcr.io/joernio/joern` (pinned tag). Script `scripts/dev-up.sh`.
  - Accept: `docker compose -f docker/docker-compose.yml up -d postgres && scripts/wait-for-pg.sh` exit 0.
- [ ] **T-003 — Java toolchain scaffold.** Gradle 8 wrapper, Java 17, modules `codegen-cli`, `seam-recipes`; Spotless with google-java-format.
  - Accept: `cd java-toolchain && ./gradlew build` exit 0.
- [ ] **T-004 — UI scaffold.** `ui/`: Vite + Vue 3 + TypeScript + Pinia; placeholder page.
  - Accept: `cd ui && pnpm install && pnpm build` exit 0.
- [ ] **T-005 — Synthetic legacy fixture app.** `fixtures/legacy-enrollment/`: plain-Java Gradle app with `EnrollmentValidator` containing ≥6 decision points (age limit incl. `< 18 → UNDER_AGE`, product-code checks with Korean product names e.g. `"암보험 기본형"`, a rate lookup reading a config table via JDBC, nested if/else, a switch) + `db/schema.sql` + `db/seed.sql` (product master, rate table, eligibility codes). Include unit tests capturing current behavior — these become golden-test seeds later.
  - Accept: `cd fixtures/legacy-enrollment && ./gradlew test` exit 0.
- [ ] **T-006 — CI.** GitHub Actions: python lint+test, java-toolchain build, fixture test, ui build. Cache deps.
  - Accept: workflow file passes `act`-style local dry run or first push is green (log run URL).
- [ ] **T-007 — Joern smoke.** `scripts/joern-smoke.sh`: parse the fixture app, CPGQL query counts methods; assert `EnrollmentValidator.evaluate` present.
  - Accept: script exit 0, prints method count > 0.

### M1 — Canonical Rule IR v1
*Exit: IR models enforce the restricted profile; JSON Schema published; fixtures round-trip.*

- [ ] **T-101 — IR Pydantic models** per `architecture.md` §5.2–5.3: `Decision`, `Rule`, `Condition` (ops `=,!=,>,>=,<,<=,IN,NOT_IN,BETWEEN,EXISTS`), `ConditionGroup` (AND/OR, max depth 3), `Action`, `SourceReference` (types `JAVA_SOURCE|DB_TABLE|MANUAL_DOC|DMN_ASSET`), hit policies `FIRST|UNIQUE|COLLECT`, status `PENDING_REVIEW|APPROVED|REJECTED|RETIRED`, `profile="RULE_IR_V1"`, version int, effective dates, audit block. Depends: T-001.
  - Accept: `uv run pytest tests/ir/` — includes tests rejecting: unknown operator, depth-4 nesting, arbitrary-function payloads, missing sourceReferences on candidates.
- [ ] **T-102 — JSON Schema export.** Generator writing `docs/ir-v1.schema.json` from the models + a test that the committed file is current.
  - Accept: `uv run pytest tests/ir/test_schema_export.py`.
- [ ] **T-103 — IR fixtures.** `tests/fixtures/ir/`: the `enrollment_eligibility` example (with Korean names) + ≥4 edge cases; serialize→parse round-trip byte-stability test.
  - Accept: `uv run pytest tests/ir/test_roundtrip.py`.

### M2 — Rule Repository (storage, versioning, governance core)
*Exit: append-only versioned store with maker-checker + audit, exposed via API.*

- [ ] **T-201 — Schema & migrations.** Tables: `decisions`, `decision_versions` (append-only, full IR JSONB + version + status), `audit_log`, `actors`. Alembic migration. Depends: T-101, T-002.
  - Accept: `uv run alembic upgrade head` against compose PG + `uv run pytest tests/repository/test_schema.py`.
- [ ] **T-202 — Repository service.** Create/get/list decisions; every change = new version row (no UPDATE of IR payloads); latest-approved resolver.
  - Accept: `uv run pytest tests/repository/test_service.py` incl. immutability test (attempt in-place mutation fails).
- [ ] **T-203 — Status lifecycle + maker-checker.** `submit → approve|reject`, `approved → retire`. Approver must differ from submitter; invalid transitions raise.
  - Accept: `uv run pytest tests/repository/test_lifecycle.py` incl. self-approval rejection test.
- [ ] **T-204 — Audit trail.** Every transition/version writes who/when/action/diff-summary; queryable per decision.
  - Accept: `uv run pytest tests/repository/test_audit.py`.
- [ ] **T-205 — FastAPI routes** for all of the above (`/decisions`, `/decisions/{id}/versions`, `/decisions/{id}/submit|approve|reject`, `/decisions/{id}/audit`).
  - Accept: `uv run pytest tests/api/test_repository_api.py` (httpx AsyncClient).
- [ ] **T-206 — Structured rule diff.** Endpoint + lib: version A vs B → added/removed/changed rules & fields (not text diff).
  - Accept: `uv run pytest tests/governance/test_diff.py`.

### M3 — Source Adapters (extraction)
*Exit: fixture DB tables and fixture Java code both yield reviewed-ready candidate rules in the repository.*

- [ ] **T-301 — SourceAdapter contract + registry.** ABC per architecture §6.1 (`discover`, `extract`), plugin registry keyed by name, site-profile config model (yaml). Depends: T-101.
  - Accept: `uv run pytest tests/adapters/test_contract.py`.
- [ ] **T-302 — MCP DB connector library.** `mcp-db-connector/`: FastMCP server with tools `list_tables`, `get_table_schema`, `sample_rows`, `get_stored_proc_source`; connection info from env/config only. Reusable standalone package. Depends: T-002.
  - Accept: `cd mcp-db-connector && uv run pytest` — integration test against compose PG loaded with fixture `schema.sql`+`seed.sql`.
- [ ] **T-303 — `db-postgres` adapter.** Mapping-spec-driven ETL: yaml declares condition columns/action columns per table; each row → candidate IR rule (`confidence=1.0`, `SourceReference type=DB_TABLE`). Uses the MCP connector. Depends: T-301, T-302.
  - Accept: `uv run pytest tests/adapters/test_db_postgres.py` — fixture rate/eligibility tables produce snapshot-matched candidates (Korean values intact).
- [ ] **T-304 — Joern pipeline: locate.** Orchestrate CPG build on a target repo; seed entry points from config (class/method patterns); call-graph reachability → kept-method list. Depends: T-007.
  - Accept: `uv run pytest tests/adapters/test_joern_locate.py` — on fixture: finds `EnrollmentValidator` methods, excludes a planted unrelated class.
- [ ] **T-305 — Joern pipeline: slice.** For each kept method: decision-construct filter (if/switch/validation), backward slice per decision point → slice manifest JSON `{sliceId, file, lineStart, lineEnd, code, entryPoint}`. Oversized units split per decision point.
  - Accept: `uv run pytest tests/adapters/test_joern_slice.py` — manifest covers all ≥6 fixture decision points with correct line ranges.
- [ ] **T-306 — Tiered LLM client.** Config-driven: `bulk` + `frontier` model slots, provider-swappable (per-site policy), structured output = the candidate-IR Pydantic schema with validation-failure retry (max 3). Mock provider for tests; real call behind `BRP_LLM_LIVE=1`.
  - Accept: `uv run pytest tests/llm/` (mock-based; validates retry-on-invalid-JSON behavior).
- [ ] **T-307 — `code-java` mining.** Slice manifest → prompt (template in repo, includes IR schema + slice code + "candidate-only" framing) → candidate IR rules with `SourceReference type=JAVA_SOURCE` (exact file/lines from the slice) + model-reported confidence; near-duplicate collapse (same conditions/actions). Depends: T-305, T-306.
  - Accept: `uv run pytest tests/adapters/test_code_java.py` — with recorded mock responses: fixture yields the `UNDER_AGE` rule with correct file/line + Korean product-name rule intact; dedup test passes.
- [ ] **T-308 — Ingestion runner.** CLI `brp ingest --site <profile>`: run configured adapters → write candidates as `PENDING_REVIEW` batch; idempotent (re-run creates no duplicates). Depends: T-303, T-307, T-202.
  - Accept: `uv run pytest tests/e2e/test_ingest.py` — run twice against compose PG, second run adds 0 candidates.

### M4 — Governance & Validation
*Exit: rules can be previewed, golden-tested, reviewed, and approved end to end.*

- [ ] **T-401 — `jdm-export` + Zen preview.** IR→JDM transform (pure function) + preview service `evaluate(decisionId, inputPayload)` using `zen-engine` Python binding on latest approved (or draft) version. Depends: T-103.
  - Accept: `uv run pytest tests/governance/test_zen_preview.py` — fixture rule: age 17 → `UNDER_AGE`; age 20 → eligible.
- [ ] **T-402 — Golden-test harness.** Models + storage for cases `{decisionId, input, expectedOutput, origin}`; runner executing cases via Zen preview; seed import from fixture app's unit-test expectations.
  - Accept: `uv run pytest tests/governance/test_golden_harness.py`.
- [ ] **T-403 — Minimal governance UI.** Decision list → decision-table view/edit (ag-grid) → submit/approve buttons (two mock users to satisfy maker-checker) → audit tab. Talks to the T-205 API. *Minimal, not pretty — hardening is Phase 2.* Depends: T-205 (may run parallel to M3).
  - Accept: `pnpm test` (vitest component smoke) + `pnpm build`; manual walkthrough screenshot saved to `docs/ui-m4.png`.
- [ ] **T-404 — Preview panel.** UI form: input payload → calls preview endpoint → shows decision output; visible on the decision page.
  - Accept: vitest smoke + screenshot appended to `docs/ui-m4.png` set.

### M5 — Target Generators
*Exit: approved IR renders to deterministic, formatted, compiling Java + generated JUnit tests.*

- [ ] **T-501 — TargetGenerator contract + orchestration.** Python ABC per architecture §7.1 + registry + artifact manifest model. Depends: T-101.
  - Accept: `uv run pytest tests/generators/test_contract.py`.
- [ ] **T-502 — `codegen-cli` (JavaPoet).** Gradle module: stdin/args = IR JSON → one final class per decision (`…rules.generated` package, `@Generated` header with decision id+version, "do not edit" banner) + a `RuleFacade` interface; google-java-format applied. **Determinism test: run twice, byte-identical.** Depends: T-003, T-102.
  - Accept: `cd java-toolchain && ./gradlew :codegen-cli:test` — golden-file + determinism + Korean-string preservation tests.
- [ ] **T-503 — Generated-module packaging.** Gradle template project for generated sources; codegen output drops in and compiles standalone; lookup access behind a provided `LookupProvider` interface (no JDBC in generated code).
  - Accept: script `scripts/gen-and-compile-fixture.sh` exit 0 (generates from an approved fixture IR, compiles module).
- [ ] **T-504 — `test-generator`.** Golden cases (T-402) → JUnit 5 sources targeting the generated classes.
  - Accept: `scripts/gen-tests-fixture.sh` — generated tests compile and pass against generated fixture module.
- [ ] **T-505 — Generation orchestration.** `brp generate --decision <id> --target java` : latest **approved** version only → codegen-cli → artifact dir + manifest (inputs hash, outputs, versions). Refuses non-approved. Depends: T-502, T-203.
  - Accept: `uv run pytest tests/e2e/test_generate.py` incl. refuses-PENDING test.

### M6 — Mode-B Delivery (round-trip on the fixture)
*Exit: an approved rule edit lands in the fixture app as a gated, reviewable code change.*

- [ ] **T-601 — Branch & diff flow.** `brp deliver --site fixture`: regenerate → write into a git clone of the target repo on branch `rules/gen-<decision>-v<N>` → commit → produce diff report. Depends: T-505.
  - Accept: `uv run pytest tests/e2e/test_deliver_branch.py` (uses a temp clone of the fixture repo).
- [ ] **T-602 — Golden-test gate.** Delivery pipeline compiles the generated module + runs generated JUnit; any failure aborts before branch push and reports.
  - Accept: `uv run pytest tests/e2e/test_gate.py` — includes a negative case (intentionally broken rule → gate blocks).
- [ ] **T-603 — Integration seam cut-over.** OpenRewrite recipe (`seam-recipes`): replace the mined `EnrollmentValidator` region in the fixture app with a call to `RuleFacade`; wire generated module + a JDBC `LookupProvider` impl. Fixture's original behavior tests must still pass post-cut-over. Depends: T-503.
  - Accept: `scripts/seam-fixture.sh` exit 0 → `cd fixtures/legacy-enrollment && ./gradlew test` green on the cut-over branch.
- [ ] **T-604 — Preview↔generated consistency check.** Run all golden cases through both Zen preview and the generated code; report divergences (expected: zero on fixture; any divergence = generator bug).
  - Accept: `uv run pytest tests/e2e/test_consistency.py`.

### M7 — End-to-End PoC Demo (PRD §11)
*Exit: the customer-facing success criterion is scriptable and repeatable.*

- [ ] **T-701 — Scripted demo.** `scripts/demo-mode-b.sh` (+ `.ps1`): compose up → ingest fixture (DB + code) → approve candidates (scripted two-actor) → seam cut-over → show enrollment outcome for age 18 → edit rule `<18` → `<19` via API → approve → deliver (regen + gate) → show outcome flipped → print summary table. Depends: all M2–M6 exit criteria.
  - Accept: script exit 0; output contains `BEFORE: ELIGIBLE` / `AFTER: REJECTED(UNDER_AGE)` (age-18 case) and zero gate failures.
- [ ] **T-702 — Demo documentation.** `docs/demo.md`: prerequisites, run steps, expected output, troubleshooting; README updated.
  - Accept: a fresh-checkout dry run following only `docs/demo.md` succeeds (log it).

### M8 — Phase 2 (GATED — do not start until the human marks M7 accepted here: ☐)

- [ ] **T-801 — DMN import adapter** (decision tables → IR; restricted-FEEL subset; BPMN rejected; review queue for unmapped FEEL).
- [ ] **T-802 — Mode-A decision service** (stateless FastAPI + embedded Zen; loads latest approved JDM; publish flow).
- [ ] **T-803 — Second DBMS driver** for the MCP connector (proves pluggability).
- [ ] **T-804 — Mining-model benchmark harness** (value vs frontier tiers on real slices: rule-level precision/recall vs reviewed ground truth, cost per 1k rules). ⚠ needs customer samples + model-policy answer.
- [ ] **T-805 — Governance UI hardening** (real auth/OIDC, role model, diff UX, batch review).

---

## 4. Blocked On Customer (track here, do not silently assume)

| Item | Blocks | Status |
|---|---|---|
| Sample Java enrollment source + PostgreSQL schema (masked) | real-data validation of M3; T-804 | ⏳ requested 2026-07-02 |
| Pilot product/flow selection | Phase-1 scoping against real system | ⏳ asked in review doc Q1 |
| Approval policy (who/how many/evidence) | T-805 config; M2 defaults are placeholders | ⏳ review doc Q4 |
| Chinese-origin model policy | T-804 shortlist | ⏳ asked 2026-07-04 |
| Coding conventions sample | codegen template tuning (T-502 style pass) | ⏳ review doc Q7 |

## 5. Definition of Done (global)

Task checked ⇔ acceptance commands pass locally ⇔ CI green ⇔ no ground-rule violations ⇔ Progress Log updated. Milestone done ⇔ all its tasks checked + exit criteria demonstrably true.

## 6. Progress Log (append-only; newest last)

<!-- agent entries: YYYY-MM-DD HH:MM | T-### | done|BLOCKED|PROPOSAL | commit | one-line note -->
```
(empty)
```
