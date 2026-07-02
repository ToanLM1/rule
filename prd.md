# Rule-Engine-Based Source Generation Module
## Product Requirements Description / Track Overview

> **Scope isolation note.** This document describes a **separate track** from the Telecom Business Knowledge Assistant (`agent/services/knowledge-api/prd.md`). It is the deferred **PGM source-generation** direction referenced in that PRD (§4.10), confirmed with the customer on 2026-06-23 and 2026-06-29. It is **effectively a different application**: its inputs are the customer's **git repositories and databases** (not documents/knowledge), and it runs on its **own analysis and mining stack** (e.g. Joern static analysis + a purpose-built rule miner + ETL + JDM code generation) — **not** the knowledge assistant's document/knowledge (RAG) ingestion. It has its own domain (finance/insurance enrollment logic), its own data model, and its own architecture. Keep this context out of the knowledge-assistant PRD to avoid polluting either scope. Nothing here is in active implementation; this is a design/groundwork document.

## 1. Track Summary

The goal of this track is a module that **manages complex business logic as data (rules-as-data) instead of source code, and can reflect edited rules back into deployable source.**

In financial/insurance systems, the logic for product enrollment (`가입 Rule`) is currently buried inside source code, which makes it hard to (a) understand the enrollment rules and (b) modify them when products or policies change. This module externalizes that logic into a governed rule repository so that:

- adding a product or changing enrollment logic means **editing data, not code**;
- business users can read, review, version, and approve rules;
- (longer-term) an edited rule can be **reflected into the source and deployed**.

This is a substantially larger and separate effort from the knowledge assistant. It should begin with its own design phase and a narrow PoC. (This track is now being actively driven by the customer, 2026-07-02.)

## 2. Relationship To The Existing Project

This track is **largely a separate application**, not an extension of the knowledge assistant. Be precise about what is and is not shared:

- **Effectively independent:** the inputs are the customer's **git repositories and databases**; the analysis/mining stack (Joern-based static analysis + a purpose-built rule miner, tabular ETL, and JDM code generation) is **all new**. It does **not** run on the knowledge assistant's document/knowledge (RAG) ingestion.
- **At most a minor overlap (not a foundation):** manuals/documents are an *optional, supplementary* source (§5.1 #2). That one sub-path may borrow low-level document-parsing utilities, but it still needs **rule-oriented extraction** producing structured condition/action rules — **not** the existing RAG ingestion as-is, whose output (retrieval chunks for citation/search) has a different contract. Do not describe the document pipeline as "the shared component."
- **Not reused:** the chat/RAG retrieval flow, citation surfaces, Neptune graph schema for telecom domains, and NUEL/ProcessMap content are **not** part of this track.
- **New:** a canonical rule repository (rules-as-data), rule-engine integration, Joern-based static analysis + source-code rule mining, tabular ETL, a DMN/external-engine import adapter (DMN→canonical→JDM), and the code-generation/deploy path are all new to this track.

## 3. Business Goal

Reduce the cost and risk of changing business logic in finance/insurance systems by decoupling enrollment/decision logic from application code. Target outcomes (industry benchmark, to be validated against the customer's own baseline):

- faster product time-to-market (decoupling business logic from code is reported to cut 40–60%);
- lower IT cost for rule maintenance;
- clearer, auditable, business-owned rules.

## 4. Domain And Terminology

- **Enrollment rule (`가입 Rule`)** — the conditions and actions governing whether/how a customer can enroll in a financial/insurance product (eligibility, required documents, rate selection, validations).
- **Rules-as-data** — rules stored as structured data (decision tables / JSON) in a repository, not as code.
- **Rule engine** — a component that loads rules and evaluates inputs against them at runtime.
- **Externalization** — the running source **calls the rule engine** at runtime (Option A).
- **Code generation** — source code is **generated from rule data**, then compiled and deployed (Option B).
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
- **External rule engine (DMN / engine-native) → import adapter** (customer request, 2026-07-02): parse the DMN (or engine-native) rules, **map to the canonical rule model, then generate JDM from that model** — never convert DMN directly into production JDM. This keeps validation, review, versioning, and future code/rule generation under our control. Simple decision tables map cleanly (DMN inputs→conditions, outputs→actions, hit policy→decision logic, DRD→decision-graph structure); complex **FEEL** expressions / boxed expressions may not map 1:1 and need special handling. Treat as an *import/conversion module*, not native compatibility.

Common output contract for every extracted item:

```
{ conditions, action(s), product / domain, source_reference, confidence, status = pending }
```

### 5.3 Rule Repository (Rules-As-Data)
A canonical system of record storing rules as data (decision tables / JSON).

- **Data model:** rule id, conditions, actions, product, version, effective/expiry dates, source trace, confidence, status (pending/approved/retired).
- **Governance:** maker-checker approval workflow, versioning and diff, full audit log (essential for finance/insurance compliance).
- **Quality:** a regression/golden test set so rule changes are validated before publishing.
- The engine consumes **only approved rules**; pending/rejected suggestions never reach production.

### 5.4 Rule Engine Execution
The system must load approved rules into the chosen engine's native format and evaluate enrollment requests. Evaluation is stateless; reference/lookup data is attached as needed.

### 5.5 Round-Trip And Deploy (Two Options)
The phrase "reflect edited rules into source and deployed" has two interpretations; the choice shapes the architecture. **This must be confirmed with the customer (see §10).**

| | A — Externalization (not chosen) | B — Code generation (customer's choice) |
|---|---|---|
| How | Current source calls the rule engine at runtime (API/embedded) | Generate source code from rule data → compile → deploy via CI/CD |
| "Deploy" means | Publish a new rule version (no app rebuild) | Rebuild & redeploy the code module |
| Pros | Fast, low-risk, industry standard | Logic runs inside legacy, no engine runtime dependency |
| Cons | Requires the engine running alongside | Complex; safe/correct code generation is hard; higher risk |
| Use when | Most cases | Logic must run inside legacy, or for performance/compliance reasons |

**Decision (customer, 2026-06-30 / 2026-07-02): lead with B (code generation).** The original recommendation was A-first (prove value quickly, lower risk), but the customer confirmed B is the target: after the one-time initial load, users edit rules in the repository and the system must **regenerate source and deploy** — the source, not a runtime engine, is what runs in production. Option A (source calls the engine at runtime) is **not being pursued**. This makes source-code round-trip (§5.1 #3) and safe code generation the core of the effort; the extra difficulty this adds is accepted (see §8 Safety, §9).

> Note: Option B (code generation) is **not the engine's job** — it is a separate, templated code generator that reads the canonical rule repository and renders source. Therefore the engine choice does not lock the code-gen approach.

## 6. Architecture — Five-Layer Pipeline

```
① Legacy source     →  ② Extraction          →  ③ Rule repository     →  ④ Rule engine      →  ⑤ Round-trip & deploy
(DB tables, code,       - tables: ETL            (rules-as-data)           executes rules        A: source calls engine
 procedures, manuals,   - code: rule mining+LLM  - canonical model        (GoRules/Drools/      B: generate source → deploy
 external engine/DMN)   - manuals: rule extract   - versioned, traced       DecisionRules)        (Option B chosen)
                        - DMN: import→canonical   - human-reviewed
```

1. **Legacy source** — inventory per §5.1; pick a narrow pilot.
2. **Extraction** — per §5.2; outputs candidate rules.
3. **Rule repository** — per §5.3; canonical, governed system of record.
4. **Rule engine** — per §5.4 and §7.
5. **Round-trip & deploy** — per §5.5.

## 7. Rule Engine Selection

Engine choice is driven by this track's specific needs: **programmatic rule generation/loading**, self-hostability, cost control for a PoC, multi-language runtime, and a rule format usable as a code-gen intermediate representation.

**Primary recommendation: GoRules (Zen / JDM).** JSON-native (JDM) — ideal for auto-generation and as a code-gen IR; MIT open-source and free to self-host; polyglot (Rust/Node/Python/Go/Java/C#/Swift); embeddable or cloud.

Alternatives by scenario:

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
- **Safety:** rule mining from code is error-prone; human review is mandatory and Option B (code-gen) is kept a separate, later phase.
- **Deployment fit:** self-hostable (on-prem/air-gapped possible for finance/insurance); AWS acceptable.
- **Multi-site / general-purpose (customer directive, 2026-07-02):** this must be built as a reusable product/solution applied across many sites, not a per-customer one-off. Every component must be generic and configuration-driven; anything that cannot be made general must be explicitly flagged as such. In particular the DB access layer must be a **plug-and-play, connection-info-driven MCP library** (a reusable owned asset), not rebuilt per site. Language and DBMS support must be pluggable (see §10 Q1).

## 9. Phasing

> Reworked 2026-07-02 to reflect confirmed customer decisions: **Option B (code generation) is the target** (§5.5), the stack is **Java-first / PostgreSQL-first with pluggable extension** (§10 Q1), and everything is built as a **reusable multi-site solution** (§8). Engine choice is deferred (§10 Q6); GoRules Zen (JDM) remains the working assumption.

- **Phase 0 — Design & samples:** finalize the canonical rule model; obtain sample legacy materials (Java enrollment source + PostgreSQL schema, anonymized); lock the pluggable-architecture boundaries (per-language parser, per-DBMS MCP connector, per-language code generator).
- **Phase 1 — PoC (source round-trip, Option B):** one financial/insurance product, one enrollment flow. Initial load from config tables + manuals (#1, #2) **plus** a first slice of Java source-code mining (#3, the differentiator) using Joern to locate and chunk the enrollment logic; store as rules-as-data; then **generate Java source from an edited rule and deploy it** (build + golden tests). **Success criterion:** editing one rule in the repository regenerates correct Java source that changes the enrollment outcome, validated by the golden test set — no hand-written code change.
- **Phase 2 — Productize for multi-site:** harden the reusable DB MCP library (connection-info-driven, PostgreSQL first), the pluggable parser/generator interfaces, and governance (maker-checker, versioning, audit). Prove a second site/DBMS or second language can be added by configuration + a plug-in, not a rewrite.
- **Phase 3 — Scale:** more products/flows; broaden language and DBMS plug-ins; revisit deferred sources (#4 stored procedures, #5 UI rules) under review; finalize engine decision.

## 10. Open Questions / Inputs Still Needed

1. **Legacy stack** — *Answered (2026-07-02): **Java first**, but the design must remain extensible to other languages (this is a solution, not a one-off).* Drives the mining parser (Joern has strong Java support) and the code-gen target. Parser + generator must be pluggable per language.
   - **DB** — *Answered (2026-07-02): **PostgreSQL first**, extensible to other DBMS.* DB access is delivered as a reusable plug-and-play MCP library (see §8 multi-site directive).
2. **Meaning of "reflected & deployed"** — *Answered (2026-06-30 / 2026-07-02): **Option B (code generation) prioritized over A (runtime engine)**.* ⚠️ This reverses the §9 phasing (which currently puts externalization/A first); §9 must be revisited to lead with B.
3. **Pilot product/flow** — which one? *(still open)*
4. **Compliance/audit constraints** — what governance is required before a rule can go live? *(still open)*
5. **Sample materials** — sample source code with enrollment logic, DB schema/table definitions, and/or sample config/rate-table data (anonymized/masked acceptable), to ground the extraction design with real data points. *(still open — requested 2026-07-02)*
6. **Final engine decision** — *Deferred by customer (2026-07-02): will decide after further review.* Confirmed the "Zen" reference = **GoRules Zen Engine** (JDM), our primary recommendation (§7); still weighing vs DecisionRules / Drools.

## 11. Demo / Validation Direction (Future)

A minimal validation for Phase 1:

- load a small enrollment rule set from a sample config table + manual into the rule repository;
- review and approve the candidate rules;
- evaluate a sample enrollment request through the engine;
- edit one rule (e.g., change an eligibility threshold), re-publish, and confirm the enrollment outcome changes — with no code modification.
