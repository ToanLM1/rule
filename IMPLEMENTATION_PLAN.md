# Implementation Plan — Business Rules Platform

> **Audience: an AI coding agent.** This file is the execution plan and progress tracker for building the platform described in `prd.md` (product) and `architecture.md` (design source of truth). The customer approved the architecture on 2026-07-04. Follow the protocol in §0 exactly. When this plan and your own judgment disagree, **this plan wins**; if the plan seems wrong, log a `PROPOSAL:` (§0.2) instead of deviating.

---

## 0. Agent Protocol

### 0.1 Required reading order
1. `AGENTS.md` (this directory) — scope boundaries.
2. `architecture.md` — full read. ADR-1..5 are binding constraints.
3. `prd.md` §5–§9 — functional requirements.
4. This file, top to bottom.

### 0.2 How to work
1. Complete the **E-tasks (§3.0)** first if any are unchecked.
2. Then pick the **first unchecked T-task, in numeric order**, whose `Depends` are all checked. Do not skip ahead across milestones. Exception: T-403/T-404 (UI) may be done any time after M2 is complete.
3. A task is **done only when every `Accept` command passes**. Run them literally — do not reason your way past them. If an Accept command cannot run (missing tool), the task is BLOCKED, not done.
4. Mark done: change `- [ ]` to `- [x]` and append ` ✅ YYYY-MM-DD <short-commit-hash>` to the task's title line. Then append one line to the Progress Log (§7).
5. One task per commit where practical. Commit message format: `feat(platform): T-303 db-postgres adapter` (use `fix`/`test`/`chore` when more accurate). Branch: work directly on `main` unless a human says otherwise.
6. **BLOCKED:** if stuck > ~30 minutes on environment/tooling, or a requirement is genuinely ambiguous: append `BLOCKED: T-### | what you tried | what is needed` to the Progress Log, leave the box unchecked, move to the next unblocked task.
7. **PROPOSAL:** to change anything in `architecture.md`/`prd.md`/this plan's design, append `PROPOSAL: <what & why>` to the Progress Log and continue without the change. A human reviews proposals.
8. Never delete or rewrite existing Progress Log lines. Append only.

### 0.3 Ground rules (violating any of these = task not done, even with green tests)
- **IR is the only system of record** (ADR-1). JDM, DMN, generated Java are derived artifacts — never primary storage.
- **Deterministic generation** (ADR-4): same approved IR in → byte-identical files out. LLM output is *candidate rules only* (`status=PENDING_REVIEW`); LLM text never enters generated artifacts, templates, or production code paths.
- Every extracted candidate has `sourceReferences` (exact file+lines, or table name) and `confidence`. Nothing is auto-approved. Approver ≠ submitter (maker-checker), enforced in code.
- Mode-B golden tests execute the **generated Java** (compile + run). Zen preview is advisory (architecture §9).
- **Korean text survives byte-exact** end to end. Fixtures deliberately contain Korean strings; tests must assert on them. Set `PYTHONUTF8=1` and `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8` (E-001).
- Nothing site-specific in core code. Site differences live in `config/sites/*.yaml` and adapters only.
- Secrets/connection strings via environment or gitignored `.env` only. Never hardcode, never log, never commit.
- All new code: English identifiers/comments; type hints everywhere (Python), `from __future__ import annotations` not required (3.12); `ruff` clean; tests colocated under `tests/` mirroring `src/` paths.

### 0.4 Environment assumptions
- **Reuse-first on AWS.** The primary dev/integration host is the **existing project EC2 instance** (the one already running the knowledge-assistant backend) — it already has Python and other tooling installed for that project. **Verify what exists before installing anything** (E-tasks start with checks, not installs). The database is **AWS RDS PostgreSQL**, not a local install.
- **Shared-host etiquette (hard rules):** the EC2 also serves the knowledge-assistant (hybrid-RAG) deployment. Do NOT: upgrade/replace system Python or global packages, stop/restart its services, edit its env files, or bind its ports. All BRP Python work lives in this repo's own uv-managed venvs; BRP API binds **port 8100** (assume 8000 is taken). If a needed system-level change could affect the other project, log `BLOCKED:`/`PROPOSAL:` instead of doing it.
- **Local Windows dev is the secondary path** (bare-metal per §2.1 winget column; Docker optional fallback). Git Bash runs `.sh`; every script in `scripts/` must have a `.ps1` twin so both environments work.
- Run Python commands from `platform/` (or `mcp-db-connector/`), Gradle from `java-toolchain/` or `fixtures/legacy-enrollment/`, pnpm from `ui/`, unless a task says otherwise.

---

## 1. Context Snapshot (self-contained)

We build a **rule-governance + source-generation platform** for finance/insurance enrollment logic (`가입 Rule`):

- **Initial load (one-time per site):** extract rules from legacy assets — PostgreSQL config tables (ETL, trust=1.0), Java source (Joern locates & slices decision logic → LLM drafts candidate rules), manuals, DMN — into a governed **Rule Repository** storing the **Canonical Rule IR v1**.
- **Operation (ongoing):** business users edit rules; after maker-checker approval, delivery happens per site:
  - **Mode B (Phase 1, this plan's target):** deterministically regenerate a Java rule module → compile → generated golden tests pass → branch/PR into the target repo.
  - **Mode A (Phase 2, gated):** publish approved rules (IR→JDM) to an embedded GoRules Zen decision service.

**Canonical Rule IR v1 example** (full spec: `architecture.md` §5 and `docs/ir-v1.schema.json` after T-102):

```json
{
  "decisionId": "enrollment_eligibility",
  "decisionName": "가입 자격 판정",
  "profile": "RULE_IR_V1",
  "version": 1,
  "status": "PENDING_REVIEW",
  "product": "CANCER_BASIC",
  "effective": { "from": "2026-08-01", "to": null },
  "hitPolicy": "FIRST",
  "inputs":  [ { "name": "customer.age", "type": "number" },
               { "name": "product.code", "type": "string" } ],
  "outputs": [ { "name": "eligible", "type": "boolean" },
               { "name": "reasonCode", "type": "string" } ],
  "lookups": [ { "name": "rate_table", "ref": "lookup://rate_table" } ],
  "rules": [ {
      "ruleId": "R001",
      "when": [ { "field": "customer.age", "operator": "<", "value": 18 } ],
      "then": [ { "field": "eligible", "value": false },
                { "field": "reasonCode", "value": "UNDER_AGE" } ],
      "sourceReferences": [ { "type": "JAVA_SOURCE", "repository": "legacy-enrollment",
        "file": "src/main/java/legacy/EnrollmentValidator.java", "lineStart": 24, "lineEnd": 29 } ],
      "confidence": 0.82
  } ]
}
```

Restricted v1 profile: operators `=, !=, >, >=, <, <=, IN, NOT_IN, BETWEEN, EXISTS`; AND/OR groups (max depth 3); hit policies `FIRST | UNIQUE | COLLECT`; explicit `lookup://` refs only; **no** FEEL, no side effects, no function calls. Anything inexpressible → review-queue item with the raw fragment attached, never silently dropped.

**Customer samples have NOT arrived.** M0 builds a synthetic legacy fixture app; all later tasks develop against it. Real samples slot in later as a second site profile — zero design change.

---

## 2. Conventions & Configuration

### 2.1 Shared AWS resources (reuse — record actual values at E-001/E-002, do not guess)

| Resource | Value (verified 2026-07-04 via AWS CLI) | Notes |
|---|---|---|
| EC2 dev host | `i-07af453b12aa01ff2` · EIP `13.251.6.169` · ap-southeast-1a · **t3.small (2 vCPU / 2 GB)** · 32 GB gp3 | runs `knowledge-api` + `knowledge-api-worker` (systemd, port 8080); EIP survives stop/start resize. ⚠ 2 GB RAM is too small for Joern — see resize note in E-001. SSH user: `_______` (fill at E-001) |
| Existing Python on EC2 | version found: `_______` (fill at E-001) | the knowledge-api already uses uv there; reuse if ≥3.12 |
| RDS PostgreSQL | `csax-rag-utils-ap-se1.cf2as4mo2yxu.ap-southeast-1.rds.amazonaws.com:5432` · **postgres 17.9** · db.t4g.small · 20 GB · publicly accessible · SG `sg-083fc997dd34f03e6` | **reuse this instance** — create a separate `brp` database + `brp` role (E-002); do NOT touch the RAG project's databases |
| BRP API port on EC2 | **8100** | 8080 is taken by knowledge-api |

### 2.1b Version pins & install paths

| Tool | Version | EC2 (Amazon Linux/Ubuntu — check first, install only if missing) | Windows local (secondary) |
|---|---|---|---|
| Python | 3.12.x | reuse existing; else `uv python install 3.12` (user-local) | `winget install Python.Python.3.12` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (user-local) | `winget install astral-sh.uv` |
| JDK | Temurin/Corretto 17 | check `java -version`; else `sudo dnf install java-17-amazon-corretto` (or apt temurin-17-jdk) | `winget install EclipseAdoptium.Temurin.17.JDK` |
| Gradle | 8.7 via wrapper | committed `gradlew` — never a global install | same |
| Node | 22 LTS | check `node -v`; else via nvm (user-local) | `winget install OpenJS.NodeJS.LTS` |
| pnpm | 9.x | `corepack enable && corepack prepare pnpm@9 --activate` | same |
| PostgreSQL | 16+ (the shared RDS runs **17.9** — target that; keep SQL/migrations compatible with 16) | **AWS RDS `csax-rag-utils-ap-se1`** (E-002) — no server install anywhere | connect to the same RDS; `psql` client tools only |
| Joern | pin latest 4.x — **record: `_______`** | release zip → `~/tools/joern` (Linux is Joern's native platform — prefer running mining on EC2) | zip → `C:\tools\joern`; fallback Docker → WSL2 |
| zen-engine (PyPI) | pin at T-401 — record: `_______` | `uv add zen-engine` | same |

### 2.2 Python dependencies (platform/pyproject.toml)
`fastapi`, `uvicorn[standard]`, `pydantic>=2.7`, `sqlalchemy>=2.0`, `alembic`, `psycopg[binary]`, `pyyaml`, `httpx`, `typer` (CLI), `structlog`; dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`. Pin exact versions in the lockfile (uv does this automatically); do not add dependencies beyond these without a `PROPOSAL:`.

### 2.3 Environment variables (`.env.example`, committed; `.env` gitignored)

```
# RDS is the primary DB (endpoint from §2.1); localhost only for offline local dev
BRP_DB_URL=postgresql+psycopg://brp:<password>@<rds-endpoint>:5432/brp
BRP_API_PORT=8100
BRP_LLM_PROVIDER=mock            # mock | anthropic | openai_compat (covers DeepSeek/Kimi/GLM/Qwen endpoints)
BRP_LLM_BULK_MODEL=
BRP_LLM_FRONTIER_MODEL=
BRP_LLM_API_KEY=
BRP_LLM_BASE_URL=                # for openai_compat providers
BRP_LLM_LIVE=0                   # 1 enables live-API tests
JOERN_HOME=C:\tools\joern
PYTHONUTF8=1
```

### 2.4 Config file shapes

**Site profile** — `config/sites/fixture.yaml`:
```yaml
site: fixture
delivery_mode: B                 # A | B
language: java
db:
  kind: postgres
  conn_env: BRP_DB_URL           # name of env var holding the connection string
adapters: [db-postgres, code-java]
code:
  repo_path: ../fixtures/legacy-enrollment
  entry_points:                  # Joern seed patterns
    - class: "legacy.EnrollmentValidator"
      method: "evaluate"
mapping_spec: config/mappings/fixture-tables.yaml
```

**Table mapping spec** — `config/mappings/fixture-tables.yaml`:
```yaml
tables:
  - table: region_eligibility
    decision_key: region_eligibility
    condition_columns: [region_code]
    action_columns:   [eligible]
  - table: rate_table
    decision_key: premium_rate
    condition_columns: [product_code, age_band, smoker]
    action_columns:   [base_rate, loading_pct]
```

### 2.5 API surface (built in M2/M4; keep paths exactly)

| Method & path | Purpose |
|---|---|
| `POST /decisions` | create decision (first draft version, PENDING_REVIEW) |
| `GET /decisions` · `GET /decisions/{key}` | list / fetch (latest version + status) |
| `POST /decisions/{key}/versions` | new draft version (body = full IR) |
| `POST /decisions/{key}/versions/{v}/submit` | submit for approval (actor header `X-BRP-Actor`) |
| `POST /decisions/{key}/versions/{v}/approve` · `/reject` | maker-checker transition (403 if actor == submitter) |
| `GET /decisions/{key}/audit` | audit trail |
| `GET /decisions/{key}/diff?from=&to=` | structured rule diff |
| `POST /preview/{key}` | body = input payload → decision output via Zen |
| `POST /golden/{key}/run` | run golden cases → pass/fail report |

Actor identity for Phase 1 = `X-BRP-Actor: <name>` header (real auth is Phase 2 / T-805). Reject requests without it (400).

### 2.6 Windows pitfalls (read once, save pain)
- Always set `PYTHONUTF8=1` (Korean text in tests will corrupt otherwise). Terminal output may still render mojibake — **trust file contents/pytest assertions, not terminal rendering** (see root `CLAUDE.md` memory note).
- Write files as UTF-8 **without BOM**; `.gitattributes`: `*.java text working-tree-encoding=UTF-8`, `* text=auto`.
- Scripts: every `scripts/x.sh` needs `scripts/x.ps1`. `.sh` runs under Git Bash.
- `psycopg[binary]` avoids needing a C compiler.
- Gradle on Windows: use `gradlew.bat` from PowerShell, `./gradlew` from Git Bash — both committed.
- Joern's launcher scripts are Unix-flavored; on native Windows run `joern.bat` if present, else use the Docker/WSL fallback and set `JOERN_MODE=docker` consumed by our wrapper (T-304 builds the wrapper with both modes).

---

## 3. Milestones & Tasks

Format per task — **Do** (steps), **Files** (what to create/touch), **Accept** (commands that must pass; run from the stated directory), **Depends**.

### 3.0 E — Environment (reuse-first on the existing EC2; install only what's missing)

- [ ] **E-001 — Inventory & base tools on the EC2.**
  - ⚠ **RAM note:** the EC2 is a t3.small (2 GB). BRP API + existing knowledge-api coexist fine, but **Joern mining will not fit** — before running any Joern task (E-003, T-007, T-304+) the instance must be resized (recommended **t3.large**, 8 GB; EIP is retained across stop/start; coordinate the few minutes of knowledge-api downtime with the team) or mining must run on a separate machine (local Windows box / ephemeral EC2). A human decides the resize — raise `BLOCKED:` if you reach a Joern task while still on 2 GB.
  - Do: on the existing EC2 (§2.1): run `python3 --version && java -version && node -v && git --version && psql --version` and **record every found version in the §2.1 table**. Install only the gaps, per the §2.1b EC2 column, always user-local (uv-managed Python, nvm Node) — **never upgrade or replace anything the knowledge-assistant uses** (§0.4 etiquette). Add `PYTHONUTF8=1` and `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8` to the BRP shell profile (or `.env`), not to system-wide config. If also working locally on Windows, repeat with the Windows column.
  - Accept: `uv --version` · `uv run python --version` prints 3.12.x · `java -version` prints 17.x · `node -v` ≥ v20 · `pnpm -v` prints 9.x — all on the host you will actually build on.
- [ ] **E-002 — RDS PostgreSQL (reuse `csax-rag-utils-ap-se1`).**
  - Do: **no new RDS instance.** On the existing instance (endpoint in §2.1, postgres 17.9): create role `brp` (strong password → `.env`, never committed) and database `brp` owned by it: `psql "<admin-url>" -c "CREATE ROLE brp LOGIN PASSWORD '<pw>'; CREATE DATABASE brp OWNER brp;"`. Do NOT touch any existing database on that instance. Verify the SG (`sg-083fc997dd34f03e6`) already allows your client (it is publicly accessible; the EC2 path should already work). Keep an eye on shared 20 GB storage — if `brp` data grows past ~5 GB, raise a `PROPOSAL:` to split to a dedicated instance.
  - Accept: `psql "$BRP_DB_URL" -c "select version();"` exit 0, prints PostgreSQL 17.x.
- [ ] **E-003 — Joern.**
  - Do: prefer the **EC2 (Linux)** — Joern's native platform: download the pinned 4.x release, extract to `~/tools/joern`, set `JOERN_HOME`; record the version in §2.1b. (Windows local: zip to `C:\tools\joern`; if the native launcher misbehaves → Docker image → WSL2; set `JOERN_MODE` accordingly in `.env`.)
  - Accept: `"$JOERN_HOME"/joern --version` (or the docker equivalent) prints the pinned version.

### M0 — Scaffold & Foundations
*Exit: all builds green; fixture app tests pass; Joern parses the fixture.*

- [ ] **T-001 — Monorepo scaffold + Python project.**
  - Do: create the §"Target Repository Layout" of the previous section — see `architecture.md` §13 for stack rationale — exactly as below:
    ```
    platform/  java-toolchain/  mcp-db-connector/  ui/  fixtures/legacy-enrollment/
    docker/  docs/  scripts/  config/sites/  config/mappings/  .github/workflows/
    ```
    `platform/`: `uv init --package`, package name `brp`, deps per §2.2, `ruff.toml` (line-length 100), `pytest.ini` (testpaths=tests, asyncio_mode=auto). Root `README.md` linking prd/architecture/this plan. `.gitattributes` per §2.6. Commit `.env.example` per §2.3.
  - Files: as above + `platform/src/brp/__init__.py`.
  - Accept (from `platform/`): `uv run ruff check .` exit 0 · `uv run pytest` exit 0 (0 collected is fine).
- [ ] **T-002 — DB bootstrap scripts.**
  - Do: `scripts/check-pg.sh|.ps1` = connect using `BRP_DB_URL` (normally the RDS endpoint from E-002), `select 1`, exit code. `scripts/db-load-fixture.sh|.ps1` = apply `fixtures/legacy-enrollment/db/schema.sql` + `seed.sql` to the `brp` DB. Also add `docker/docker-compose.yml` (postgres:16 with healthcheck) as the *offline fallback only* — CI also uses a containerized PG service, dev uses RDS.
  - Accept: `scripts/check-pg.sh` exit 0 against the RDS endpoint.
  - Depends: E-002.
- [ ] **T-003 — Java toolchain scaffold.**
  - Do: `java-toolchain/`: Gradle 8.7 wrapper committed, Java 17 toolchain block, modules `codegen-cli` (application plugin, mainClass `brp.codegen.Main`) and `seam-recipes` (java-library); Spotless plugin with googleJavaFormat; an empty smoke test each.
  - Accept (from `java-toolchain/`): `./gradlew build` exit 0.
  - Depends: E-001.
- [ ] **T-004 — UI scaffold.**
  - Do: `ui/`: Vite + Vue 3 + TS + Pinia + vue-router; deps `ag-grid-community ag-grid-vue3 monaco-editor`; placeholder `DecisionsPage.vue`; vitest configured.
  - Accept (from `ui/`): `pnpm install && pnpm build && pnpm test -- --run` exit 0.
  - Depends: E-001.
- [ ] **T-005 — Synthetic legacy fixture app.** *(the stand-in for the customer's system — build it exactly as specced)*
  - Do: `fixtures/legacy-enrollment/` = standalone Gradle Java 17 app:
    - `legacy.model.EnrollmentRequest` fields: `int age; String productCode; boolean smoker; String regionCode; int occupationClass;`
    - `legacy.model.EnrollmentResult` fields: `boolean eligible; String reasonCode; int premiumLoadingPct; List<String> requiredDocs;`
    - `legacy.EnrollmentValidator#evaluate(EnrollmentRequest, Connection)` implementing **exactly these decision points** (keep them as plain if/switch — this is deliberately "bad" legacy style):
      1. `age < 18` → reject `UNDER_AGE`
      2. `"CANCER_BASIC".equals(productCode) && age > 65` → reject `OVER_AGE_LIMIT`
      3. `smoker && productCode.startsWith("CANCER")` → `premiumLoadingPct += 20`
      4. `regionCode` not present with `eligible=true` in DB table `region_eligibility` → reject `REGION_NOT_COVERED` (JDBC lookup)
      5. `switch (occupationClass)`: class 4 or 5 → add `"DOC_HEALTH_CHECK"` to `requiredDocs`
      6. nested: `age between 60 and 65 && "CANCER_BASIC".equals(productCode)` → `premiumLoadingPct += 30` **and** add `"DOC_HEALTH_CHECK"`
    - `db/schema.sql` + `db/seed.sql`: `product_master(product_code pk, product_name_kr, min_age, max_age)` seeded with `('CANCER_BASIC','암보험 기본형',18,65)` and `('SAVINGS_PLUS','저축보험 플러스',19,70)`; `rate_table(product_code, age_band, smoker, base_rate, loading_pct)` ≥6 rows; `region_eligibility(region_code pk, region_name_kr, eligible)` ≥5 rows incl. `('JEJU','제주',false)`; `occupation_class(class_code pk, name_kr, required_doc)`.
    - JUnit 5 tests pinning current behavior for ≥10 input combinations (these are the future golden seeds), using an in-memory H2 in PostgreSQL mode OR the real local PG via env — pick H2 for test isolation, but keep SQL ANSI so both work.
  - Accept (from `fixtures/legacy-enrollment/`): `./gradlew test` exit 0.
  - Depends: E-001.
- [ ] **T-006 — CI.**
  - Do: `.github/workflows/ci.yml`: jobs = platform (uv sync, ruff, pytest with a postgres service container), java-toolchain (`./gradlew build`), fixture (`./gradlew test`), ui (pnpm build+test). Cache uv/gradle/pnpm.
  - Accept: push → CI green; record the run URL in the Progress Log line.
  - Depends: T-001..T-005.
- [ ] **T-007 — Joern smoke.**
  - Do: `scripts/joern-smoke.sh|.ps1`: build CPG for the fixture app, run a CPGQL query counting methods, assert `EnrollmentValidator.evaluate` exists. Must work in both `JOERN_MODE=native|docker`.
  - Accept: `scripts/joern-smoke.sh` exit 0 and prints a method count > 0.
  - Depends: E-003, T-005.

### M1 — Canonical Rule IR v1
*Exit: IR models enforce the restricted profile; JSON Schema published; fixtures round-trip byte-stably.*

- [ ] **T-101 — IR Pydantic models.**
  - Do: `src/brp/ir/models.py` implementing §1's shape: enums for operators/hit-policies/status/source-ref-types; `ConditionGroup` with `all|any` recursion capped at depth 3 (validator); `Decision.profile` literal `"RULE_IR_V1"`; candidates (`PENDING_REVIEW`) must have ≥1 sourceReference (validator); values are JSON scalars or lists only (no expressions/callables).
  - Files: `src/brp/ir/models.py`, `tests/ir/test_models.py`.
  - Accept (from `platform/`): `uv run pytest tests/ir/test_models.py` — must include tests rejecting: unknown operator, depth-4 nesting, candidate without sourceReferences, non-scalar action value.
  - Depends: T-001.
- [ ] **T-102 — JSON Schema export.**
  - Do: `src/brp/ir/schema_export.py` + CLI `uv run python -m brp.ir.schema_export` writing `docs/ir-v1.schema.json`; test asserts committed file == freshly generated.
  - Accept: `uv run pytest tests/ir/test_schema_export.py`.
  - Depends: T-101.
- [ ] **T-103 — IR fixtures + round-trip.**
  - Do: `tests/fixtures/ir/*.json`: the §1 example plus ≥4 edge cases (COLLECT policy; BETWEEN; NOT_IN with Korean values `["제주","울릉"]`; nested groups depth 3; effective-dated version). Round-trip test: parse → dump → parse → equal, and dumped bytes stable across two dumps.
  - Accept: `uv run pytest tests/ir/test_roundtrip.py`.
  - Depends: T-101.

### M2 — Rule Repository
*Exit: append-only versioned store with maker-checker + audit, exposed via the §2.5 API.*

- [ ] **T-201 — Schema & migrations.**
  - Do: SQLAlchemy models + Alembic migration for:
    ```sql
    decisions(id uuid pk, decision_key text unique not null, name text, product text,
              created_by text, created_at timestamptz)
    decision_versions(id uuid pk, decision_id fk, version int not null, ir jsonb not null,
              status text not null, submitted_by text, approved_by text,
              created_at timestamptz, unique(decision_id, version))
    audit_log(id bigserial pk, decision_id fk, version int, actor text not null,
              action text not null, detail jsonb, at timestamptz default now())
    ```
    No UPDATE path for `decision_versions.ir` — enforce via service layer + a DB trigger raising on UPDATE of `ir`.
  - Accept: `uv run alembic upgrade head` exit 0 against local PG, then `uv run pytest tests/repository/test_schema.py` (asserts trigger blocks IR update).
  - Depends: T-101, T-002.
- [ ] **T-202 — Repository service.**
  - Do: `src/brp/repository/service.py`: `create_decision(ir, actor)`, `add_version(key, ir, actor)`, `get(key)`, `get_version(key, v)`, `list()`, `latest_approved(key)`. Every write inserts a new version row.
  - Accept: `uv run pytest tests/repository/test_service.py`.
  - Depends: T-201.
- [ ] **T-203 — Lifecycle + maker-checker.**
  - Do: transitions `PENDING_REVIEW→(submit)→SUBMITTED→(approve|reject)→APPROVED|REJECTED`, `APPROVED→(retire)→RETIRED`; approve/reject require actor ≠ submitted_by (raise `SelfApprovalError`); illegal transitions raise.
  - Accept: `uv run pytest tests/repository/test_lifecycle.py` incl. explicit self-approval-rejected test.
  - Depends: T-202.
- [ ] **T-204 — Audit trail.**
  - Do: every version insert + transition writes `audit_log` (actor, action, detail = {from,to,version,summary}); `get_audit(key)`.
  - Accept: `uv run pytest tests/repository/test_audit.py`.
  - Depends: T-203.
- [ ] **T-205 — FastAPI routes** per §2.5 (repository subset).
  - Do: `src/brp/api/app.py` + routers; `X-BRP-Actor` header required (400 otherwise); errors → RFC7807-ish JSON.
  - Accept: `uv run pytest tests/api/test_repository_api.py` (httpx ASGI client; covers 400-no-actor, 403-self-approve).
  - Depends: T-203, T-204.
- [ ] **T-206 — Structured diff.**
  - Do: `src/brp/governance/diff.py`: version A vs B → `{added:[ruleId], removed:[ruleId], changed:[{ruleId, field_changes:[...]}]}` (semantic, not text). Route `GET /decisions/{key}/diff`.
  - Accept: `uv run pytest tests/governance/test_diff.py`.
  - Depends: T-202.

### M3 — Source Adapters
*Exit: fixture DB tables and fixture Java code both land as candidate rules in the repository, idempotently.*

- [ ] **T-301 — SourceAdapter contract + site profiles.**
  - Do: `src/brp/adapters/base.py`: `class SourceAdapter(ABC)` with `discover(site: SiteProfile) -> list[Source]` and `extract(source: Source) -> list[Decision]` (candidates); registry `@register_adapter("name")`; `SiteProfile` Pydantic model loading §2.4 yaml.
  - Accept: `uv run pytest tests/adapters/test_contract.py` (registry resolves; fixture.yaml parses).
  - Depends: T-101.
- [ ] **T-302 — MCP DB connector library.** *(standalone reusable asset — own package, own tests)*
  - Do: `mcp-db-connector/` (uv package `brp-mcp-db`): FastMCP server exposing `list_tables()`, `get_table_schema(table)`, `sample_rows(table, limit<=50)`, `get_stored_proc_source(name)`; connection from env var named in config; read-only (SET default_transaction_read_only); no site specifics.
  - Accept (from `mcp-db-connector/`): `uv run pytest` — integration tests against local PG loaded via `scripts/db-load-fixture.sh`.
  - Depends: T-002.
- [ ] **T-303 — `db-postgres` adapter.**
  - Do: mapping-spec-driven ETL (§2.4 mapping yaml): each mapped table row → one candidate rule (conditions from condition_columns, actions from action_columns, `confidence=1.0`, `SourceReference{type=DB_TABLE, file=<table>, lineStart=<row pk repr>}`), one Decision per `decision_key`. Uses the MCP connector as its DB access.
  - Accept: `uv run pytest tests/adapters/test_db_postgres.py` — snapshot test: fixture `region_eligibility` + `rate_table` → expected candidate JSON (Korean values byte-equal).
  - Depends: T-301, T-302.
- [ ] **T-304 — Joern locate.**
  - Do: `src/brp/adapters/code_java/joern.py`: wrapper honoring `JOERN_MODE=native|docker`; build CPG for `site.code.repo_path`; seed from `site.code.entry_points`; call-graph reachability → `list[MethodRef{class, method, file, lineStart, lineEnd}]`.
  - Accept: `uv run pytest tests/adapters/test_joern_locate.py` — finds `EnrollmentValidator.evaluate` + its private helpers; excludes a planted `legacy.UnrelatedUtil` class (add it to the fixture in this task if missing).
  - Depends: T-007, T-301.
- [ ] **T-305 — Joern slice.**
  - Do: within kept methods: identify decision constructs (if/switch/ternary + JDBC-lookup calls); backward-slice each into `Slice{sliceId, file, lineStart, lineEnd, code, entryPoint, kind}`; write `slice-manifest.json`; split oversized methods per decision point (max slice 120 lines).
  - Accept: `uv run pytest tests/adapters/test_joern_slice.py` — manifest covers all 6 specced fixture decision points; line ranges match the fixture source.
  - Depends: T-304.
- [ ] **T-306 — Tiered LLM client.**
  - Do: `src/brp/llm/client.py`: providers `mock` (fixture-replay), `anthropic`, `openai_compat` (base_url — covers DeepSeek/Kimi/GLM/Qwen endpoints); tiers `bulk`/`frontier` from env (§2.3); `extract_candidates(slice, schema) -> list[Decision]` enforcing structured output by validating against the candidate-IR schema with ≤3 retries (re-prompt with validation errors); token/cost counters logged.
  - Accept: `uv run pytest tests/llm/` — mock provider: happy path, invalid-JSON-then-retry path, gives-up-after-3 path. Live smoke exists but auto-skips unless `BRP_LLM_LIVE=1`.
  - Depends: T-101.
- [ ] **T-307 — `code-java` mining.**
  - Do: prompt template at `src/brp/adapters/code_java/prompts/mine_slice.md` (contains: role, IR schema, slice code+file+lines, "output candidate rules only; if the logic cannot be expressed in the restricted profile, return it in `unmappable` with the raw fragment"); pipeline slice→prompt→client(bulk tier)→candidates with `SourceReference{JAVA_SOURCE, file, lines from slice}`; `unmappable` items become review-queue records; near-dup collapse (identical normalized conditions+actions).
  - Accept: `uv run pytest tests/adapters/test_code_java.py` — with recorded mock responses: fixture yields ≥6 candidates incl. `UNDER_AGE` (correct file/lines) and the Korean product-name value intact; dedup case passes; unmappable case lands in review queue.
  - Depends: T-305, T-306.
- [ ] **T-308 — Ingestion runner.**
  - Do: Typer CLI `brp ingest --site config/sites/fixture.yaml`: run site adapters, write candidates via repository service as PENDING_REVIEW; idempotency = skip when an identical (decision_key, normalized-IR-hash) candidate already exists; summary table printed.
  - Accept: `uv run pytest tests/e2e/test_ingest.py` — run twice: second run inserts 0; counts match expectations.
  - Depends: T-303, T-307, T-205.

### M4 — Governance & Validation

- [ ] **T-401 — jdm-export + Zen preview.**
  - Do: `src/brp/generators/jdm_export.py` (pure IR→JDM dict); `src/brp/governance/preview.py`: `evaluate(key, payload, version=None)` via `zen-engine`; route `POST /preview/{key}`; lookups resolved from a `LookupResolver` reading the fixture tables.
  - Accept: `uv run pytest tests/governance/test_zen_preview.py` — age 17 → `UNDER_AGE`; age 20 non-smoker eligible; smoker loading case.
  - Depends: T-103, T-205. Record zen-engine pin in §2.1.
- [ ] **T-402 — Golden-test harness.**
  - Do: models+tables `golden_cases(decision_key, input jsonb, expected jsonb, origin)`; importer seeding cases from the fixture app's JUnit expectations (T-005's ≥10 combos); runner via preview; route `POST /golden/{key}/run` → `{passed, failed:[{case, got, expected}]}`.
  - Accept: `uv run pytest tests/governance/test_golden_harness.py`.
  - Depends: T-401.
- [ ] **T-403 — Minimal governance UI.** *(may run any time after M2)*
  - Do: pages: decision list → detail (ag-grid decision table render/edit of `rules[]`), submit/approve buttons with an actor picker (two hardcoded actors to satisfy maker-checker), audit tab, diff view (from T-206). API base from env. Minimal styling — hardening is T-805.
  - Accept (from `ui/`): `pnpm test -- --run` component smokes + `pnpm build`; save `docs/ui-m4-list.png`, `docs/ui-m4-detail.png` screenshots.
  - Depends: T-205, T-206.
- [ ] **T-404 — Preview panel in UI.**
  - Do: on decision detail: JSON input form (monaco) → `POST /preview/{key}` → rendered output; a "run golden" button showing the T-402 report.
  - Accept: vitest smoke; screenshot `docs/ui-m4-preview.png`.
  - Depends: T-403, T-402.

### M5 — Target Generators

- [ ] **T-501 — TargetGenerator contract + orchestration model.**
  - Do: `src/brp/generators/base.py`: `supports(profile, target) -> bool`, `generate(decisions, target) -> GeneratedArtifact{files, manifest}`; manifest = inputs hash (canonical IR bytes), generator version, outputs+hashes.
  - Accept: `uv run pytest tests/generators/test_contract.py`.
  - Depends: T-101.
- [ ] **T-502 — codegen-cli (JavaPoet).**
  - Do (in `java-toolchain/codegen-cli`): CLI `java -jar codegen-cli.jar --ir <file.json> --out <dir>`:
    - per decision → `brp.rules.generated.<PascalCase(decisionId)>Rules` final class, single public method `evaluate(<DecisionId>Input in, LookupProvider lookups) -> <DecisionId>Output`; input/output records generated from IR inputs/outputs; hit policies: FIRST = first match returns; UNIQUE = evaluate all, throw on >1 match; COLLECT = aggregate outputs list.
    - file header: `// GENERATED — Business Rules Platform · decision <id> · v<version>` + `@Generated("brp")` + "do not edit" banner; google-java-format applied in-process.
    - **Determinism:** identical IR file → byte-identical output (test runs generator twice, `diff -r` empty). Korean strings escaped correctly and asserted.
  - Accept (from `java-toolchain/`): `./gradlew :codegen-cli:test` (golden-file tests + determinism + Korean preservation + all three hit policies).
  - Depends: T-003, T-102.
- [ ] **T-503 — Generated-module packaging + LookupProvider.**
  - Do: `java-toolchain/generated-module-template/` Gradle template; `LookupProvider` interface (`lookup(name, key) -> Map<String,Object>`) lives in a tiny published `brp-rules-runtime` module; codegen output compiles against it; `scripts/gen-and-compile-fixture.sh|.ps1` = export an approved fixture IR → run codegen-cli → compile the module.
  - Accept: `scripts/gen-and-compile-fixture.sh` exit 0.
  - Depends: T-502.
- [ ] **T-504 — test-generator.**
  - Do: golden cases (T-402) → JUnit 5 source per decision (`<DecisionId>RulesGoldenTest`) exercising the **generated** class with a stub LookupProvider seeded from fixture tables; part of codegen-cli (`--emit-tests`).
  - Accept: `scripts/gen-tests-fixture.sh` exit 0 — generated tests compile and pass.
  - Depends: T-503, T-402.
- [ ] **T-505 — Generation orchestration.**
  - Do: Typer CLI `brp generate --site <yaml> --decision <key>`: fetch **latest APPROVED** (refuse otherwise, exit 2), write IR temp file, invoke codegen-cli (with `--emit-tests`), collect artifact + manifest into `out/generated/<key>/v<N>/`.
  - Accept: `uv run pytest tests/e2e/test_generate.py` incl. refuses-PENDING (exit 2) test.
  - Depends: T-502, T-203.

### M6 — Mode-B Delivery (round-trip on the fixture)

- [ ] **T-601 — Branch & diff flow.**
  - Do: `brp deliver --site <yaml> --decision <key>`: clone/refresh target repo working copy → branch `rules/gen-<key>-v<N>` → copy generated module + tests into agreed paths → commit with manifest in message → emit `diff-report.md` (files + semantic rule diff from T-206).
  - Accept: `uv run pytest tests/e2e/test_deliver_branch.py` (temp clone of fixture repo; asserts branch, commit, report).
  - Depends: T-505.
- [ ] **T-602 — Golden-test gate.**
  - Do: deliver pipeline step: compile generated module + run generated JUnit **before** committing; on failure: no branch, non-zero exit, failure report.
  - Accept: `uv run pytest tests/e2e/test_gate.py` — includes negative case (corrupt one expected output → gate blocks, no branch created).
  - Depends: T-601, T-504.
- [ ] **T-603 — Integration seam cut-over.**
  - Do (in `java-toolchain/seam-recipes`): OpenRewrite recipe replacing the 6 mined regions in `EnrollmentValidator.evaluate` with delegation to `EnrollmentEligibilityRules` (+ premium/docs decisions as designed in the IR set) behind a small hand-written facade + JDBC LookupProvider impl; applied by `scripts/seam-fixture.sh|.ps1` on a branch of the fixture repo.
  - Accept: `scripts/seam-fixture.sh` exit 0, then (from cut-over fixture branch) `./gradlew test` green — original behavior tests pass against the generated module.
  - Depends: T-503.
- [ ] **T-604 — Preview↔generated consistency check.**
  - Do: `brp check-consistency --site <yaml>`: run every golden case through Zen preview AND the generated Java (via a small JUnit-console or CLI runner); diff outcomes; nonzero exit on divergence.
  - Accept: `uv run pytest tests/e2e/test_consistency.py` — fixture: zero divergences; planted-divergence test detects it.
  - Depends: T-602, T-401.

### M7 — End-to-End PoC Demo (PRD §11 success criterion)

- [ ] **T-701 — Scripted demo.**
  - Do: `scripts/demo-mode-b.sh|.ps1`: (1) load fixture DB; (2) `brp ingest`; (3) scripted two-actor approve-all; (4) seam cut-over; (5) print outcome for `{age:18, product:CANCER_BASIC, region:SEOUL, class:1}` → ELIGIBLE; (6) edit R001 `< 18` → `< 19` via API as actor A, approve as actor B; (7) `brp deliver` (gate runs); (8) print outcome again → REJECTED(UNDER_AGE); (9) summary table (steps, timings, versions).
  - Accept: script exit 0; stdout contains `BEFORE: ELIGIBLE` and `AFTER: REJECTED(UNDER_AGE)`.
  - Depends: all of M2–M6 checked.
- [ ] **T-702 — Demo documentation.**
  - Do: `docs/demo.md` (prereqs = E-tasks; exact commands; expected output; troubleshooting incl. §2.6 pitfalls); update root README.
  - Accept: fresh-checkout dry run following only `docs/demo.md` succeeds; log it in the Progress Log.
  - Depends: T-701.

### M8 — Phase 2 (GATED — a human must replace this ☐ with ☑ before any T-8xx starts)

- [ ] **T-801 — DMN import adapter** (decision tables → IR; restricted-FEEL subset; BPMN rejected with clear error; unmapped FEEL → review queue).
- [ ] **T-802 — Mode-A decision service** (stateless FastAPI + embedded Zen, loads latest approved JDM per decision; publish/rollback endpoints).
- [ ] **T-803 — Second DBMS driver** for the MCP connector (proves pluggability; suggest MySQL or Oracle per customer).
- [ ] **T-804 — Mining-model benchmark harness** (value vs frontier tiers on real slices; metrics: rule-level precision/recall vs reviewed ground truth, cost per 1k rules; report). ⚠ needs customer samples + model-policy answer.
- [ ] **T-805 — Governance UI hardening** (OIDC auth, role model, richer diff/batch review UX).

---

## 4. Blocked On Customer

| Item | Blocks | Status |
|---|---|---|
| Sample Java enrollment source + PostgreSQL schema (masked OK) | real-data validation of M3; T-804 | ⏳ requested 2026-07-02 |
| Pilot product/flow selection | Phase-1 scoping on the real system | ⏳ review-doc Q1 |
| Approval policy (who/how many/evidence) | T-805 config (M2 defaults are placeholders) | ⏳ review-doc Q4 |
| Chinese-origin model policy | T-804 shortlist | ⏳ asked 2026-07-04 |
| Coding-conventions sample | codegen style pass on T-502 templates | ⏳ review-doc Q7 |

## 5. Definition of Done (global)

Task checked ⇔ all Accept commands pass locally ⇔ CI green ⇔ no §0.3 ground-rule violations ⇔ Progress Log updated. Milestone done ⇔ every task checked **and** its exit line is demonstrably true.

## 6. Out Of Scope (do not build, even if tempting)

Full FEEL support · BPMN import · a bespoke rule evaluator (use Zen; ADR-3) · graph database · message broker · real auth before T-805 · any UI beyond the minimal M4 scope · performance tuning before M7 passes.

## 7. Progress Log (append-only; newest last)

Format: `YYYY-MM-DD HH:MM | T-### | done|BLOCKED|PROPOSAL | <commit> | one-line note`

```
(empty)
```
