# AGENTS.md

## Purpose

This directory is an isolated application: the **Canonical Business Rules Management & Delivery Platform** for governed finance/insurance decision logic. It is not part of the Telecom Business Knowledge Assistant chat/RAG product.

Read `prd.md` first, then `architecture.md`, then the **active roadmap at the top** of `IMPLEMENTATION_PLAN.md`.

## Current Product Goal

Complete one useful small-repository round trip:

```text
public GitHub Java repo → pinned evidence-backed candidates
→ business-friendly canonical edit → review/approve
→ deterministic Java + tests → target tests
→ pushed branch → reviewable GitHub pull request
```

After that passes, complete the same governed delivery loop from one selected small cloud-PostgreSQL table/view.

The product core is canonical rule authoring, governance, testing, and delivery. Mining is a bootstrap/reconciliation assistant, not the product source of truth.

## Active Architecture Rules

- The user-facing governed model is the **Canonical Decision Package**: vocabulary, decision tables, lookups, composition, business scenarios, evidence, effective dates, and target binding.
- The restricted Canonical Rule IR is the deterministic executable representation compiled from an approved package. Normal business authoring must not require editing IR or raw JSON.
- Extracted rules are candidates only. Preserve exact immutable source evidence, assumptions, unresolved fragments, tool transcript, and confidence per field. Nothing is auto-approved.
- Production Java and JUnit are generated deterministically. For the active Mode-B path, compiled generated Java and configured target tests are authoritative.
- “Deploy back” for the active MVP means a remotely pushed branch and reviewable GitHub pull request. Never auto-merge or claim downstream production deployment.
- Keep Korean text byte-safe and preserve maker-checker, immutable revisions, effective dating, audit, secret redaction, and test-database safety.

## Small-First Analysis Policy

Use progressive evidence acquisition:

1. pinned Git commit, manifests, `git`, `rg`, and bounded source/test reads;
2. Tree-sitter or equivalent structural query when text evidence is insufficient;
3. targeted JavaParser/SymbolSolver, OpenRewrite, or JDT LS when a concrete symbol/type/reference question remains;
4. human review for unresolved ambiguity;
5. Joern/SootUp only after a recorded real failure demonstrates why lighter tiers are insufficient and a human activates that work.

Joern, a graph database, Docker, or a heavyweight analysis worker is not a base prerequisite. Repository size alone is not a reason to escalate.

## Task Selection

- Select the first unblocked unchecked `F-*` task in the active section of `IMPLEMENTATION_PLAN.md`.
- M0–M11 are historical appendix records. Do not select or resume them unless a human explicitly reactivates a specific item.
- Do not prioritize container hardening, RDS cutover, OIDC, multi-site scale, 10k performance, second languages/DBMSs, Mode A, DMN/DRL/C#, stored procedures, UI mining, or heavyweight analysis before the active full-flow acceptance passes.
- Preserve existing historical capabilities and regression coverage, but do not expand them speculatively.

## Evidence And Claims

- Synthetic fixtures prove only their explicit contracts.
- The current fixed Java miner does not prove arbitrary Java compatibility.
- A local bare Git branch or PR-equivalent report does not prove a real GitHub pull-request flow.
- A deterministic C# artifact without a compiler does not prove executable C# delivery.
- Restricted DMN/DRL/PL/pgSQL/HTML fixtures do not prove real-site compatibility.
- Never claim production readiness, real-site mining accuracy, scale, or non-technical usability without matching acceptance evidence.

Label results explicitly as unit/synthetic, dummy-repository, cloud-DB integration, or real-site evidence.

## Runtime And Safety

- Active local runtime: native API, worker, and UI using Git, Java 17, and the existing cloud PostgreSQL. Docker PostgreSQL is not required.
- Platform persistence and source-rule DB access use separate configuration/roles even if hosted on the same PostgreSQL server. Source-rule access is read-only and allowlisted.
- Destructive automated DB tests must target an isolated `*_test` database or explicitly disposable isolated schema and must fail closed otherwise.
- Secrets come from environment/secret references. Never commit or print credentials, tokens, connection URLs with passwords, or provider keys.
- Do not modify or wire this application into the knowledge-assistant backend/frontend.

## Files

- `prd.md` — product requirements and acceptance source of truth.
- `architecture.md` — architecture decisions, package/IR boundary, evidence pipeline, and active technology choices.
- `IMPLEMENTATION_PLAN.md` — active `F-*` execution queue followed by historical M0–M11 evidence.
- `docs/` — operational and demo material; historical production-hardening documents do not override the active roadmap.
