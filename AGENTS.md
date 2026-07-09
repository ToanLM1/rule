# AGENTS.md

## Purpose
This directory is an **isolated track**: the **Rule-Engine-Based Source Generation Module** for finance/insurance enrollment logic. It is the deferred "PGM source-generation" direction mentioned in the Telecom Business Knowledge Assistant PRD (`../agent/services/knowledge-api/prd.md`, §4.10), kept separate so its scope does not pollute the active knowledge-assistant work.

Read `prd.md` in this directory as the source of truth for this track before doing anything here.

## Scope Boundary (read first)
- This track is **NOT** part of the knowledge-assistant chat/RAG product; it is **effectively a separate application**. Do not mix its requirements with `agent/` or `frontend/`.
- Inputs are the customer's **git repositories and databases**; the analysis/mining stack (Joern static analysis + a purpose-built rule miner, ETL, JDM code-gen) is **all new**. It does **not** run on the knowledge assistant's document/knowledge (RAG) ingestion.
- There is **no meaningful shared component**. At most, the optional/supplementary manuals source (`prd.md` §5.1 #2, §5.2) may borrow low-level document-parsing utilities — but it needs rule-oriented extraction, not the RAG ingestion as-is. Do not call the document pipeline "the shared component."
- Not reused from the main project: chat/RAG retrieval, citation surfaces, Neptune telecom graph schema, NUEL/ProcessMap content.
- **Status: implementation (Phase 0/1) — customer approved the architecture 2026-07-04.** Build strictly per `IMPLEMENTATION_PLAN.md` (task order, acceptance criteria, progress protocol). Still do not wire anything into the knowledge-assistant backend/frontend.

## Domain
- Business problem: enrollment logic (`가입 Rule`) for financial/insurance products is buried in source code; this track manages it as **rules-as-data** in a governed repository, with an optional path to reflect edited rules back into deployable source.
- Customer context confirmed 2026-06-23 and 2026-06-29 (see `prd.md` §1, §10).

## Files In This Track
- `prd.md` — track PRD (product source of truth).
- `architecture.md` — architecture design (design source of truth: ADRs, IR spec, adapter contracts, tech stack).
- `IMPLEMENTATION_PLAN.md` — execution plan + progress tracker for AI coding agents (milestones M0–M8, task checkboxes, agent protocol). **Implementing agents start here.**
- `prd-architecture-revision-note.md` — superseded historical note (do not follow).
- `proposals/business-rules-platform-design-review.en.docx` — customer-facing design review document (approved 2026-07-04).
- `vendor-survey.ko.md` / `vendor-survey.vi.md` — rule-engine vendor comparison (license, deployment, pricing, pros/cons, recommendation). Appendix to `prd.md` §7.
- `proposals/item2-source-module.en.docx` / `.ko.docx` — the initial design proposal for the customer (Item 2 reply).

## Working Rules
- Keep this track's context here. If a change affects the main project, make it in `agent/` or `frontend/` instead, not here.
- Engine recommendation is **GoRules (Zen/JDM)** as default; alternatives are scenario-driven (see `prd.md` §7). Do not hard-commit an engine before the §10 open questions are answered.
- The round-trip A/B decision (externalization vs code generation, `prd.md` §5.5) is **unconfirmed** and shapes the whole design — surface it, don't silently assume one.
- Rule extraction from legacy code is precision-sensitive: any extracted rule is a **human-reviewed candidate**, never auto-applied. Preserve source traceability and Korean text.
- Prefer additive design notes over speculative implementation. This is a planning track until the customer confirms scope and provides sample materials (`prd.md` §10).

## Instruction Priority
- This `AGENTS.md` and `prd.md` govern work inside `rule-engine/`.
- For anything outside this directory, defer to the root `AGENTS.md` and the relevant app's `AGENTS.md`.
