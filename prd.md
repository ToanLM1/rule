# Rule-Engine-Based Source Generation Module
## Product Requirements Description / Track Overview

> **Scope isolation note.** This document describes a **separate track** from the Telecom Business Knowledge Assistant (`agent/services/knowledge-api/prd.md`). It is the deferred **PGM source-generation** direction referenced in that PRD (§4.10), confirmed with the customer on 2026-06-23 and 2026-06-29. It is **effectively a different application**: its inputs are the customer's **git repositories and databases** (not documents/knowledge), and it runs on its **own analysis and mining stack** (e.g. Joern static analysis + a purpose-built rule miner + ETL + deterministic source/JDM generation) — **not** the knowledge assistant's document/knowledge (RAG) ingestion. It has its own domain (finance/insurance enrollment logic), its own data model, and its own architecture. Keep this context out of the knowledge-assistant PRD to avoid polluting either scope. Nothing here is in active implementation; this is a design/groundwork document.

## 1. Track Summary

The goal of this track is a module that **manages complex business logic as data (rules-as-data) instead of source code, and can reflect edited rules back into deployable source.**

In financial/insurance systems, the logic for product enrollment (`가입 Rule`) is currently buried inside source code, which makes it hard to (a) understand the enrollment rules and (b) modify them when products or policies change. This module externalizes that logic into a governed rule repository so that:

- adding a product or changing enrollment logic means **editing data, not code**;
- business users can read, review, version, and approve rules;
- (longer-term) an edited rule can be **reflected into the source and deployed**.

**Architecture stance (2026-07-03, see `architecture.md`):** the platform's source of truth is a vendor-neutral **Canonical Rule IR** — not JDM, DMN, or any engine-native format. Production delivery is a **per-site choice between two modes** over that same IR: **generated source code** (mode B — for sites whose logic lives in code; the Phase-1 lead) or **our rule engine as the runtime** (mode A — for sites migrating off an existing third-party engine, confirmed by the customer 2026-07-03). Engine formats are adapters around the IR, never the system of record.

This is a substantially larger and separate effort from the knowledge assistant. It should begin with its own design phase and a narrow PoC. (This track is now being actively driven by the customer, 2026-07-02.)

## 2. Relationship To The Existing Project

This track is **largely a separate application**, not an extension of the knowledge assistant. Be precise about what is and is not shared:

- **Effectively independent:** the inputs are the customer's **git repositories and databases**; the analysis/mining stack (Joern-based static analysis + a purpose-built rule miner, tabular ETL, and JDM code generation) is **all new**. It does **not** run on the knowledge assistant's document/knowledge (RAG) ingestion.
- **At most a minor overlap (not a foundation):** manuals/documents are an *optional, supplementary* source (§5.1 #2). That one sub-path may borrow low-level document-parsing utilities, but it still needs **rule-oriented extraction** producing structured condition/action rules — **not** the existing RAG ingestion as-is, whose output (retrieval chunks for citation/search) has a different contract. Do not describe the document pipeline as "the shared component."
- **Not reused:** the chat/RAG retrieval flow, citation surfaces, Neptune graph schema for telecom domains, and NUEL/ProcessMap content are **not** part of this track.
- **New:** a canonical rule repository (Canonical Rule IR), Joern-based static analysis + source-code rule mining, tabular ETL, a DMN/external-engine import adapter (DMN→Canonical Rule IR), target generators (Java source, JDM), engine-runtime integration (GoRules Zen), and the CI/CD deploy path are all new to this track.

## 3. Business Goal

Reduce the cost and risk of changing business logic in finance/insurance systems by decoupling enrollment/decision logic from application code. Target outcomes (industry benchmark, to be validated against the customer's own baseline):

- faster product time-to-market (decoupling business logic from code is reported to cut 40–60%);
- lower IT cost for rule maintenance;
- clearer, auditable, business-owned rules.

## 4. Domain And Terminology

- **Enrollment rule (`가입 Rule`)** — the conditions and actions governing whether/how a customer can enroll in a financial/insurance product (eligibility, required documents, rate selection, validations).
- **Rules-as-data** — rules stored as structured data (decision tables / JSON) in a repository, not as code.
- **Canonical Rule IR** — the platform-owned, vendor-neutral rule representation (restricted, codegen-friendly JSON) used as the governed source of truth. See `architecture.md`.
- **Source adapter** — a plug-in that extracts candidate rules from one legacy input kind (DB tables, source code, manuals, DMN/engine assets) into the Canonical Rule IR shape.
- **Target generator** — a plug-in that emits artifacts from approved IR: Java source, JDM, DMN export, golden tests, reports.
- **Rule engine** — a component that loads rules and evaluates inputs at runtime. Here: GoRules Zen, fed from the IR via JDM export. It is the *production runtime* only in delivery mode A, and a *preview/simulation* tool everywhere else. It is never the system of record.
- **Externalization (mode A)** — the running system **calls the rule engine** at runtime; the delivery mode for engine-migration sites (§5.1 #6).
- **Code generation (mode B)** — source code is **generated from rule data**, then compiled and deployed; the delivery mode for logic-in-code sites, and the Phase-1 lead.
- **Delivery mode** — the per-site choice between A and B; both are target paths over the same Canonical Rule IR, so this is a deployment decision, not an architecture fork.
- **Round-trip** — the full loop: edit rule in repository → reflect into the running system (A or B).

## 5. Core Functional Requirements

### 5.1 Initial Data Loading From Legacy
The module must be able to populate the rule repository from existing legacy assets ("initial data loading"). Candidate legacy sources, ranked by ease and risk:

| Priority | Legacy item | Nature | Ease | Note |
|---|---|---|---|---|
| 1 (priority 1) | Config/code tables in DB (product master, rate tables, eligibility code tables) | Already tabular | Easiest | Direct ETL → rule data, near-lossless. Confirmed priority 1 by customer (2026-06-30). |
| 2 | Business manuals/documents | Structured text | Easy | Rule-oriented extraction (new; supplementary); may borrow document-parsing utilities but not the RAG ingestion as-is. Needs a supplementary path when the manual is sparse (customer 2026-06-30). |
| 3 (strategic differentiator) | Validation logic in source code (if-else, switch) | Code | Hard | Rule mining + mandatory human review; source DB via the reusable MCP. **Elevated to a strategic differentiator (customer 2026-06-30)** — pursued despite difficulty; this is what sets our Rule-Engine apart from other engines. |
| 4 | Stored procedures / SQL business logic | DB code | Hard | Same as #3. **Deferred / out of current scope (customer 2026-06-30).** |
| 5 | Screen/UI validation rules (required fields, value ranges) | UI code | Medium | Supplementary. **Excluded for now (customer 2026-06-30).** |
| 6 (distinct macro-case) | Rules already running in an **external rule engine** (DMN or engine-native format) | Rules-as-data (a standard) | Easy–Medium | **Import/migration path (customer 2026-07-02).** Some sites are not "logic in code" but "already an engine" — DMN is the OMG international standard, so DMN-based legacy is common. Serves the **original purpose** ("migrate systems on other companies' engines to ours") and the multi-site directive. Simple decision tables map cleanly; complex FEEL expressions / DRDs are the hard part. |

**Selection criterion (updated 2026-06-30 / 2026-07-02):** a legacy site falls into one of two macro-cases. **(a) Logic buried in code/data** (#1–#5): #1 (DB config/code tables) is the priority-1 initial source; #2 (manuals) follows, with a supplementary path for sparse manuals; #3 (source code) is **elevated to a strategic differentiator** — pursued despite its difficulty, under strict mandatory human review, because reflecting rules back into source (Option B, §5.5) is the customer's chosen direction; #4 (stored procedures) and #5 (UI rules) are deferred / out of current scope. **(b) Already on an external rule engine** (#6): import via DMN→canonical→JDM (§5.2) — the easier, standard case that broadens multi-site coverage, though it is table-stakes rather than the differentiator.

### 5.2 Extraction To Candidate Rules
The system must convert heterogeneous legacy logic into normalized **candidate rules** via parallel sub-pipelines, all producing a common output contract. Nothing extracted is auto-applied; every item is a suggestion routed to human review.

- **Tabular config → ETL** (deterministic, highest trust): map condition columns and action columns; each row → one rule row.
- **Source code → rule mining** (static analysis + LLM assist): locate decision points, convert each branch to a human-readable rule + structured condition/action, de-duplicate, attach exact source location for traceability. Candidate-only; mandatory review.
- **Stored procedures/SQL → rule mining** (same pattern, DB-side).
- **Manuals/documents → rule-oriented extraction** (new; supplementary source): produce candidate rules (structured condition/action) mapped to the same shape. May borrow low-level document-parsing utilities from the existing pipeline, but not its RAG/knowledge-chunk output as-is.
- **External rule engine (DMN / engine-native) → import adapter** (customer request, 2026-07-02): parse the DMN (or engine-native) rules and **map to the Canonical Rule IR** — never convert DMN directly into a production artifact. Targets (JDM for the engine runtime, or generated source) are emitted from the IR after governance. This keeps validation, review, versioning, and future code/rule generation under our control. Simple decision tables map cleanly (DMN inputs→conditions, outputs→actions, hit policy→decision logic, DRD→decision-graph structure); complex **FEEL** expressions / boxed expressions may not map 1:1 and go to a manual-review queue. **BPMN is not importable as rules** — it is workflow orchestration; decisions embedded in BPMN need a separate analysis path, candidate-only with mandatory review. Treat all of this as an *import/conversion module*, not native compatibility.

Common output contract for every extracted item:

```
{ conditions, action(s), product / domain, source_reference, confidence, status = pending }
```

### 5.3 Rule Repository (Rules-As-Data)
A canonical system of record storing rules as the vendor-neutral **Canonical Rule IR** (decision tables / restricted JSON; spec in `architecture.md`). Engine formats (JDM, DMN) and source code are **generated artifacts**, never the primary storage format.

- **Data model:** rule id, conditions, actions, product, version, effective/expiry dates, source trace, confidence, status (pending/approved/retired).
- **Governance:** maker-checker approval workflow, versioning and diff, full audit log (essential for finance/insurance compliance).
- **Quality:** a regression/golden test set so rule changes are validated before publishing.
- Downstream targets (engine runtime or code generation) consume **only approved rules**; pending/rejected suggestions never reach production.

### 5.4 Execution, Preview, And Validation
Production execution depends on the site's delivery mode (§5.5): generated source (mode B) or the rule engine as runtime (mode A). In both modes the platform provides **preview/simulation** by exporting IR→JDM and evaluating with an embedded GoRules Zen engine (stateless; reference/lookup data attached as needed) — no bespoke rule evaluator is built.

**Validation authority (avoid semantic drift):** for **mode B**, authoritative golden tests run against the **generated source itself** (compile + execute) — engine preview is advisory only, because preview (Zen/JDM semantics) and production (generated Java) are two different executors. For **mode A**, the engine *is* production, so engine-run golden tests are authoritative.

### 5.5 Round-Trip And Deploy (Two Delivery Modes)
The phrase "reflect edited rules into source and deployed" has two interpretations. Both are real; they map to the two site macro-cases (§5.1) and are **per-site delivery modes over the same Canonical Rule IR**, not competing architectures.

| | A — Engine runtime (engine-migration sites) | B — Code generation (logic-in-code sites; Phase-1 lead) |
|---|---|---|
| How | System calls our rule engine at runtime (IR→JDM→Zen, API/embedded) | Generate source code from approved IR → compile → deploy via CI/CD |
| "Deploy" means | Publish a new approved rule version (no app rebuild) | Rebuild & redeploy the generated code module |
| Pros | Fast rule changes, industry standard, keeps rules-as-data live | Logic runs inside legacy, no engine runtime dependency |
| Cons | Requires the engine running alongside | Complex; safe/correct code generation is hard; higher risk |
| Use when | Site already ran a third-party engine (§5.1 #6) — confirmed end state (customer 2026-07-03) | Logic was buried in source; production must stay engine-free |

**Decision (customer, 2026-06-30 → 2026-07-03): per-site delivery mode, with B leading.** For logic-in-code sites (macro-case a), the confirmed target is **B**: after the one-time initial load, users edit rules in the repository and the system **regenerates source and deploys** — the source, not an engine, runs in production. For engine-migration sites (macro-case b, §5.1 #6), the customer confirmed (2026-07-03) the end state is **our engine as the production runtime** (mode A) — converting an engine-based site to hard-coded source would forfeit the rules-as-data benefit it already has. Phase 1 leads with B (the harder, differentiating path); mode A arrives with the DMN/engine import work in Phase 2 (§9).

**Mode-B integration seam (critical, often missed):** generating a rule module is not enough — during initial load, the mined region in the legacy source must be **replaced by a call into the generated module** (a one-time, human-reviewed surgical change per site). Otherwise edited rules regenerate code that nothing calls. Defining this seam is part of Phase 0/1 design (`architecture.md`).

> Note: Option B (code generation) is **not the engine's job** — it is a separate, templated code generator that reads the canonical rule repository and renders source. Therefore the engine choice does not lock the code-gen approach.

## 6. Architecture — Adapter Pipeline Around A Canonical IR

Full design in **`architecture.md`** (source of truth for architecture detail). Summary:

```
① Legacy inputs    → ② Source adapters   → ③ Canonical Rule    → ④ Governance &     → ⑤ Target           → ⑥ Delivery
(DB tables, code,     (db-postgres,          Repository            validation           generators           B: CI/CD build +
 manuals, external     code-java/Joern,      - Canonical Rule IR   - review/approve     - Java source gen       golden tests →
 engines / DMN)        engine-dmn,           - versioned, traced   - rule diff          - JDM export            deploy
                       docs-manual)          - audited             - golden tests       - DMN export         A: Zen engine
                                                                   - Zen preview        - test/report gen       runtime
```

1. **Legacy inputs** — inventory per §5.1; pick a narrow pilot.
2. **Source adapters** — per §5.2; pluggable per input kind; output candidate IR rules.
3. **Canonical rule repository** — per §5.3; the governed system of record (IR, never engine formats).
4. **Governance & validation** — per §5.3/§5.4; review, approval, golden tests, Zen-based preview.
5. **Target generators** — pluggable emitters from approved IR (Java source, JDM, DMN, tests, reports).
6. **Delivery** — per-site mode (§5.5): B = CI/CD build/test/deploy of generated source; A = Zen engine runtime.

## 7. Rule Representation And Engine Strategy

**The primary architecture decision is the Canonical Rule IR and the adapter model around it — not the engine** (see `architecture.md`, ADR-1). No engine-native format (JDM, DMN, DRL) may become the system of record; engines consume artifacts *generated from* the IR.

**Engine (working decision, 2026-07-03): GoRules Zen.** The customer has effectively accepted GoRules/Zen (license/cost concerns addressed 2026-07-02); formal confirmation pending (§10 Q6). Zen fits both of its roles here: **mode-A production runtime** for engine-migration sites, and **embedded preview/simulation** everywhere (MIT license, in-process embedding, polyglot bindings — Rust/Node/Python/Go/Java/C#). JDM is JSON-native, so the IR→JDM export adapter is straightforward. Because the engine sits behind the IR + export adapter, swapping it later would be localized, not a rewrite.

Fallback alternatives by scenario (if the final engine decision changes):

| If the customer… | Engine | Why |
|---|---|---|
| Wants a fast, cheap, automation-heavy PoC (default) | **GoRules** | JSON-native, free, self-host |
| Requires business-user UI + audit/versioning up front (common in insurance) | **DecisionRules.io** | API-first managed BRMS, lookup tables, audit; self-host available |
| Is a Java shop wanting zero vendor risk + Excel decision tables | **Drools** | Proven open-source, business-editable Excel tables |
| Mandates enterprise governance and has an IBM footprint and budget | IBM ODM | Strongest governance, but expensive and least automation-friendly |

**Generally not recommended for this track:** Camunda (8.6+ production licensing tightened; BPMN-oriented, not needed here) and Corticon (commercial; smaller community) — except that Corticon.js natively compiles rules to JavaScript source, which could be relevant if Option B is prioritized.

A fuller vendor survey (license, deployment, pricing, pros/cons) is maintained as an appendix in this track: `vendor-survey.ko.md` / `vendor-survey.vi.md`. The customer-facing initial design proposal is in `proposals/item2-source-module.en.docx` / `proposals/item2-source-module.ko.docx`.

## 8. Non-Functional Requirements

- **Trust & explainability:** every rule traces back to its legacy source; candidate rules are human-reviewed before activation.
- **Governance/compliance:** maker-checker approval, versioning, audit trail — required for finance/insurance.
- **Korean preservation:** Korean text in rules, product names, and conditions must survive extraction, storage, and execution.
- **Safety:** rule mining from code is error-prone; human review is mandatory before any candidate rule is approved, and production delivery is gated by golden tests.
- **Deterministic generation:** production source code is generated by deterministic templates/AST-based generators. LLMs assist *mining only* (producing human-reviewed candidates); no free-form LLM code ever reaches production.
- **Vendor neutrality:** no rule-engine-native format (JDM, DMN, DRL) may become the system of record; the Canonical Rule IR is the only primary storage format.
- **Preview–production consistency:** golden-test authority follows the delivery mode (§5.4) — generated source for mode B, engine runtime for mode A; engine preview is never the authority for mode-B behavior.
- **Deployment fit:** self-hostable (on-prem/air-gapped possible for finance/insurance); AWS acceptable.
- **Co-deployment with the knowledge assistant (MIGHT-HAVE, not MUST-HAVE):** for PoC/MVP the rule-engine and the knowledge/manual agent may be **co-located on the same server** (e.g. one EC2) as **separate apps** — the customer's preference (2026-07-03): keep them independently configured but on one host to avoid extra deployment/cost complexity. On the same host they communicate over `localhost`, so no special network setup and negligible call latency. Inter-service communication (rule-engine ↔ knowledge/manual agent, e.g. sharing indexed info via API) should be **kept possible but treated as optional** — in most cases the two are expected to run without needing each other's data, so this is a precaution, not a designed dependency. Keep the boundary clean so either app can later split onto its own server without a rewrite.
- **Multi-site / general-purpose (customer directive, 2026-07-02):** this must be built as a reusable product/solution applied across many sites, not a per-customer one-off. Every component must be generic and configuration-driven; anything that cannot be made general must be explicitly flagged as such. In particular the DB access layer must be a **plug-and-play, connection-info-driven MCP library** (a reusable owned asset), not rebuilt per site. Language and DBMS support must be pluggable (see §10 Q1).

## 9. Phasing

> Reworked 2026-07-03: **per-site delivery modes** with **B (code generation) leading** (§5.5); **Canonical Rule IR** as the system of record (`architecture.md`); stack **Java-first / PostgreSQL-first with pluggable adapters** (§10 Q1); **reusable multi-site solution** (§8); engine = **GoRules Zen** (working decision, §10 Q6).

- **Phase 0 — Design & samples:** finalize **Canonical Rule IR v1** and its restricted profile; define the source-adapter and target-generator contracts; design the **mode-B integration seam** (§5.5) against sample code; obtain sample legacy materials (Java enrollment source + PostgreSQL schema, anonymized); confirm whether pilot sites hold existing engine assets (Camunda DMN etc.).
- **Phase 1 — PoC (mode B reference path):** one financial/insurance product, one enrollment flow. Adapters: PostgreSQL config-table (#1) + Java source mining via Joern (#3, the differentiator), manuals (#2) as supplement. Store as IR; preview via IR→JDM→embedded Zen; **generate Java source deterministically from an edited approved rule**, run golden tests against the generated code, produce a reviewable diff/PR, deploy. **Success criterion:** editing one approved rule regenerates Java source that passes golden tests and changes the enrollment outcome — no hand-written code change.
- **Phase 2 — Productize + mode A:** harden the reusable DB MCP library (connection-info-driven, PostgreSQL first) and the adapter/generator contracts; build the **DMN/engine import adapter** and deliver the **engine-runtime mode (A)** for an engine-migration site (IR→JDM→Zen runtime); harden governance (maker-checker, versioning, audit). Prove a second DBMS or language lands as a plug-in, not a rewrite.
- **Phase 3 — Scale:** more products/flows/sites; broaden language, DBMS, and engine-import adapters; revisit deferred sources (#4 stored procedures, #5 UI rules) under review; DMN export.

## 10. Open Questions / Inputs Still Needed

1. **Legacy stack** — *Answered (2026-07-02): **Java first**, but the design must remain extensible to other languages (this is a solution, not a one-off).* Drives the mining parser (Joern has strong Java support) and the code-gen target. Parser + generator must be pluggable per language.
   - **DB** — *Answered (2026-07-02): **PostgreSQL first**, extensible to other DBMS.* DB access is delivered as a reusable plug-and-play MCP library (see §8 multi-site directive).
2. **Meaning of "reflected & deployed"** — *Answered, refined 2026-07-03: **per-site delivery mode** (§5.5).* B (code generation) for logic-in-code sites — the Phase-1 lead; A (our engine as production runtime) confirmed as the end state for engine-migration sites (§5.1 #6). Both are target paths over the same Canonical Rule IR.
3. **Pilot product/flow** — which one? *(still open)*
4. **Compliance/audit constraints** — what governance is required before a rule can go live? *(still open)*
5. **Sample materials** — sample source code with enrollment logic, DB schema/table definitions, and/or sample config/rate-table data (anonymized/masked acceptable), to ground the extraction design with real data points. *(still open — requested 2026-07-02)*
6. **Final engine decision** — *Working decision (2026-07-03): **GoRules Zen** effectively accepted by the customer; license/cost concerns addressed 2026-07-02.* Formal confirmation still pending, but the engine now sits behind the IR + JDM-export adapter (§7), so a late swap would be localized. Confirmed the "Zen" reference = GoRules Zen Engine (JDM).

## 11. Demo / Validation Direction (Future)

A minimal validation for Phase 1 (mode B):

- load a small enrollment rule set from a sample config table + Java source slice into the rule repository (IR);
- review and approve the candidate rules;
- preview a sample enrollment request (IR→JDM→embedded Zen);
- edit one rule (e.g., change an eligibility threshold), approve, **regenerate the Java rule module**, run golden tests against the generated code, and confirm the enrollment outcome changes — with **no hand-written code change**.

A follow-on validation for Phase 2 (mode A): import a sample DMN asset → IR → approve → publish to the Zen runtime → confirm the same edited-rule flow changes the outcome with no rebuild.
