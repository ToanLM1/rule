# Rule-Engine-Based Source Generation Module
## Product Requirements Description / Track Overview

> **Scope isolation note.** This document describes a **separate track** from the Telecom Business Knowledge Assistant (`agent/services/knowledge-api/prd.md`). It is the deferred **PGM source-generation** direction referenced in that PRD (§4.10), confirmed with the customer on 2026-06-23 and 2026-06-29. It shares only one thing with the current project — the **document/knowledge extraction pipeline** — and otherwise has its own domain (finance/insurance enrollment logic), its own data model, and its own architecture. Keep this context out of the knowledge-assistant PRD to avoid polluting either scope. Nothing here is in active implementation; this is a design/groundwork document.

## 1. Track Summary

The goal of this track is a module that **manages complex business logic as data (rules-as-data) instead of source code, and can reflect edited rules back into deployable source.**

In financial/insurance systems, the logic for product enrollment (`가입 Rule`) is currently buried inside source code, which makes it hard to (a) understand the enrollment rules and (b) modify them when products or policies change. This module externalizes that logic into a governed rule repository so that:

- adding a product or changing enrollment logic means **editing data, not code**;
- business users can read, review, version, and approve rules;
- (longer-term) an edited rule can be **reflected into the source and deployed**.

This is a substantially larger and separate effort from the knowledge assistant. It should begin with its own design phase and a narrow PoC, and only proceed in earnest after the knowledge assistant's answer quality for business-manual and inquiry-response questions is solid.

## 2. Relationship To The Existing Project

- **Reused:** the existing document/knowledge **extraction pipeline** (turning manuals/documents into structured knowledge) is reused as one of the rule-extraction sources (see §6, source 2d).
- **Not reused:** the chat/RAG retrieval flow, citation surfaces, Neptune graph schema for telecom domains, and NUEL/ProcessMap content are **not** part of this track.
- **New:** a canonical rule repository (rules-as-data), a rule engine, legacy rule-mining, and an optional code-generation/deploy path are all new to this track.

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
| 1 (start here) | Config/code tables in DB (product master, rate tables, eligibility code tables) | Already tabular | Easiest | Direct ETL → rule data, near-lossless |
| 2 | Business manuals/documents | Structured text | Easy | Reuse the existing extraction pipeline |
| 3 | Validation logic in source code (if-else, switch) | Code | Hard | Needs rule mining + mandatory human review |
| 4 | Stored procedures / SQL business logic | DB code | Hard | Same as #3 |
| 5 | Screen/UI validation rules (required fields, value ranges) | UI code | Medium | Supplementary |

**Selection criterion:** prefer items that are (i) frequently changed, (ii) already semi-structured, (iii) business-owned. Start with #1 + #2; tackle code (#3, #4) under strict review.

### 5.2 Extraction To Candidate Rules
The system must convert heterogeneous legacy logic into normalized **candidate rules** via parallel sub-pipelines, all producing a common output contract. Nothing extracted is auto-applied; every item is a suggestion routed to human review.

- **Tabular config → ETL** (deterministic, highest trust): map condition columns and action columns; each row → one rule row.
- **Source code → rule mining** (static analysis + LLM assist): locate decision points, convert each branch to a human-readable rule + structured condition/action, de-duplicate, attach exact source location for traceability. Candidate-only; mandatory review.
- **Stored procedures/SQL → rule mining** (same pattern, DB-side).
- **Manuals/documents → existing extraction pipeline** (reused), mapped to the same candidate-rule shape.

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

| | A — Externalization (recommended first) | B — Code generation (literal interpretation) |
|---|---|---|
| How | Current source calls the rule engine at runtime (API/embedded) | Generate source code from rule data → compile → deploy via CI/CD |
| "Deploy" means | Publish a new rule version (no app rebuild) | Rebuild & redeploy the code module |
| Pros | Fast, low-risk, industry standard | Logic runs inside legacy, no engine runtime dependency |
| Cons | Requires the engine running alongside | Complex; safe/correct code generation is hard; higher risk |
| Use when | Most cases | Logic must run inside legacy, or for performance/compliance reasons |

**Recommendation:** Phase 1 = A (externalization) to prove value quickly; Phase 2 = add B (code generation) only where truly required.

> Note: Option B (code generation) is **not the engine's job** — it is a separate, templated code generator that reads the canonical rule repository and renders source. Therefore the engine choice does not lock the code-gen approach.

## 6. Architecture — Five-Layer Pipeline

```
① Legacy source     →  ② Extraction          →  ③ Rule repository     →  ④ Rule engine      →  ⑤ Round-trip & deploy
(DB tables, code,       - tables: ETL            (rules-as-data)           executes rules        A: source calls engine
 procedures, manuals)   - code: rule mining+LLM  - canonical model        (GoRules/Drools/      B: generate source → deploy
                        - manuals: reuse pipeline - versioned, traced       DecisionRules)
                                                  - human-reviewed
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

## 9. Phasing

- **Phase 0 — Design & samples:** confirm §10 questions; obtain sample legacy materials; finalize canonical rule model.
- **Phase 1 — PoC (externalization):** one financial/insurance product, one enrollment flow; initial source = config tables + manuals (#1, #2); engine = GoRules; round-trip = A. **Success criterion:** editing one rule in data changes the enrollment outcome correctly, with no code change.
- **Phase 2 — Code generation (Option B):** add templated source generation + deploy only where required; expand legacy sources (#3, #4) under review.
- **Phase 3 — Scale:** more products/flows, hardened governance, broader engine integration.

## 10. Open Questions / Inputs Still Needed

1. **Legacy stack** — COBOL / Java / .NET? which DB? (drives mining and code-gen approach).
2. **Meaning of "reflected & deployed"** — regenerate source code (Option B), or simply have the source call the engine (Option A)? *(Most important — shapes the whole design.)*
3. **Pilot product/flow** — which one?
4. **Compliance/audit constraints** — what governance is required before a rule can go live?
5. **Sample materials** — sample source code with enrollment logic, DB schema/table definitions, and/or sample config/rate-table data (anonymized/masked acceptable), to ground the extraction design with real data points.
6. **Final engine decision** — confirm GoRules vs DecisionRules vs Drools once questions 1–4 are answered.

## 11. Demo / Validation Direction (Future)

A minimal validation for Phase 1:

- load a small enrollment rule set from a sample config table + manual into the rule repository;
- review and approve the candidate rules;
- evaluate a sample enrollment request through the engine;
- edit one rule (e.g., change an eligibility threshold), re-publish, and confirm the enrollment outcome changes — with no code modification.
