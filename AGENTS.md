# AGENTS.md

## Purpose
This directory is an **isolated track**: the **Rule-Engine-Based Source Generation Module** for finance/insurance enrollment logic. It is the deferred "PGM source-generation" direction mentioned in the Telecom Business Knowledge Assistant PRD (`../agent/services/knowledge-api/prd.md`, §4.10), kept separate so its scope does not pollute the active knowledge-assistant work.

Read `prd.md` in this directory as the source of truth for this track before doing anything here.

## Scope Boundary (read first)
- This track is **NOT** part of the knowledge-assistant chat/RAG product. Do not mix its requirements with `agent/` or `frontend/`.
- The **only** shared component is the existing document/knowledge **extraction pipeline**, reused as one rule-extraction source (see `prd.md` §5.2 / §6, source 2d).
- Not reused from the main project: chat/RAG retrieval, citation surfaces, Neptune telecom graph schema, NUEL/ProcessMap content.
- **Status: design/groundwork only.** Nothing here is in active implementation. Do not treat this as a build spec or wire it into the running backend/frontend.

## Domain
- Business problem: enrollment logic (`가입 Rule`) for financial/insurance products is buried in source code; this track manages it as **rules-as-data** in a governed repository, with an optional path to reflect edited rules back into deployable source.
- Customer context confirmed 2026-06-23 and 2026-06-29 (see `prd.md` §1, §10).

## Files In This Track
- `prd.md` — track PRD (source of truth).
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
